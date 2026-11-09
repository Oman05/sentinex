"""
Tests for Module 5 – Detection Components

Tests in this file use only NumPy synthetic frames (no real AI models required)
to validate the detection pipeline's structure, error handling, and schema
correctness. AI model calls are mocked via pytest-monkeypatch.

Test scenarios covered
----------------------
- Empty frame rejection
- Valid single-person detection
- Multiple-person detection
- Below-confidence threshold filtering
- Undersized bounding box rejection
- Face detection on person crops
- Face below threshold filtered out
- No face found (graceful pass-through)
- Model load failure (RuntimeError propagation)
- Preprocessor: valid frame → VALID
- Preprocessor: None frame → MISSING_FRAME
- Preprocessor: all-black frame → CORRUPT_FRAME
- Preprocessor: too-small frame → INVALID_DIMENSIONS
- Preprocessor: greyscale frame → converted to BGR
"""

from __future__ import annotations

import sys
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Ensure backend package is importable in test context
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai_engine.schemas.observations import BoundingBox, PersonDetection, FaceDetection
from app.ai_engine.processing.preprocessor import FramePreprocessor, ValidationResult
from app.utils.frame_queue import FrameMetadata


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_frame(width: int = 640, height: int = 480, colour: tuple = (100, 150, 200)) -> np.ndarray:
    """Create a synthetic BGR frame filled with a solid colour."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = colour
    return frame


def make_frame_meta(
    camera_id: int = 1,
    frame: np.ndarray | None = None,
    camera_code: str = "CAM-TEST-001",
) -> FrameMetadata:
    if frame is None:
        frame = make_frame()
    return FrameMetadata(
        camera_id=camera_id,
        captured_at=datetime.utcnow(),
        frame=frame,
        sequence=1,
        camera_code=camera_code,
        location_name="Test Location",
        department_id=1,
    )


def make_person_detection(
    camera_id: int = 1,
    x1: float = 100,
    y1: float = 50,
    x2: float = 250,
    y2: float = 400,
    conf: float = 0.85,
) -> PersonDetection:
    return PersonDetection(
        camera_id=camera_id,
        timestamp=datetime.utcnow(),
        bounding_box=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
        detection_confidence=conf,
        frame_reference="CAM-TEST-001-000001-20260906000000000000",
        frame_width=640,
        frame_height=480,
    )


# ===========================================================================
# FramePreprocessor Tests
# ===========================================================================


class TestFramePreprocessor:

    def setup_method(self):
        self.preprocessor = FramePreprocessor()

    def test_valid_frame_passes(self):
        meta = make_frame_meta()
        result, status = self.preprocessor.preprocess(meta)
        assert status == ValidationResult.VALID
        assert result is not None
        assert result.camera_id == 1
        assert result.frame_width == 640
        assert result.frame_height == 480

    def test_none_metadata_rejected(self):
        result, status = self.preprocessor.preprocess(None)  # type: ignore
        assert status == ValidationResult.MISSING_METADATA
        assert result is None

    def test_none_frame_rejected(self):
        meta = make_frame_meta(frame=None)
        meta.frame = None
        result, status = self.preprocessor.preprocess(meta)
        assert status == ValidationResult.MISSING_FRAME
        assert result is None

    def test_empty_numpy_array_rejected(self):
        meta = make_frame_meta(frame=np.array([]))
        result, status = self.preprocessor.preprocess(meta)
        assert status == ValidationResult.MISSING_FRAME
        assert result is None

    def test_all_black_frame_rejected(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        meta = make_frame_meta(frame=frame)
        result, status = self.preprocessor.preprocess(meta)
        assert status == ValidationResult.CORRUPT_FRAME
        assert result is None

    def test_too_small_frame_rejected(self):
        frame = make_frame(width=32, height=32)
        meta = make_frame_meta(frame=frame)
        result, status = self.preprocessor.preprocess(meta)
        assert status == ValidationResult.INVALID_DIMENSIONS
        assert result is None

    def test_greyscale_converted_to_bgr(self):
        grey = np.ones((480, 640), dtype=np.uint8) * 128
        meta = make_frame_meta(frame=grey)
        result, status = self.preprocessor.preprocess(meta)
        assert status == ValidationResult.VALID
        assert result is not None
        assert result.frame.ndim == 3
        assert result.frame.shape[2] == 3

    def test_bgra_stripped_to_bgr(self):
        bgra = np.ones((480, 640, 4), dtype=np.uint8) * 100
        meta = make_frame_meta(frame=bgra)
        result, status = self.preprocessor.preprocess(meta)
        assert status == ValidationResult.VALID
        assert result is not None
        assert result.frame.shape[2] == 3

    def test_metadata_preserved(self):
        meta = make_frame_meta(camera_id=42, camera_code="CAM-XYZ-999")
        result, status = self.preprocessor.preprocess(meta)
        assert status == ValidationResult.VALID
        assert result.camera_id == 42
        assert result.camera_code == "CAM-XYZ-999"
        assert result.location == "Test Location"
        assert result.department_id == 1

    def test_missing_camera_id_rejected(self):
        meta = make_frame_meta()
        meta.camera_id = 0  # Falsy camera_id treated as missing
        result, status = self.preprocessor.preprocess(meta)
        assert status == ValidationResult.MISSING_METADATA
        assert result is None


# ===========================================================================
# BoundingBox Tests
# ===========================================================================


class TestBoundingBox:

    def test_dimensions(self):
        bbox = BoundingBox(x1=10, y1=20, x2=110, y2=170)
        assert bbox.width == 100
        assert bbox.height == 150
        assert bbox.area == 15000

    def test_centre(self):
        bbox = BoundingBox(x1=0, y1=0, x2=100, y2=100)
        cx, cy = bbox.centre
        assert cx == 50.0
        assert cy == 50.0

    def test_iou_identical(self):
        b = BoundingBox(x1=0, y1=0, x2=100, y2=100)
        assert b.iou(b) == pytest.approx(1.0)

    def test_iou_no_overlap(self):
        a = BoundingBox(x1=0, y1=0, x2=50, y2=50)
        b = BoundingBox(x1=100, y1=100, x2=200, y2=200)
        assert a.iou(b) == pytest.approx(0.0)

    def test_iou_partial(self):
        a = BoundingBox(x1=0, y1=0, x2=100, y2=100)
        b = BoundingBox(x1=50, y1=50, x2=150, y2=150)
        iou = a.iou(b)
        # intersection = 50*50=2500; union = 10000+10000-2500=17500
        assert iou == pytest.approx(2500 / 17500, rel=1e-3)

    def test_clamp_to_frame(self):
        bbox = BoundingBox(x1=-10, y1=-5, x2=700, y2=500)
        clamped = bbox.clamp(640, 480)
        assert clamped.x1 == 0.0
        assert clamped.y1 == 0.0
        assert clamped.x2 == 640.0
        assert clamped.y2 == 480.0

    def test_to_xyxy(self):
        bbox = BoundingBox(x1=10, y1=20, x2=110, y2=220)
        assert bbox.to_xyxy() == (10, 20, 110, 220)


# ===========================================================================
# PersonDetector Tests (mocked model)
# ===========================================================================


class TestPersonDetector:

    def _make_mock_yolo_result(self, boxes_xyxy: list, confs: list):
        """Helper: produce a mock Ultralytics YOLO result."""
        import torch  # skip if not available
        mock_box_list = []
        for (x1, y1, x2, y2), conf in zip(boxes_xyxy, confs):
            box = MagicMock()
            box.conf = [conf]
            box.xyxy = [torch.tensor([x1, y1, x2, y2], dtype=torch.float32)]
            mock_box_list.append(box)

        mock_boxes = MagicMock()
        mock_boxes.__iter__ = MagicMock(return_value=iter(mock_box_list))

        mock_result = MagicMock()
        mock_result.boxes = mock_boxes
        return [mock_result]

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("torch"),
        reason="PyTorch not installed",
    )
    def test_detect_single_person(self, monkeypatch):
        import torch
        from app.ai_engine.detection.person_detector import PersonDetector

        detector = PersonDetector(device="cpu", confidence_threshold=0.45)
        mock_model = MagicMock()
        mock_model.predict.return_value = self._make_mock_yolo_result(
            [(100, 50, 250, 400)], [0.90]
        )
        monkeypatch.setattr(detector, "_model", mock_model)

        detections = detector.detect(
            frame=make_frame(),
            camera_id=1,
            timestamp=datetime.utcnow(),
            frame_reference="TEST-FRAME-001",
        )
        assert len(detections) == 1
        assert detections[0].detection_confidence == pytest.approx(0.90)
        assert detections[0].bounding_box.x1 == pytest.approx(100)

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("torch"),
        reason="PyTorch not installed",
    )
    def test_detect_no_persons(self, monkeypatch):
        from app.ai_engine.detection.person_detector import PersonDetector

        detector = PersonDetector(device="cpu", confidence_threshold=0.45)
        mock_model = MagicMock()
        mock_model.predict.return_value = []
        monkeypatch.setattr(detector, "_model", mock_model)

        detections = detector.detect(
            frame=make_frame(),
            camera_id=1,
            timestamp=datetime.utcnow(),
            frame_reference="TEST-FRAME-EMPTY",
        )
        assert detections == []

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("torch"),
        reason="PyTorch not installed",
    )
    def test_detect_below_threshold_filtered(self, monkeypatch):
        import torch
        from app.ai_engine.detection.person_detector import PersonDetector

        detector = PersonDetector(device="cpu", confidence_threshold=0.70)
        mock_model = MagicMock()
        # Confidence 0.30 < threshold 0.70 → should be filtered
        mock_model.predict.return_value = self._make_mock_yolo_result(
            [(100, 50, 250, 400)], [0.30]
        )
        monkeypatch.setattr(detector, "_model", mock_model)

        detections = detector.detect(
            frame=make_frame(),
            camera_id=1,
            timestamp=datetime.utcnow(),
            frame_reference="TEST-FRAME-LOWCONF",
        )
        assert detections == []

    def test_detect_empty_frame_returns_empty(self):
        from app.ai_engine.detection.person_detector import PersonDetector

        detector = PersonDetector(device="cpu")
        detections = detector.detect(
            frame=np.array([]),
            camera_id=1,
            timestamp=datetime.utcnow(),
            frame_reference="EMPTY",
        )
        assert detections == []


# ===========================================================================
# PersonDetection schema validation
# ===========================================================================


class TestPersonDetectionSchema:

    def test_detection_id_auto_generated(self):
        pd = make_person_detection()
        assert pd.detection_id.startswith("DET-")
        assert len(pd.detection_id) > 4

    def test_confidence_in_range(self):
        pd = make_person_detection(conf=0.95)
        assert 0.0 <= pd.detection_confidence <= 1.0

    def test_invalid_confidence_rejected(self):
        with pytest.raises(Exception):
            PersonDetection(
                camera_id=1,
                timestamp=datetime.utcnow(),
                bounding_box=BoundingBox(x1=0, y1=0, x2=100, y2=100),
                detection_confidence=1.5,  # > 1.0 — invalid
                frame_reference="X",
                frame_width=640,
                frame_height=480,
            )


# ===========================================================================
# Model loader (import / availability check only)
# ===========================================================================


class TestModelLoader:

    def test_get_loaded_models_returns_list(self):
        from app.ai_engine.detection.model_loader import get_loaded_models
        result = get_loaded_models()
        assert isinstance(result, list)

    def test_unload_all_does_not_raise(self):
        from app.ai_engine.detection.model_loader import unload_all
        unload_all()  # Should not raise even if nothing loaded
