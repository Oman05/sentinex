"""
Module 5 – Frame Processor
============================
Orchestrates the per-frame detection pass: person detection → face detection
→ tracker update. Produces a list of updated tracks for every processed frame.

This class is the heart of the perception pipeline. It wires together the
stateless detectors and the stateful tracker, but contains no business logic
about tracking algorithms or identity decisions.

Error handling
--------------
A single frame failure must never crash the pipeline. Every error is caught,
logged, and the method returns an empty list for that frame.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from app.ai_engine.detection.face_detector import FaceDetector
from app.ai_engine.detection.person_detector import PersonDetector
from app.ai_engine.processing.preprocessor import PreprocessedFrame
from app.ai_engine.schemas.observations import BoundingBox, FaceDetection, PersonDetection, TrackState
from app.ai_engine.tracking.tracker import BaseTracker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-frame result bundle
# ---------------------------------------------------------------------------


@dataclass
class FrameResult:
    """
    Complete result for one processed frame.

    Downstream code should use this bundle rather than individual lists to
    ensure all results stay in sync.
    """

    frame_reference: str
    camera_id: int
    timestamp: datetime
    frame: np.ndarray | None = None

    person_detections: list[PersonDetection] = field(default_factory=list)
    face_detections: list[FaceDetection] = field(default_factory=list)
    updated_tracks: list[TrackState] = field(default_factory=list)

    processing_latency_ms: float = 0.0
    success: bool = True
    error_message: str | None = None


# ---------------------------------------------------------------------------
# Frame Processor
# ---------------------------------------------------------------------------


class FrameProcessor:
    """
    Single-frame detection + tracking orchestrator.

    One instance is created per active camera and reused across frames.
    The stateful ``tracker`` must be specific to the same camera.

    Usage
    -----
    >>> processor = FrameProcessor(person_detector, face_detector, tracker)
    >>> result = processor.process(preprocessed_frame, frame_index=42)
    """

    def __init__(
        self,
        person_detector: PersonDetector,
        face_detector: FaceDetector,
        tracker: BaseTracker,
    ) -> None:
        self._person_detector = person_detector
        self._face_detector = face_detector
        self._tracker = tracker

    # -------------------------------------------------------------------------
    # Public interface
    # -------------------------------------------------------------------------

    def process(
        self,
        frame: PreprocessedFrame,
        frame_index: int,
    ) -> FrameResult:
        """
        Run the full perception pass for a single validated frame.

        Sequence
        --------
        1. Person detection
        2. Face detection (on person crops)
        3. Tracker update

        Parameters
        ----------
        frame:
            A pre-validated ``PreprocessedFrame`` from the preprocessor.
        frame_index:
            Monotonically increasing frame counter for this camera stream.
            Used by the tracker for age management.

        Returns
        -------
        A ``FrameResult`` with all detections and updated track states.
        On processing failure, ``FrameResult.success`` is ``False`` and
        ``error_message`` describes the cause.
        """
        t_start = time.perf_counter()
        result = FrameResult(
            frame_reference=frame.frame_reference,
            camera_id=frame.camera_id,
            timestamp=frame.timestamp,
            frame=frame.frame,
        )

        try:
            result.person_detections = self._detect_people(frame)
            if result.person_detections:
                result.face_detections = self._detect_faces(frame, result.person_detections)

            # Direct full-frame face detection fallback if no person/faces found
            if not result.face_detections:
                direct_faces = self._face_detector.detect_on_frame(
                    frame.frame, frame.timestamp, frame.frame_reference
                )
                if direct_faces:
                    h, w = frame.frame.shape[:2]
                    for df in direct_faces:
                        fb = df.bounding_box
                        px1 = max(0.0, fb.x1 - fb.width * 0.5)
                        py1 = max(0.0, fb.y1 - fb.height * 0.2)
                        px2 = min(float(w), fb.x2 + fb.width * 0.5)
                        py2 = min(float(h), fb.y2 + fb.height * 2.5)
                        pd = PersonDetection(
                            camera_id=frame.camera_id,
                            timestamp=frame.timestamp,
                            bounding_box=BoundingBox(x1=px1, y1=py1, x2=px2, y2=py2),
                            detection_confidence=max(0.60, df.face_detection_confidence),
                            frame_reference=frame.frame_reference,
                            frame_width=w,
                            frame_height=h,
                        )
                        df.person_detection_id = pd.detection_id
                        result.person_detections.append(pd)
                        result.face_detections.append(df)

            result.updated_tracks = self._update_tracker(
                result.person_detections,
                result.face_detections,
                frame.timestamp,
                frame_index,
            )
        except Exception as exc:
            result.success = False
            result.error_message = str(exc)
            logger.error(
                "[FrameProcessor] camera_id=%d | frame=%s | Error: %s",
                frame.camera_id,
                frame.frame_reference,
                exc,
                exc_info=True,
            )
        finally:
            elapsed_ms = (time.perf_counter() - t_start) * 1000
            result.processing_latency_ms = round(elapsed_ms, 2)

        logger.debug(
            "[FrameProcessor] camera_id=%d | frame=%s | persons=%d | faces=%d | "
            "tracks=%d | latency=%.1fms | ok=%s",
            result.camera_id,
            result.frame_reference,
            len(result.person_detections),
            len(result.face_detections),
            len(result.updated_tracks),
            result.processing_latency_ms,
            result.success,
        )
        return result

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _detect_people(self, frame: PreprocessedFrame) -> list[PersonDetection]:
        return self._person_detector.detect(
            frame=frame.frame,
            camera_id=frame.camera_id,
            timestamp=frame.timestamp,
            frame_reference=frame.frame_reference,
        )

    def _detect_faces(
        self,
        frame: PreprocessedFrame,
        persons: list[PersonDetection],
    ) -> list[FaceDetection]:
        if not persons:
            return []
        return self._face_detector.detect(
            frame=frame.frame,
            person_detections=persons,
        )

    def _update_tracker(
        self,
        persons: list[PersonDetection],
        faces: list[FaceDetection],
        timestamp: datetime,
        frame_index: int,
    ) -> list[TrackState]:
        return self._tracker.update(
            detections=persons,
            face_detections=faces,
            timestamp=timestamp,
            frame_index=frame_index,
        )
