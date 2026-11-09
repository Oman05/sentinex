"""
Module 5 – Video Processing Pipeline
=======================================
The main async pipeline loop that consumes ``BoundedFrameQueue`` objects from
Module 4's ``StreamManager``, runs the full perception stack, and dispatches
``CandidateObservation`` objects to registered downstream handlers.

Architecture
------------
                 Module 4 StreamManager
                        │
              BoundedFrameQueue (per camera)
                        │
             VideoProcessingPipeline.run()
                        │
                ┌───────┴───────┐
          FramePreprocessor   (validates)
                        │
             FrameProcessor.process()
              ├── PersonDetector
              ├── FaceDetector
              └── IoUTrackManager
                        │
             CandidateBuilder.build_candidates()
                        │
            ┌───────────┴────────────┐
        Module 6               Module 7
   (Face Quality)       (Candidate Matching)

Design rules
------------
- One pipeline coroutine per camera (configurable).
- A single failed frame or model error must not stop the loop.
- Raw frames are consumed from the queue and discarded after processing.
  They are never written to disk here.
- No identity decisions are made; only CandidateObservation objects are emitted.
- Processing events are optionally written to the database for audit/research.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from app.ai_engine.config.settings import ai_settings
from app.ai_engine.detection.face_detector import FaceDetector
from app.ai_engine.detection.person_detector import PersonDetector
from app.ai_engine.metrics.performance_monitor import performance_monitor
from app.ai_engine.processing.candidate_builder import CandidateBuilder
from app.ai_engine.processing.frame_processor import FrameProcessor
from app.ai_engine.processing.preprocessor import FramePreprocessor, ValidationResult
from app.ai_engine.schemas.observations import CandidateObservation
from app.ai_engine.tracking.track_manager import IoUTrackManager
from app.utils.frame_queue import BoundedFrameQueue

logger = logging.getLogger(__name__)

# Type alias for the downstream handler callback
CandidateHandler = Callable[[CandidateObservation], Awaitable[None] | None]


# ---------------------------------------------------------------------------
# Per-camera pipeline worker
# ---------------------------------------------------------------------------


class _CameraPipelineWorker:
    """
    Async worker that processes frames from a single camera's queue.

    Created and managed by ``VideoProcessingPipeline``.
    """

    def __init__(
        self,
        camera_id: int,
        camera_code: str,
        location: str | None,
        department_id: int,
        queue: BoundedFrameQueue,
        handlers: list[CandidateHandler],
        db_writer: "_ProcessingEventWriter | None" = None,
    ) -> None:
        self._camera_id = camera_id
        self._camera_code = camera_code
        self._location = location
        self._department_id = department_id
        self._queue = queue
        self._handlers = handlers
        self._db_writer = db_writer

        # Shared (singleton) detectors — stateless, thread-safe
        self._preprocessor = FramePreprocessor()
        self._person_detector = PersonDetector()
        self._face_detector = FaceDetector()

        # Per-camera stateful components
        self._tracker = IoUTrackManager(camera_id=camera_id)
        self._processor = FrameProcessor(
            self._person_detector, self._face_detector, self._tracker
        )
        self._candidate_builder = CandidateBuilder(
            camera_code=camera_code,
            location=location,
            department_id=department_id,
        )

        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._frame_index: int = 0

    def start(self) -> asyncio.Task:
        if self._task is None or self._task.done():
            self._stop_event.clear()
            self._task = asyncio.create_task(
                self._run(),
                name=f"ai-pipeline-cam-{self._camera_id}",
            )
        return self._task

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
        self._tracker.reset()
        performance_monitor.remove_camera(self._camera_id)
        logger.info("[Pipeline] camera_id=%d pipeline stopped.", self._camera_id)

    async def _run(self) -> None:
        """Main frame-consumption loop."""
        logger.info(
            "[Pipeline] camera_id=%d (%s) pipeline started.", self._camera_id, self._camera_code
        )

        while not self._stop_event.is_set():
            try:
                frame_meta = await asyncio.wait_for(
                    self._queue.get(), timeout=2.0
                )
            except asyncio.TimeoutError:
                # No frames available; check stop event and continue
                continue
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(
                    "[Pipeline] camera_id=%d | Queue read error: %s", self._camera_id, exc
                )
                await asyncio.sleep(0.1)
                continue

            performance_monitor.record_frame_received(self._camera_id)

            # Run blocking AI inference off the event loop
            await asyncio.to_thread(self._process_frame, frame_meta)

            try:
                self._queue.task_done()
            except Exception:
                pass  # Not all queue implementations require task_done

        logger.info("[Pipeline] camera_id=%d pipeline loop exited.", self._camera_id)

    def _process_frame(self, frame_meta: Any) -> None:
        """
        Synchronous frame processing block — runs in a thread pool via
        ``asyncio.to_thread()``. Never raises; all errors are logged.
        """
        self._frame_index += 1

        # 1. Validate & preprocess
        preprocessed, validation_result = self._preprocessor.preprocess(frame_meta)

        if validation_result != ValidationResult.VALID or preprocessed is None:
            performance_monitor.record_frame_dropped(self._camera_id)
            if self._db_writer:
                self._db_writer.write(
                    camera_id=self._camera_id,
                    timestamp=getattr(frame_meta, "captured_at", datetime.utcnow()),
                    frame_reference=getattr(frame_meta, "frame_reference", ""),
                    status="VALIDATION_FAILED",
                    people=0,
                    faces=0,
                    tracks=0,
                    latency_ms=0.0,
                )
            return

        # 2. Detection + tracking
        result = self._processor.process(preprocessed, self._frame_index)

        if not result.success:
            performance_monitor.record_frame_error(self._camera_id)
            logger.warning(
                "[Pipeline] camera_id=%d | Processing error: %s", self._camera_id, result.error_message
            )
            if self._db_writer:
                self._db_writer.write(
                    camera_id=self._camera_id,
                    timestamp=preprocessed.timestamp,
                    frame_reference=preprocessed.frame_reference,
                    status="PROCESSING_ERROR",
                    people=0,
                    faces=0,
                    tracks=len(result.updated_tracks),
                    latency_ms=result.processing_latency_ms,
                )
            return

        performance_monitor.record_frame_processed(
            self._camera_id,
            latency_s=result.processing_latency_ms / 1000,
        )
        performance_monitor.update_active_tracks(self._camera_id, len(result.updated_tracks))

        # 3. Candidate generation
        candidates = self._candidate_builder.build_candidates(
            frame_result=result,
            tracks=result.updated_tracks,
            frame_index=self._frame_index,
        )
        if candidates:
            performance_monitor.record_candidate_emitted(self._camera_id, len(candidates))

        # 4. Optional DB write
        if self._db_writer:
            self._db_writer.write(
                camera_id=self._camera_id,
                timestamp=preprocessed.timestamp,
                frame_reference=preprocessed.frame_reference,
                status="PROCESSED",
                people=len(result.person_detections),
                faces=len(result.face_detections),
                tracks=len(result.updated_tracks),
                latency_ms=result.processing_latency_ms,
            )

        # 5. Dispatch candidates to downstream handlers (async-friendly via schedule)
        if candidates:
            asyncio.get_event_loop().call_soon_threadsafe(
                self._schedule_dispatch, candidates
            )

    def _schedule_dispatch(self, candidates: list[CandidateObservation]) -> None:
        """Schedule async candidate dispatch on the event loop."""
        asyncio.ensure_future(self._dispatch_candidates(candidates))

    async def _dispatch_candidates(self, candidates: list[CandidateObservation]) -> None:
        """Deliver each candidate to every registered downstream handler."""
        for candidate in candidates:
            for handler in self._handlers:
                try:
                    result = handler(candidate)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as exc:
                    logger.error(
                        "[Pipeline] camera_id=%d | Handler error for candidate %s: %s",
                        self._camera_id,
                        candidate.candidate_id,
                        exc,
                    )


# ---------------------------------------------------------------------------
# Database event writer (optional, runs synchronously in the thread pool)
# ---------------------------------------------------------------------------


class _ProcessingEventWriter:
    """
    Writes rows to the ``processing_events`` table.
    Initialised lazily on first write to avoid import-time DB dependency.
    """

    def write(
        self,
        camera_id: int,
        timestamp: datetime,
        frame_reference: str,
        status: str,
        people: int,
        faces: int,
        tracks: int,
        latency_ms: float,
    ) -> None:
        if not ai_settings.PROCESSING_EVENTS_ENABLED:
            return
        try:
            from app.database.session import SessionLocal  # noqa: PLC0415
            from app.models.processing_event import ProcessingEvent  # noqa: PLC0415

            db = SessionLocal()
            try:
                event = ProcessingEvent(
                    camera_id=camera_id,
                    timestamp=timestamp,
                    frame_reference=frame_reference,
                    processing_status=status,
                    people_detected=people,
                    faces_detected=faces,
                    tracks_created=tracks,
                    processing_latency_ms=latency_ms,
                )
                db.add(event)
                db.commit()
            except Exception as db_exc:
                db.rollback()
                logger.debug("[Pipeline] DB write failed: %s", db_exc)
            finally:
                db.close()
        except Exception as exc:
            logger.debug("[Pipeline] ProcessingEventWriter error: %s", exc)


# ---------------------------------------------------------------------------
# Main pipeline orchestrator
# ---------------------------------------------------------------------------


class VideoProcessingPipeline:
    """
    Central orchestrator for the Module 5 AI Video Processing pipeline.

    Manages one ``_CameraPipelineWorker`` per active camera stream.
    Workers are started/stopped dynamically as cameras come online/offline.

    Usage (from FastAPI lifespan)
    -----------------------------
    >>> pipeline = VideoProcessingPipeline()
    >>> pipeline.add_candidate_handler(my_module6_handler)
    >>> await pipeline.start_camera(camera_id=1, camera_code="CAM-001", ...)
    >>> ...
    >>> await pipeline.stop_all()
    """

    def __init__(self) -> None:
        self._workers: dict[int, _CameraPipelineWorker] = {}
        self._handlers: list[CandidateHandler] = []
        self._db_writer = _ProcessingEventWriter()

    # -------------------------------------------------------------------------
    # Handler registration
    # -------------------------------------------------------------------------

    def add_candidate_handler(self, handler: CandidateHandler) -> None:
        """
        Register a downstream handler to receive ``CandidateObservation`` objects.

        Handlers are called in registration order for every emitted candidate.
        Both sync and async handlers are supported.
        """
        self._handlers.append(handler)
        logger.info("[Pipeline] Registered candidate handler: %s", getattr(handler, "__name__", handler))

    def remove_candidate_handler(self, handler: CandidateHandler) -> None:
        try:
            self._handlers.remove(handler)
        except ValueError:
            pass

    # -------------------------------------------------------------------------
    # Camera management
    # -------------------------------------------------------------------------

    async def start_camera(
        self,
        camera_id: int,
        queue: BoundedFrameQueue,
        camera_code: str = "",
        location: str | None = None,
        department_id: int = 0,
    ) -> None:
        """
        Start the AI pipeline for one camera stream.

        Parameters
        ----------
        camera_id:
            Numeric camera ID.
        queue:
            The ``BoundedFrameQueue`` for this camera (from StreamManager).
        camera_code, location, department_id:
            Metadata propagated into candidate observations.
        """
        await self.stop_camera(camera_id)  # Stop existing worker if any

        worker = _CameraPipelineWorker(
            camera_id=camera_id,
            camera_code=camera_code,
            location=location,
            department_id=department_id,
            queue=queue,
            handlers=self._handlers,
            db_writer=self._db_writer,
        )
        self._workers[camera_id] = worker
        worker.start()
        logger.info("[Pipeline] Started AI pipeline for camera_id=%d.", camera_id)

    async def stop_camera(self, camera_id: int) -> None:
        """Stop the AI pipeline for one camera."""
        worker = self._workers.pop(camera_id, None)
        if worker:
            await worker.stop()

    async def stop_all(self) -> None:
        """Gracefully stop all running pipeline workers."""
        for camera_id in list(self._workers):
            await self.stop_camera(camera_id)
        logger.info("[Pipeline] All camera pipelines stopped.")

    def is_running(self, camera_id: int) -> bool:
        worker = self._workers.get(camera_id)
        return worker is not None and worker._task is not None and not worker._task.done()

    def active_camera_ids(self) -> list[int]:
        return [cid for cid in self._workers if self.is_running(cid)]

    # -------------------------------------------------------------------------
    # Public service interfaces (Module 5 internal API)
    # -------------------------------------------------------------------------

    def get_processing_metrics(self, camera_id: int | None = None):
        """
        Return processing metrics.

        Parameters
        ----------
        camera_id:
            If specified, returns metrics for one camera.
            If None, returns a list of snapshots for all cameras.
        """
        if camera_id is not None:
            return performance_monitor.snapshot(camera_id)
        return performance_monitor.all_snapshots()

    def get_pipeline_status(self) -> dict:
        """Return a top-level status summary for the health endpoint."""
        active = self.active_camera_ids()
        return {
            "status": "running" if active else "idle",
            "active_cameras": len(active),
            "camera_ids": active,
        }


# ---------------------------------------------------------------------------
# Module-level singleton — imported by main.py and API routers
# ---------------------------------------------------------------------------
video_pipeline = VideoProcessingPipeline()
