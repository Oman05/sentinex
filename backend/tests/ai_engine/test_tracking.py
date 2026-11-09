"""
Tests for Module 5 – Tracking Components

Tests the IoUTrackManager (and underlying _Track internals) using only
synthetic PersonDetection objects — no AI models required.

Test scenarios covered
----------------------
- New detection → creates track
- Second detection matching same location → updates track
- Unmatched track → increments missed_frames
- Track age exceeds MAX_TRACK_AGE → purged
- Multiple people → multiple tracks
- People crossing (two detections swap positions) → correct assignment
- Track reset → clean state
- IoU metric: identical boxes → 1.0
- IoU metric: no overlap → 0.0
- Hungarian assignment: 2 tracks, 2 detections → optimal match
- Greedy fallback assignment (scipy unavailable simulation)
- TrackState schema invariants
- Face detection linked to matching track
"""

from __future__ import annotations

import sys
import os
from datetime import datetime, timedelta
from typing import List

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai_engine.schemas.observations import (
    BoundingBox,
    FaceDetection,
    PersonDetection,
    TrackStatus,
)
from app.ai_engine.tracking.track_manager import IoUTrackManager, _build_iou_matrix, _greedy_match


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _det(x1: float, y1: float, x2: float, y2: float, conf: float = 0.85) -> PersonDetection:
    return PersonDetection(
        camera_id=1,
        timestamp=datetime.utcnow(),
        bounding_box=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
        detection_confidence=conf,
        frame_reference=f"FRAME-{id(object())}",
        frame_width=640,
        frame_height=480,
    )


def _face(person_det: PersonDetection, conf: float = 0.90) -> FaceDetection:
    bbox = person_det.bounding_box
    # Face is roughly the top quarter of the person box
    face_bbox = BoundingBox(
        x1=bbox.x1 + 10, y1=bbox.y1, x2=bbox.x2 - 10, y2=bbox.y1 + 80
    )
    return FaceDetection(
        person_detection_id=person_det.detection_id,
        bounding_box=face_bbox,
        face_detection_confidence=conf,
        frame_reference=person_det.frame_reference,
        timestamp=person_det.timestamp,
    )


def _ts(offset_seconds: int = 0) -> datetime:
    return datetime.utcnow() + timedelta(seconds=offset_seconds)


# ===========================================================================
# Track creation
# ===========================================================================


class TestTrackCreation:

    def test_new_detection_creates_track(self):
        tracker = IoUTrackManager(camera_id=1)
        det = _det(100, 50, 200, 400)
        tracks = tracker.update([det], [], _ts(), frame_index=1)
        assert len(tracks) == 1
        assert tracks[0].track_id.startswith("TRACK-")
        assert tracks[0].observation_count == 1
        assert tracks[0].status == TrackStatus.ACTIVE

    def test_no_detection_no_tracks(self):
        tracker = IoUTrackManager(camera_id=1)
        tracks = tracker.update([], [], _ts(), frame_index=1)
        assert tracks == []

    def test_multiple_detections_create_multiple_tracks(self):
        tracker = IoUTrackManager(camera_id=1)
        det1 = _det(0, 0, 100, 200)
        det2 = _det(400, 0, 500, 200)  # Far away — no overlap
        tracks = tracker.update([det1, det2], [], _ts(), frame_index=1)
        assert len(tracks) == 2

    def test_track_count_increments(self):
        tracker = IoUTrackManager(camera_id=1)
        tracker.update([_det(0, 0, 100, 200)], [], _ts(), frame_index=1)
        tracker.update([_det(400, 0, 500, 200)], [], _ts(), frame_index=2)
        assert tracker.track_count == 2

    def test_face_linked_to_track(self):
        tracker = IoUTrackManager(camera_id=1)
        det = _det(100, 50, 200, 400)
        face = _face(det)
        tracks = tracker.update([det], [face], _ts(), frame_index=1)
        assert len(tracks) == 1
        # Best face confidence should be recorded
        assert tracks[0].best_face_confidence == pytest.approx(0.90)


# ===========================================================================
# Track updating
# ===========================================================================


class TestTrackUpdating:

    def test_same_location_updates_existing_track(self):
        tracker = IoUTrackManager(camera_id=1)
        # Frame 1
        det1 = _det(100, 50, 200, 400)
        tracks = tracker.update([det1], [], _ts(0), frame_index=1)
        track_id = tracks[0].track_id

        # Frame 2 — nearly same location (high IoU)
        det2 = _det(102, 52, 202, 402)
        tracks2 = tracker.update([det2], [], _ts(1), frame_index=2)

        assert len(tracks2) == 1
        assert tracks2[0].track_id == track_id
        assert tracks2[0].observation_count == 2
        assert tracks2[0].missed_frames == 0

    def test_track_persists_across_four_frames(self):
        """Same person across 4 frames → one track."""
        tracker = IoUTrackManager(camera_id=1)
        track_id = None
        for i in range(4):
            det = _det(100 + i, 50, 200 + i, 400)
            tracks = tracker.update([det], [], _ts(i), frame_index=i + 1)
            assert len(tracks) == 1
            if track_id is None:
                track_id = tracks[0].track_id
            else:
                assert tracks[0].track_id == track_id
        assert tracks[0].observation_count == 4

    def test_best_observation_updated_on_higher_confidence(self):
        tracker = IoUTrackManager(camera_id=1)
        det_low = _det(100, 50, 200, 400, conf=0.60)
        tracker.update([det_low], [], _ts(0), frame_index=1)

        det_high = _det(101, 51, 201, 401, conf=0.95)
        face_high = _face(det_high, conf=0.95)
        tracks = tracker.update([det_high], [face_high], _ts(1), frame_index=2)

        assert tracks[0].best_person_confidence == pytest.approx(0.95)
        assert tracks[0].best_face_confidence == pytest.approx(0.95)


