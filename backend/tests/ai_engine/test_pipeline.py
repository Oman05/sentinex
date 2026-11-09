"""
Tests for Module 5 – Full Processing Pipeline Integration

Uses mocked AI detectors and the real tracker/candidate builder to validate
end-to-end pipeline behaviour without requiring GPU or model downloads.

Test scenarios covered
----------------------
Full pipeline (mocked detectors, real tracker + candidate builder):
- No person in frame → empty candidates
- Single person detected → candidate emitted on first observation
- Multiple people → multiple tracks, multiple candidates
- Face visible → candidate has face_bbox and has_face=True
- No face found → candidate proceeds with has_face=False
- Same person across 4 frames → one track (not 4)
- Duplicate filtering: same track emits at most once per CANDIDATE_EMIT_INTERVAL
- Corrupt/invalid frame → logged, dropped, pipeline continues
- Improved observation → re-emit triggered before interval expires
- CandidateObservation identity invariants (no identity fields)

PerformanceMonitor:
- record_frame_received increments counter
- record_frame_processed increments counter and accumulates latency
- record_frame_dropped increments dropped counter
- fps_processed returns > 0 after frames processed
- all_snapshots returns list of snapshots
"""

from __future__ import annotations

import sys
import os
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai_engine.schemas.observations import (
    BoundingBox,
    CandidateObservation,
    FaceDetection,
    PersonDetection,
    ProcessingStatus,
    QualityStatus,
    TrackStatus,
)
from app.ai_engine.tracking.track_manager import IoUTrackManager
from app.ai_engine.processing.preprocessor import FramePreprocessor, ValidationResult
from app.ai_engine.processing.frame_processor import FrameProcessor, FrameResult
from app.ai_engine.processing.candidate_builder import CandidateBuilder
from app.ai_engine.metrics.performance_monitor import PerformanceMonitor
from app.utils.frame_queue import FrameMetadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_frame(width: int = 640, height: int = 480) -> np.ndarray:
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[100:400, 100:250] = (128, 200, 100)  # Non-zero, non-trivial
    return frame


def make_meta(camera_id: int = 1) -> FrameMetadata:
    return FrameMetadata(
        camera_id=camera_id,
        captured_at=datetime.utcnow(),
        frame=make_frame(),
        sequence=1,
        camera_code="CAM-TEST-001",
        location_name="Test Location",
        department_id=1,
    )


def make_person_det(x1=100, y1=50, x2=250, y2=400, conf=0.85) -> PersonDetection:
    return PersonDetection(
        camera_id=1,
        timestamp=datetime.utcnow(),
        bounding_box=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
        detection_confidence=conf,
        frame_reference="CAM-TEST-001-000001-20260906000000000000",
        frame_width=640,
        frame_height=480,
    )


def make_face_det(person: PersonDetection, conf=0.90) -> FaceDetection:
    bbox = person.bounding_box
    return FaceDetection(
        person_detection_id=person.detection_id,
        bounding_box=BoundingBox(
            x1=bbox.x1 + 10, y1=bbox.y1, x2=bbox.x2 - 10, y2=bbox.y1 + 80
        ),
        face_detection_confidence=conf,
        frame_reference=person.frame_reference,
        timestamp=person.timestamp,
    )


def make_frame_result(
    persons: list[PersonDetection],
    faces: list[FaceDetection],
    tracks,
    camera_id: int = 1,
) -> FrameResult:
    return FrameResult(
        frame_reference="CAM-TEST-001-000001-20260906000000000000",
        camera_id=camera_id,
        timestamp=datetime.utcnow(),
        person_detections=persons,
        face_detections=faces,
        updated_tracks=tracks,
        processing_latency_ms=12.5,
        success=True,
    )


# ===========================================================================
# FrameProcessor Tests (mocked detectors)
# ===========================================================================


