"""
Module 5 – Candidate Builder
==============================
Converts ``TrackState`` objects (produced by the tracker) into
``CandidateObservation`` objects — the standardised interface between
Module 5 and the downstream modules (Module 6 and Module 7).

Duplicate filtering
-------------------
A new candidate is emitted for a track only when:
1. The track is newly created (first observation).
2. The track has accumulated a meaningfully better observation since the
   last emission (improvement in combined confidence beyond the threshold).
3. The number of frames since the last emission exceeds
   ``CANDIDATE_EMIT_INTERVAL``.

This prevents flooding Module 6 with near-identical observations of the
same person standing in one place.

Design invariant
----------------
The returned ``CandidateObservation`` carries NO identity label, NO case
reference, and NO field suggesting a positive identification. It is a
structured perception result that requires downstream assessment and
authorised human review.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.ai_engine.config.settings import ai_settings
from app.ai_engine.processing.frame_processor import FrameResult
from app.ai_engine.schemas.observations import (
    BoundingBox,
    CandidateObservation,
    QualityStatus,
    TrackState,
    TrackStatus,
)

logger = logging.getLogger(__name__)

# Minimum improvement in combined confidence to trigger a mid-track re-emission
_IMPROVEMENT_THRESHOLD = 0.05


@dataclass
class _TrackEmitRecord:
    """Internal record of what was last emitted for a track."""

    last_emit_frame: int = 0
    last_combined_confidence: float = 0.0


class CandidateBuilder:
    """
    Converts ``FrameResult`` + ``TrackState`` objects into ``CandidateObservation``s.

    One instance is created per active camera and maintains lightweight
    per-track emission state to implement duplicate filtering.
    """

    def __init__(
        self,
        camera_code: str = "",
        location: str | None = None,
        department_id: int = 0,
        emit_interval: int | None = None,
    ) -> None:
        self._camera_code = camera_code
        self._location = location
        self._department_id = department_id
        self._emit_interval = (
            emit_interval if emit_interval is not None else ai_settings.CANDIDATE_EMIT_INTERVAL
        )
        # track_id → emission record (cleared when track expires)
        self._emit_records: dict[str, _TrackEmitRecord] = {}

    # -------------------------------------------------------------------------
    # Public interface
    # -------------------------------------------------------------------------

    def build_candidates(
        self,
        frame_result: FrameResult,
        tracks: list[TrackState],
        frame_index: int,
    ) -> list[CandidateObservation]:
        """
        Evaluate each active track and decide whether to emit a new candidate.

        Parameters
        ----------
        frame_result:
            The ``FrameResult`` from the current frame.
        tracks:
            Updated ``TrackState`` list from the tracker.
        frame_index:
            Current frame counter (monotonically increasing per camera).

        Returns
        -------
        A (possibly empty) list of ``CandidateObservation`` objects ready to
        be dispatched to Module 6 and Module 7.
        """
        candidates: list[CandidateObservation] = []

        # Face lookup: find the face that corresponds to each track's best frame.
        # We match by person_detection_id contained in the frame result.
        face_by_detection: dict[str, "FaceDetectionRef"] = {
            fd.person_detection_id: fd
            for fd in frame_result.face_detections
        }
        person_by_ref: dict[str, "PersonDetectionRef"] = {
            pd.detection_id: pd
            for pd in frame_result.person_detections
        }

        for track in tracks:
            if track.status == TrackStatus.EXPIRED:
                # Clean up emit records for expired tracks
                self._emit_records.pop(track.track_id, None)
                continue

            if self._should_emit(track, frame_index):
                candidate = self._build(track, face_by_detection, person_by_ref, frame_result)
                if candidate:
                    record = self._emit_records.setdefault(
                        track.track_id, _TrackEmitRecord()
                    )
                    record.last_emit_frame = frame_index
                    record.last_combined_confidence = (
                        track.best_person_confidence + track.best_face_confidence
                    )
                    candidates.append(candidate)

        if candidates:
            logger.debug(
                "[CandidateBuilder] camera_id=%d | frame=%s | emitting %d candidate(s)",
                frame_result.camera_id,
                frame_result.frame_reference,
                len(candidates),
            )

        return candidates

    def purge_track(self, track_id: str) -> None:
        """Remove emission bookkeeping for a track that has been purged."""
        self._emit_records.pop(track_id, None)

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _should_emit(self, track: TrackState, frame_index: int) -> bool:
        """
        Return True if this track should produce a new candidate.

        Conditions (any one sufficient):
        - Track has never been emitted before.
        - Enough frames have passed since the last emission (emit interval).
        - Combined confidence has improved significantly since last emission.
        """
        record = self._emit_records.get(track.track_id)
        if record is None:
            return True  # First observation

        frames_since_emit = frame_index - record.last_emit_frame
        if frames_since_emit >= self._emit_interval:
            return True

        combined_now = track.best_person_confidence + track.best_face_confidence
        improvement = combined_now - record.last_combined_confidence
        if improvement >= _IMPROVEMENT_THRESHOLD:
            return True

        return False

    def _build(
        self,
        track: TrackState,
        face_by_detection: dict,
        person_by_ref: dict,
        frame_result: FrameResult,
    ) -> CandidateObservation | None:
        """Assemble a ``CandidateObservation`` from a track and current frame data."""
        # Attempt to find face data from current frame; fall back to track metadata
        # Current frame may not have the best observation — use track.best_face_confidence
        # and track.best_frame_reference as the authoritative source.

        # Look up face for any person detection in this frame that belongs to this track
        face_bbox: BoundingBox | None = None
        face_conf: float | None = None
        landmark_points = None

        # Try to find a face in the current frame linked to any detected person
        for fd in frame_result.face_detections:
            parent = person_by_ref.get(fd.person_detection_id)
            if parent is not None:
                # Simple heuristic: the person whose bbox is closest to the track's current bbox
                if parent.bounding_box.iou(track.current_bounding_box) > 0.3:
                    face_bbox = fd.bounding_box
                    face_conf = fd.face_detection_confidence
                    landmark_points = fd.landmark_points
                    break

        # If the track has historically seen a face but none in current frame,
        # use the track's best-frame data (don't fabricate a bbox we don't have)
        if face_bbox is None and track.best_face_confidence > 0:
            face_conf = track.best_face_confidence
            # Note: we don't have the bbox from previous frames stored in track state
            # This is intentional — only current-frame geometry is used

        has_face = face_bbox is not None

        # Extract real face crop base64 for downstream quality & matching
        face_b64 = None
        if has_face and face_bbox is not None and frame_result.frame is not None:
            try:
                import cv2  # noqa: PLC0415
                import base64  # noqa: PLC0415

                fh_raw, fw_raw = frame_result.frame.shape[:2]
                fx1 = max(0, int(face_bbox.x1))
                fy1 = max(0, int(face_bbox.y1))
                fx2 = min(fw_raw, int(face_bbox.x2))
                fy2 = min(fh_raw, int(face_bbox.y2))
                if fx2 > fx1 and fy2 > fy1:
                    crop = frame_result.frame[fy1:fy2, fx1:fx2]
                    ok, enc = cv2.imencode(".jpg", crop)
                    if ok:
                        face_b64 = base64.b64encode(enc.tobytes()).decode("ascii")
            except Exception as crop_exc:
                logger.debug("[CandidateBuilder] Face crop encoding error: %s", crop_exc)

        # Coarse quality assessment
        quality_status = _assess_quality(
            person_conf=track.best_person_confidence,
            face_conf=face_conf,
            has_face=has_face,
        )

        try:
            return CandidateObservation(
                track_id=track.track_id,
                camera_id=frame_result.camera_id,
                camera_code=self._camera_code,
                timestamp=track.last_seen,
                location=self._location,
                department_id=self._department_id,
                person_bbox=track.current_bounding_box,
                face_bbox=face_bbox,
                person_confidence=track.best_person_confidence,
                face_confidence=face_conf,
                frame_reference=track.best_frame_reference,
                quality_status=quality_status,
                observation_count=track.observation_count,
                has_face=has_face,
                landmark_points=landmark_points,
                face_crop_base64=face_b64,
            )
        except Exception as exc:
            logger.warning(
                "[CandidateBuilder] Failed to build candidate for track %s: %s",
                track.track_id,
                exc,
            )
            return None


def _assess_quality(
    person_conf: float,
    face_conf: float | None,
    has_face: bool,
) -> QualityStatus:
    """
    Assign a coarse quality status based on detection confidence scores.

    Module 6 (Face Quality Assessment) will perform the definitive fine-grained
    quality assessment. This is a preliminary filter only.
    """
    if not has_face or face_conf is None:
        return QualityStatus.POOR  # No face → limited matching potential

    if person_conf >= 0.6 and face_conf >= 0.85:
        return QualityStatus.ACCEPTABLE

    if face_conf >= 0.70:
        return QualityStatus.ACCEPTABLE

    return QualityStatus.POOR


# Type aliases for readability in this module
from app.ai_engine.schemas.observations import FaceDetection as FaceDetectionRef  # noqa: E402
from app.ai_engine.schemas.observations import PersonDetection as PersonDetectionRef  # noqa: E402
