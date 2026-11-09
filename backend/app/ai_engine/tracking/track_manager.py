"""
Module 5 – IoU-Based Track Manager
=====================================
Concrete implementation of ``BaseTracker`` using Intersection-over-Union
assignment via the Hungarian algorithm (``scipy.optimize.linear_sum_assignment``).

Algorithm overview
------------------
Each incoming set of person detections is matched against existing active
tracks by computing the IoU between each detection box and each track's
last known bounding box. The Hungarian algorithm finds the globally optimal
one-to-one assignment. Unmatched detections spawn new tracks. Unmatched tracks
age by one frame; tracks older than ``MAX_TRACK_AGE`` are purged.

Face detections are associated with their matched track via the parent
``person_detection_id`` link. The track records the best (highest combined
confidence) observation seen so far.

This implementation is intentionally simple and replaceable. A more
sophisticated algorithm (SORT, ByteTrack, DeepSORT) can be substituted by
providing a new ``BaseTracker`` subclass.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict

from app.ai_engine.config.settings import ai_settings
from app.ai_engine.schemas.observations import (
    BoundingBox,
    FaceDetection,
    PersonDetection,
    TrackState,
    TrackStatus,
)
from app.ai_engine.tracking.tracker import BaseTracker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal track representation (richer than the public TrackState schema)
# ---------------------------------------------------------------------------


class _Track:
    """
    Internal mutable track object. One instance per active person track.
    Converted to ``TrackState`` for external consumption.
    """

    _id_counter: int = 0

    def __init__(
        self,
        detection: PersonDetection,
        face: FaceDetection | None,
        frame_index: int,
        camera_id: int,
    ) -> None:
        _Track._id_counter += 1
        self.track_id = f"TRACK-{_Track._id_counter:05d}"
        self.camera_id = camera_id

        self.first_seen: datetime = detection.timestamp
        self.last_seen: datetime = detection.timestamp
        self.current_bbox: BoundingBox = detection.bounding_box
        self.observation_count: int = 1
        self.missed_frames: int = 0
        self.status: TrackStatus = TrackStatus.ACTIVE
        self.last_frame_index: int = frame_index
        self.last_emit_frame: int = 0  # frame_index when candidate was last emitted

        # Best observation (highest combined confidence)
        self.best_frame_reference: str = detection.frame_reference
        self.best_person_confidence: float = detection.detection_confidence
        self.best_face_confidence: float = face.face_detection_confidence if face else 0.0
        self.best_face_bbox: BoundingBox | None = face.bounding_box if face else None
        self.best_landmark_points: list[tuple[float, float]] | None = (
            face.landmark_points if face else None
        )
        self.best_timestamp: datetime = detection.timestamp

    def update(
        self,
        detection: PersonDetection,
        face: FaceDetection | None,
        frame_index: int,
    ) -> None:
        """Update track with a newly matched detection."""
        self.last_seen = detection.timestamp
        self.current_bbox = detection.bounding_box
        self.observation_count += 1
        self.missed_frames = 0
        self.status = TrackStatus.ACTIVE
        self.last_frame_index = frame_index

        # Update best observation if this frame has higher combined confidence
        combined_new = detection.detection_confidence + (
            face.face_detection_confidence if face else 0.0
        )
        combined_best = self.best_person_confidence + self.best_face_confidence

        if combined_new > combined_best:
            self.best_frame_reference = detection.frame_reference
            self.best_person_confidence = detection.detection_confidence
            self.best_face_confidence = face.face_detection_confidence if face else 0.0
            self.best_face_bbox = face.bounding_box if face else None
            self.best_landmark_points = face.landmark_points if face else None
            self.best_timestamp = detection.timestamp

    def mark_missed(self) -> None:
        """Increment missed-frame counter and update status."""
        self.missed_frames += 1
        if self.missed_frames >= 1:
            self.status = TrackStatus.LOST

    def to_state(self) -> TrackState:
        """Convert to the public ``TrackState`` schema."""
        return TrackState(
            track_id=self.track_id,
            camera_id=self.camera_id,
            first_seen=self.first_seen,
            last_seen=self.last_seen,
            current_bounding_box=self.current_bbox,
            observation_count=self.observation_count,
            best_frame_reference=self.best_frame_reference,
            best_person_confidence=self.best_person_confidence,
            best_face_confidence=self.best_face_confidence,
            status=self.status,
            missed_frames=self.missed_frames,
            last_emit_frame=self.last_emit_frame,
        )


# ---------------------------------------------------------------------------
# Track Manager
# ---------------------------------------------------------------------------


class IoUTrackManager(BaseTracker):
    """
    Short-term person tracker using IoU assignment.

    One instance should be created per active camera stream.
    """

    def __init__(
        self,
        camera_id: int,
        max_track_age: int | None = None,
        iou_threshold: float | None = None,
    ) -> None:
        self._camera_id = camera_id
        self._max_age = max_track_age if max_track_age is not None else ai_settings.MAX_TRACK_AGE
        self._iou_threshold = (
            iou_threshold if iou_threshold is not None else ai_settings.IOU_ASSIGNMENT_THRESHOLD
        )
        self._tracks: Dict[str, _Track] = {}  # track_id → _Track
        self._total_created: int = 0

    # -------------------------------------------------------------------------
    # BaseTracker interface
    # -------------------------------------------------------------------------

    def update(
        self,
        detections: list[PersonDetection],
        face_detections: list[FaceDetection],
        timestamp: datetime,
        frame_index: int,
    ) -> list[TrackState]:
        """
        Match detections to existing tracks and update state.

        Steps
        -----
        1. Build a face lookup: person_detection_id → FaceDetection.
        2. Compute the IoU cost matrix between active tracks and new detections.
        3. Run the Hungarian algorithm to find the optimal assignment.
        4. Update matched tracks; create new tracks for unmatched detections.
        5. Age unmatched tracks; purge those that exceed MAX_TRACK_AGE.
        6. Return the full list of active + lost tracks.
        """
        # Step 1: index face detections by their parent detection ID
        face_map: dict[str, FaceDetection] = {
            fd.person_detection_id: fd for fd in face_detections
        }

        active_tracks = list(self._tracks.values())

        if not detections:
            # No detections → age all tracks
            self._age_unmatched(active_tracks, set())
            self._purge_expired()
            return self._active_states()

        if not active_tracks:
            # No existing tracks → create one per detection
            for det in detections:
                self._create_track(det, face_map.get(det.detection_id), frame_index)
            return self._active_states()

        # Step 2: build IoU cost matrix
        iou_matrix = _build_iou_matrix(active_tracks, detections)

        # Step 3: Hungarian assignment (minimise cost = maximise IoU)
        matched_track_ids, matched_det_ids = _hungarian_match(
            iou_matrix, active_tracks, detections, self._iou_threshold
        )

        # Step 4a: update matched tracks
        for track_id, det_idx in zip(matched_track_ids, matched_det_ids):
            det = detections[det_idx]
            face = face_map.get(det.detection_id)
            self._tracks[track_id].update(det, face, frame_index)

        # Step 4b: create new tracks for unmatched detections
        matched_det_set = set(matched_det_ids)
        for idx, det in enumerate(detections):
            if idx not in matched_det_set:
                self._create_track(det, face_map.get(det.detection_id), frame_index)

        # Step 5: age unmatched tracks and purge expired
        matched_track_set = set(matched_track_ids)
        self._age_unmatched(active_tracks, matched_track_set)
        self._purge_expired()

        return self._active_states()

    def get_active_tracks(self) -> list[TrackState]:
        return self._active_states()

    def reset(self) -> None:
        self._tracks.clear()
        self._total_created = 0
        _Track._id_counter = 0
        logger.info("[TrackManager] camera_id=%d tracks reset.", self._camera_id)

    @property
    def track_count(self) -> int:
        return self._total_created

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _create_track(
        self,
        detection: PersonDetection,
        face: FaceDetection | None,
        frame_index: int,
    ) -> _Track:
        track = _Track(detection, face, frame_index, self._camera_id)
        self._tracks[track.track_id] = track
        self._total_created += 1
        logger.debug(
            "[TrackManager] camera_id=%d | Created %s (total=%d)",
            self._camera_id,
            track.track_id,
            self._total_created,
        )
        return track

    def _age_unmatched(
        self, all_tracks: list[_Track], matched_ids: set[str]
    ) -> None:
        for track in all_tracks:
            if track.track_id not in matched_ids:
                track.mark_missed()

    def _purge_expired(self) -> None:
        expired = [
            tid
            for tid, track in self._tracks.items()
            if track.missed_frames > self._max_age
        ]
        for tid in expired:
            self._tracks[tid].status = TrackStatus.EXPIRED
            del self._tracks[tid]
            logger.debug(
                "[TrackManager] camera_id=%d | Purged expired track %s",
                self._camera_id,
                tid,
            )

    def _active_states(self) -> list[TrackState]:
        return [t.to_state() for t in self._tracks.values()]


# ---------------------------------------------------------------------------
# Helpers (module-level, stateless)
# ---------------------------------------------------------------------------


def _build_iou_matrix(
    tracks: list[_Track], detections: list[PersonDetection]
) -> list[list[float]]:
    """Build a (num_tracks × num_detections) IoU matrix."""
    matrix: list[list[float]] = []
    for track in tracks:
        row = [
            track.current_bbox.iou(det.bounding_box)
            for det in detections
        ]
        matrix.append(row)
    return matrix


def _hungarian_match(
    iou_matrix: list[list[float]],
    tracks: list[_Track],
    detections: list[PersonDetection],
    threshold: float,
) -> tuple[list[str], list[int]]:
    """
    Apply the Hungarian algorithm to the negated IoU cost matrix.

    Returns two parallel lists:
    - matched track IDs
    - matched detection indices

    Pairs whose IoU is below ``threshold`` are discarded.
    """
    try:
        import numpy as np  # noqa: PLC0415
        from scipy.optimize import linear_sum_assignment  # noqa: PLC0415
    except ImportError as exc:
        logger.warning("[TrackManager] scipy not available; falling back to greedy match: %s", exc)
        return _greedy_match(iou_matrix, tracks, detections, threshold)

    cost = np.array(iou_matrix, dtype=np.float32)
    row_indices, col_indices = linear_sum_assignment(-cost)  # maximise IoU

    matched_track_ids: list[str] = []
    matched_det_ids: list[int] = []

    for row, col in zip(row_indices, col_indices):
        if cost[row, col] >= threshold:
            matched_track_ids.append(tracks[row].track_id)
            matched_det_ids.append(col)

    return matched_track_ids, matched_det_ids


def _greedy_match(
    iou_matrix: list[list[float]],
    tracks: list[_Track],
    detections: list[PersonDetection],
    threshold: float,
) -> tuple[list[str], list[int]]:
    """
    Fallback greedy assignment when scipy is unavailable.
    Greedily assigns highest-IoU pairs without global optimality.
    """
    matched_track_ids: list[str] = []
    matched_det_ids: list[int] = []
    used_tracks: set[int] = set()
    used_dets: set[int] = set()

    # Flatten all (iou, track_idx, det_idx) tuples and sort descending
    pairs = [
        (iou_matrix[t][d], t, d)
        for t in range(len(tracks))
        for d in range(len(detections))
    ]
    pairs.sort(reverse=True)

    for iou, t_idx, d_idx in pairs:
        if iou < threshold:
            break
        if t_idx in used_tracks or d_idx in used_dets:
            continue
        matched_track_ids.append(tracks[t_idx].track_id)
        matched_det_ids.append(d_idx)
        used_tracks.add(t_idx)
        used_dets.add(d_idx)

    return matched_track_ids, matched_det_ids