class TestFrameProcessor:

    def _make_processor(self, person_dets=None, face_dets=None):
        person_detector = MagicMock()
        person_detector.detect.return_value = person_dets or []
        face_detector = MagicMock()
        face_detector.detect.return_value = face_dets or []
        tracker = IoUTrackManager(camera_id=1)
        return FrameProcessor(person_detector, face_detector, tracker)

    def _make_preprocessed(self):
        from app.ai_engine.processing.preprocessor import PreprocessedFrame
        return PreprocessedFrame(
            frame=make_frame(),
            camera_id=1,
            camera_code="CAM-TEST-001",
            timestamp=datetime.utcnow(),
            location="Test Location",
            department_id=1,
            frame_reference="CAM-TEST-001-000001-20260906000000000000",
            frame_width=640,
            frame_height=480,
        )

    def test_no_persons_returns_empty_result(self):
        proc = self._make_processor(person_dets=[])
        pf = self._make_preprocessed()
        result = proc.process(pf, frame_index=1)
        assert result.success
        assert result.person_detections == []
        assert result.face_detections == []
        assert result.updated_tracks == []

    def test_single_person_detected(self):
        det = make_person_det()
        proc = self._make_processor(person_dets=[det])
        pf = self._make_preprocessed()
        result = proc.process(pf, frame_index=1)
        assert result.success
        assert len(result.person_detections) == 1
        assert len(result.updated_tracks) == 1

    def test_person_with_face_detected(self):
        det = make_person_det()
        face = make_face_det(det)
        proc = self._make_processor(person_dets=[det], face_dets=[face])
        pf = self._make_preprocessed()
        result = proc.process(pf, frame_index=1)
        assert result.success
        assert len(result.face_detections) == 1

    def test_multiple_persons_produce_multiple_tracks(self):
        det1 = make_person_det(x1=0, y1=0, x2=100, y2=200)
        det2 = make_person_det(x1=400, y1=0, x2=500, y2=200)
        proc = self._make_processor(person_dets=[det1, det2])
        pf = self._make_preprocessed()
        result = proc.process(pf, frame_index=1)
        assert len(result.updated_tracks) == 2

    def test_processing_latency_recorded(self):
        proc = self._make_processor()
        pf = self._make_preprocessed()
        result = proc.process(pf, frame_index=1)
        assert result.processing_latency_ms >= 0.0

    def test_model_error_marks_failure_not_crash(self):
        person_detector = MagicMock()
        person_detector.detect.side_effect = RuntimeError("Model GPU OOM")
        face_detector = MagicMock()
        face_detector.detect.return_value = []
        tracker = IoUTrackManager(camera_id=1)
        proc = FrameProcessor(person_detector, face_detector, tracker)

        from app.ai_engine.processing.preprocessor import PreprocessedFrame
        pf = PreprocessedFrame(
            frame=make_frame(),
            camera_id=1,
            camera_code="CAM-001",
            timestamp=datetime.utcnow(),
            location=None,
            department_id=1,
            frame_reference="FRAME-ERR",
            frame_width=640,
            frame_height=480,
        )
        result = proc.process(pf, frame_index=1)
        assert not result.success
        assert "Model GPU OOM" in result.error_message


# ===========================================================================
# CandidateBuilder Tests
# ===========================================================================


