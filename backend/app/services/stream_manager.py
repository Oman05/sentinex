from __future__ import annotations

from datetime import datetime
from typing import Any

from app.database.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.camera import Camera, CameraStatus
from app.services.stream_health_service import StreamHealthService
from app.utils.frame_queue import BoundedFrameQueue, FrameMetadata
from app.workers.stream_worker import StreamWorker


class StreamManager:
    """
    Central manager orchestrating multi-camera video streams.
    Manages background workers, tracks real-time stream health, and provides
    the clean frame acquisition interface for downstream AI video processing.
    """

    def __init__(self) -> None:
        self.health: StreamHealthService = StreamHealthService()
        self._workers: dict[int, StreamWorker] = {}

    async def start(
        self,
        camera: Camera,
        decrypted_password: str | None = None,
    ) -> StreamWorker:
        """Start an independent streaming worker for the specified camera."""
        await self.stop(camera.id)

        if decrypted_password is None and getattr(camera, "encrypted_password", None):
            try:
                from app.services.camera_service import CameraService
                decrypted_password = CameraService.decrypt_password(camera.encrypted_password)
            except Exception:
                pass

        worker = StreamWorker(
            camera_id=camera.id,
            stream_url=camera.stream_url,
            sample_fps=camera.sample_fps,
            queue_size=camera.queue_size,
            retry_limit=camera.retry_limit,
            on_status=lambda s, t, e: self._persist(camera.id, s, t, e),
            camera_code=camera.camera_code,
            location_name=camera.location_name,
            department_id=camera.department_id,
            username_reference=camera.username_reference,
            decrypted_password=decrypted_password,
        )

        self._workers[camera.id] = worker
        worker.start()

        # Automatically start AI Video Processing Pipeline for this camera stream
        try:
            from app.ai_engine.pipeline.processing_pipeline import video_pipeline
            await video_pipeline.start_camera(
                camera_id=camera.id,
                queue=worker.queue,
                camera_code=camera.camera_code,
                location=camera.location_name,
                department_id=camera.department_id,
            )
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "[StreamManager] Could not start AI pipeline for camera %s: %s", camera.id, exc
            )

        return worker

    async def start_camera(
        self,
        camera: Camera,
        decrypted_password: str | None = None,
    ) -> StreamWorker:
        """Alias for start() to support admin and management API callers."""
        return await self.start(camera, decrypted_password=decrypted_password)

    async def stop(self, camera_id: int) -> None:
        """Stop monitoring a camera stream."""
        try:
            from app.ai_engine.pipeline.processing_pipeline import video_pipeline
            await video_pipeline.stop_camera(camera_id)
        except Exception:
            pass

        worker = self._workers.pop(camera_id, None)
        if worker is not None:
            await worker.stop()
        self._persist(camera_id, "OFFLINE", None, None)

    async def stop_camera(self, camera_id: int) -> None:
        """Alias for stop()."""
        await self.stop(camera_id)

    async def stop_all(self) -> None:
        """Gracefully stop all running camera streams (e.g. during application shutdown)."""
        try:
            from app.ai_engine.pipeline.processing_pipeline import video_pipeline
            await video_pipeline.stop_all()
        except Exception:
            pass
        for camera_id in list(self._workers):
            await self.stop(camera_id)

    def is_running(self, camera_id: int) -> bool:
        """Check whether a camera worker task is actively running."""
        worker = self._workers.get(camera_id)
        return worker is not None and worker._task is not None and not worker._task.done()

    def get_worker(self, camera_id: int) -> StreamWorker | None:
        return self._workers.get(camera_id)

    # ---------------------------------------------------------------------------
    # Clean Interface for Future Module 5: AI Video Processing Pipeline
    # ---------------------------------------------------------------------------

    def get_frame_queue(self, camera_id: int) -> BoundedFrameQueue | None:
        """Retrieve the bounded frame queue for an active camera stream."""
        worker = self._workers.get(camera_id)
        return worker.queue if worker else None

    def get_latest_frame(self, camera_id: int) -> FrameMetadata | None:
        """Fetch the most recently sampled frame and its metadata for a camera."""
        worker = self._workers.get(camera_id)
        return worker.queue.get_latest() if worker else None

    def get_all_active_queues(self) -> dict[int, BoundedFrameQueue]:
        """Return a mapping of camera_id to frame queue for all currently running streams."""
        return {cid: w.queue for cid, w in self._workers.items() if self.is_running(cid)}

    # ---------------------------------------------------------------------------
    # Internal Status Synchronization & Audit Logging
    # ---------------------------------------------------------------------------

    def _persist(
        self,
        camera_id: int,
        status: str,
        seen: datetime | None,
        error: str | None,
    ) -> None:
        previous_status = self.health.get(camera_id).status

        # Update live in-memory telemetry
        if status == "ONLINE":
            self.health.record_frame(camera_id, seen)
        elif status == "ERROR":
            self.health.record_failure(camera_id, error or "Stream error")
        elif status == "CONNECTING":
            self.health.record_connecting(camera_id)
        else:
            self.health.record_offline(camera_id, error)

        # Sync to persistent database
        db = SessionLocal()
        try:
            camera = db.query(Camera).filter(Camera.id == camera_id).first()
            if camera:
                if seen:
                    camera.last_seen_at = seen

                if status == "ERROR":
                    camera.last_error = error or "Stream error"
                    camera.status = CameraStatus.ERROR.value
                    db.add(
                        AuditLog(
                            user_id=None,
                            action="CAMERA_STREAM_ERROR",
                            resource_type="CAMERA",
                            resource_id=camera_id,
                            details=f"Stream failure: {error}",
                        )
                    )
                elif status == "ONLINE":
                    camera.last_error = None
                    camera.status = CameraStatus.ONLINE.value
                    if previous_status in {"ERROR", "OFFLINE"}:
                        db.add(
                            AuditLog(
                                user_id=None,
                                action="STREAM_RECONNECTED",
                                resource_type="CAMERA",
                                resource_id=camera_id,
                                details=f"Camera reconnected online (code: {camera.camera_code})",
                            )
                        )
                elif status == "CONNECTING":
                    camera.status = CameraStatus.CONNECTING.value
                elif status == "OFFLINE":
                    camera.status = CameraStatus.OFFLINE.value

                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()


stream_manager = StreamManager()