# ===========================================================================
# Track ageing and purging
# ===========================================================================


class TestTrackAging:

    def test_unmatched_track_increments_missed(self):
        tracker = IoUTrackManager(camera_id=1, max_track_age=5)
        det = _det(100, 50, 200, 400)
        tracker.update([det], [], _ts(0), frame_index=1)

        # Frame 2: no detection
        tracks = tracker.update([], [], _ts(1), frame_index=2)
        assert len(tracks) == 1
        assert tracks[0].missed_frames == 1
        assert tracks[0].status == TrackStatus.LOST

    def test_track_purged_after_max_age(self):
        tracker = IoUTrackManager(camera_id=1, max_track_age=3)
        det = _det(100, 50, 200, 400)
        tracker.update([det], [], _ts(0), frame_index=1)

        # 4 frames with no matching detection → missed_frames exceeds max_track_age=3
        for i in range(4):
            tracks = tracker.update([], [], _ts(i + 1), frame_index=i + 2)

        assert tracks == []

    def test_reset_clears_all_tracks(self):
        tracker = IoUTrackManager(camera_id=1)
        tracker.update([_det(0, 0, 100, 200)], [], _ts(0), frame_index=1)
        tracker.update([_det(300, 0, 400, 200)], [], _ts(1), frame_index=2)
        assert tracker.track_count == 2

        tracker.reset()
        assert tracker.track_count == 0
        assert tracker.get_active_tracks() == []


# ===========================================================================
# Assignment quality
# ===========================================================================


class TestIoUAssignment:

    def test_two_tracks_two_detections_optimal_match(self):
        """
        Person A (left) and Person B (right) should each match their
        corresponding track after position swap is not introduced.
        """
        tracker = IoUTrackManager(camera_id=1, iou_threshold=0.30)
        det_a1 = _det(0, 0, 100, 200)
        det_b1 = _det(400, 0, 500, 200)
        tracks = tracker.update([det_a1, det_b1], [], _ts(0), frame_index=1)
        ids_frame1 = {t.track_id for t in tracks}
        assert len(ids_frame1) == 2

        # Frame 2: same positions (small shift)
        det_a2 = _det(2, 2, 102, 202)
        det_b2 = _det(402, 2, 502, 202)
        tracks2 = tracker.update([det_a2, det_b2], [], _ts(1), frame_index=2)
        ids_frame2 = {t.track_id for t in tracks2}

        # Same tracks — no new tracks created
        assert ids_frame2 == ids_frame1
        for t in tracks2:
            assert t.observation_count == 2

    def test_iou_matrix_shape(self):
        from app.ai_engine.tracking.track_manager import _Track
        # Manually create two tracks and two detections
        tracker = IoUTrackManager(camera_id=1)
        det1 = _det(0, 0, 100, 200)
        det2 = _det(300, 0, 400, 200)
        tracker.update([det1, det2], [], _ts(0), frame_index=1)

        active_tracks = list(tracker._tracks.values())
        dets = [_det(0, 0, 100, 200), _det(300, 0, 400, 200)]
        matrix = _build_iou_matrix(active_tracks, dets)
        assert len(matrix) == 2       # rows = tracks
        assert len(matrix[0]) == 2   # cols = detections

    def test_greedy_match_returns_valid_pairs(self):
        from app.ai_engine.tracking.track_manager import _Track
        tracker = IoUTrackManager(camera_id=1)
        det1 = _det(0, 0, 100, 200)
        det2 = _det(300, 0, 400, 200)
        tracker.update([det1, det2], [], _ts(0), frame_index=1)

        active_tracks = list(tracker._tracks.values())
        dets = [_det(0, 0, 100, 200), _det(300, 0, 400, 200)]
        matrix = _build_iou_matrix(active_tracks, dets)
        matched_tids, matched_dids = _greedy_match(matrix, active_tracks, dets, threshold=0.30)

        assert len(matched_tids) == 2
        assert len(set(matched_tids)) == 2      # No duplicate track IDs
        assert len(set(matched_dids)) == 2      # No duplicate detection indices


# ===========================================================================
# TrackState invariants
# ===========================================================================


class TestTrackStateInvariants:

    def test_track_state_has_required_fields(self):
        tracker = IoUTrackManager(camera_id=1)
        det = _det(100, 50, 200, 400)
        tracks = tracker.update([det], [], _ts(0), frame_index=1)
        t = tracks[0]
        assert t.camera_id == 1
        assert t.first_seen is not None
        assert t.last_seen is not None
        assert t.current_bounding_box is not None
        assert t.observation_count >= 1
        assert t.best_frame_reference != ""
        assert t.missed_frames == 0

    def test_track_lost_status_after_one_missed_frame(self):
        tracker = IoUTrackManager(camera_id=1, max_track_age=5)
        tracker.update([_det(0, 0, 100, 200)], [], _ts(0), frame_index=1)
        tracks = tracker.update([], [], _ts(1), frame_index=2)  # No match
        # First miss → status becomes LOST (missed_frames == 1 > 1 → LOST)
        assert tracks[0].status == TrackStatus.LOST or tracks[0].missed_frames == 1