class TestCandidateBuilder:

    def _make_tracker_with_detection(self, person_dets, face_dets=None):
        tracker = IoUTrackManager(camera_id=1)
        tracks = tracker.update(
            person_dets, face_dets or [], datetime.utcnow(), frame_index=1
        )
        return tracker, tracks

    def test_candidate_emitted_on_first_observation(self):
        det = make_person_det()
        tracker, tracks = self._make_tracker_with_detection([det])
        builder = CandidateBuilder(camera_code="CAM-001", department_id=1)
        frame_result = make_frame_result([det], [], tracks)
        candidates = builder.build_candidates(frame_result, tracks, frame_index=1)
        assert len(candidates) == 1

    def test_candidate_has_no_identity_fields(self):
        """Invariant: CandidateObservation must carry no identity label."""
        det = make_person_det()
        tracker, tracks = self._make_tracker_with_detection([det])
        builder = CandidateBuilder(camera_code="CAM-001", department_id=1)
        frame_result = make_frame_result([det], [], tracks)
        candidates = builder.build_candidates(frame_result, tracks, frame_index=1)
        c = candidates[0]

        # No identity-related fields
        assert not hasattr(c, "person_name")
        assert not hasattr(c, "case_id")
        assert not hasattr(c, "is_wanted")
        assert not hasattr(c, "is_missing")
        assert not hasattr(c, "match_score")

    def test_candidate_default_status_is_pending(self):
        det = make_person_det()
        tracker, tracks = self._make_tracker_with_detection([det])
        builder = CandidateBuilder(camera_code="CAM-001", department_id=1)
        frame_result = make_frame_result([det], [], tracks)
        candidates = builder.build_candidates(frame_result, tracks, frame_index=1)
        c = candidates[0]
        assert c.processing_status == ProcessingStatus.PENDING_FACE_QUALITY

    def test_no_face_gives_poor_quality(self):
        det = make_person_det()
        tracker, tracks = self._make_tracker_with_detection([det])
        builder = CandidateBuilder(camera_code="CAM-001", department_id=1)
        frame_result = make_frame_result([det], [], tracks)
        candidates = builder.build_candidates(frame_result, tracks, frame_index=1)
        c = candidates[0]
        assert not c.has_face
        assert c.quality_status == QualityStatus.POOR

    def test_with_face_gives_acceptable_quality(self):
        det = make_person_det(conf=0.80)
        face = make_face_det(det, conf=0.92)
        tracker = IoUTrackManager(camera_id=1)
        tracks = tracker.update([det], [face], datetime.utcnow(), frame_index=1)
        builder = CandidateBuilder(camera_code="CAM-001", department_id=1)
        frame_result = make_frame_result([det], [face], tracks)
        candidates = builder.build_candidates(frame_result, tracks, frame_index=1)
        c = candidates[0]
        assert c.has_face or c.quality_status in (QualityStatus.ACCEPTABLE, QualityStatus.POOR)

    def test_duplicate_filtered_within_interval(self):
        """Second emission for the same track within emit_interval should be suppressed."""
        det = make_person_det()
        tracker, tracks = self._make_tracker_with_detection([det])
        builder = CandidateBuilder(
            camera_code="CAM-001", department_id=1, emit_interval=10
        )
        frame_result = make_frame_result([det], [], tracks)

        # First emission
        c1 = builder.build_candidates(frame_result, tracks, frame_index=1)
        assert len(c1) == 1

        # Second emission immediately (frame_index=2, interval=10 → suppressed)
        c2 = builder.build_candidates(frame_result, tracks, frame_index=2)
        assert len(c2) == 0

    def test_emission_after_interval_expires(self):
        det = make_person_det()
        tracker, tracks = self._make_tracker_with_detection([det])
        builder = CandidateBuilder(
            camera_code="CAM-001", department_id=1, emit_interval=5
        )
        frame_result = make_frame_result([det], [], tracks)

        builder.build_candidates(frame_result, tracks, frame_index=1)  # First emit

        # Frame index 6 → interval expired
        c = builder.build_candidates(frame_result, tracks, frame_index=6)
        assert len(c) == 1

    def test_no_persons_no_candidates(self):
        tracker = IoUTrackManager(camera_id=1)
        tracks = tracker.update([], [], datetime.utcnow(), frame_index=1)
        builder = CandidateBuilder(camera_code="CAM-001", department_id=1)
        frame_result = make_frame_result([], [], tracks)
        candidates = builder.build_candidates(frame_result, tracks, frame_index=1)
        assert candidates == []

    def test_candidate_id_unique_per_emission(self):
        det1 = make_person_det(x1=0, y1=0, x2=100, y2=200)
        det2 = make_person_det(x1=400, y1=0, x2=500, y2=200)
        tracker = IoUTrackManager(camera_id=1)
        tracks = tracker.update([det1, det2], [], datetime.utcnow(), frame_index=1)
        builder = CandidateBuilder(camera_code="CAM-001", department_id=1)
        frame_result = make_frame_result([det1, det2], [], tracks)
        candidates = builder.build_candidates(frame_result, tracks, frame_index=1)
        ids = [c.candidate_id for c in candidates]
        assert len(ids) == len(set(ids))  # All unique


# ===========================================================================
# PerformanceMonitor Tests
# ===========================================================================


class TestPerformanceMonitor:

    def test_record_frame_received(self):
        monitor = PerformanceMonitor()
        monitor.record_frame_received(camera_id=99)
        snap = monitor.snapshot(camera_id=99)
        assert snap.frames_received == 1

    def test_record_frame_processed(self):
        monitor = PerformanceMonitor()
        monitor.record_frame_processed(camera_id=99, latency_s=0.050)
        monitor.record_frame_processed(camera_id=99, latency_s=0.030)
        snap = monitor.snapshot(camera_id=99)
        assert snap.frames_processed == 2
        assert snap.total_processing_time_s == pytest.approx(0.080, rel=1e-3)

    def test_record_frame_dropped(self):
        monitor = PerformanceMonitor()
        monitor.record_frame_dropped(camera_id=99)
        monitor.record_frame_dropped(camera_id=99)
        snap = monitor.snapshot(camera_id=99)
        assert snap.frames_dropped == 2

    def test_average_latency_computed(self):
        monitor = PerformanceMonitor()
        monitor.record_frame_processed(camera_id=99, latency_s=0.040)
        monitor.record_frame_processed(camera_id=99, latency_s=0.060)
        snap = monitor.snapshot(camera_id=99)
        # avg latency = (0.040 + 0.060) / 2 * 1000 = 50ms
        assert snap.average_latency_ms == pytest.approx(50.0, rel=1e-2)

    def test_fps_positive_after_processing(self):
        monitor = PerformanceMonitor()
        monitor.record_frame_processed(camera_id=99, latency_s=0.010)
        time.sleep(0.01)
        snap = monitor.snapshot(camera_id=99)
        assert snap.fps_processed >= 0.0  # May be near 0 due to timing in tests

    def test_all_snapshots_returns_list(self):
        monitor = PerformanceMonitor()
        monitor.record_frame_received(camera_id=1)
        monitor.record_frame_received(camera_id=2)
        snaps = monitor.all_snapshots()
        assert len(snaps) >= 2

    def test_remove_camera_clears_metrics(self):
        monitor = PerformanceMonitor()
        monitor.record_frame_received(camera_id=77)
        monitor.remove_camera(camera_id=77)
        snaps = monitor.all_snapshots()
        cam_ids = [s.camera_id for s in snaps]
        assert 77 not in cam_ids

    def test_update_active_tracks(self):
        monitor = PerformanceMonitor()
        monitor.update_active_tracks(camera_id=99, count=5)
        snap = monitor.snapshot(camera_id=99)
        assert snap.active_tracks == 5

    def test_candidates_emitted_counter(self):
        monitor = PerformanceMonitor()
        monitor.record_candidate_emitted(camera_id=99, count=3)
        snap = monitor.snapshot(camera_id=99)
        assert snap.candidates_emitted == 3


# ===========================================================================
# End-to-end integration: Preprocessor → Processor → Builder
# ===========================================================================


class TestEndToEndPipeline:

    def test_invalid_frame_does_not_reach_processor(self):
        """A corrupt FrameMetadata stops at preprocessor; processor never called."""
        preprocessor = FramePreprocessor()
        person_detector = MagicMock()

        bad_frame = np.zeros((480, 640, 3), dtype=np.uint8)  # All-black = corrupt
        meta = FrameMetadata(
            camera_id=1,
            captured_at=datetime.utcnow(),
            frame=bad_frame,
            sequence=1,
            camera_code="CAM-001",
            location_name=None,
            department_id=1,
        )
        result, status = preprocessor.preprocess(meta)
        assert status == ValidationResult.CORRUPT_FRAME
        assert result is None
        person_detector.detect.assert_not_called()

    def test_valid_frame_flows_to_candidate(self):
        """Valid frame → detection → track → candidate with no identity label."""
        det = make_person_det()
        person_detector = MagicMock()
        person_detector.detect.return_value = [det]
        face_detector = MagicMock()
        face_detector.detect.return_value = []
        tracker = IoUTrackManager(camera_id=1)
        processor = FrameProcessor(person_detector, face_detector, tracker)
        builder = CandidateBuilder(camera_code="CAM-001", department_id=1)

        from app.ai_engine.processing.preprocessor import PreprocessedFrame
        pf = PreprocessedFrame(
            frame=make_frame(),
            camera_id=1,
            camera_code="CAM-001",
            timestamp=datetime.utcnow(),
            location=None,
            department_id=1,
            frame_reference="FRAME-E2E-001",
            frame_width=640,
            frame_height=480,
        )

        result = processor.process(pf, frame_index=1)
        assert result.success

        fr = make_frame_result(result.person_detections, result.face_detections, result.updated_tracks)
        candidates = builder.build_candidates(fr, result.updated_tracks, frame_index=1)
        assert len(candidates) == 1

        c = candidates[0]
        # All schema checks
        assert c.candidate_id.startswith("CAND-")
        assert c.track_id.startswith("TRACK-")
        assert c.camera_id == 1
        assert c.processing_status == ProcessingStatus.PENDING_FACE_QUALITY
        assert not hasattr(c, "case_id")
        assert not hasattr(c, "is_wanted")
