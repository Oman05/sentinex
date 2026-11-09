"""
Tests for Module 6 – FaceQualityAssessor (End-to-End)
=======================================================
Validates the full quality pipeline: image validation → blur → lighting →
size → pose → occlusion → composite score → classification → match-readiness.

AI Safety Invariant:
    Tests explicitly confirm the assessor never returns identity decisions.
    Only image-quality signals and match-readiness flags are verified.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import numpy as np
import pytest

from app.ai_engine.quality.quality_assessor import FaceQualityAssessor
from app.ai_engine.schemas.observations import BoundingBox
from app.ai_engine.schemas.quality import (
    QualityClassification,
    RejectionReason,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bbox(x1: int = 0, y1: int = 0, x2: int = 100, y2: int = 100) -> BoundingBox:
    return BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)


def _ts() -> datetime:
    return datetime.now(timezone.utc)


def _sharp_face(h: int = 112, w: int = 112) -> np.ndarray:
    """High-frequency (sharp) face crop with natural-ish texture."""
    rng = np.random.default_rng(7)
    img = rng.integers(60, 200, (h, w, 3), dtype=np.uint8)
    return img


def _blurry_face(h: int = 112, w: int = 112) -> np.ndarray:
    """Heavily Gaussian-blurred image with minimal Laplacian variance."""
    import cv2
    img = _sharp_face(h, w)
    return cv2.GaussianBlur(img, (31, 31), 10)


def _tiny_face(h: int = 20, w: int = 20) -> np.ndarray:
    rng = np.random.default_rng(3)
    return rng.integers(50, 200, (h, w, 3), dtype=np.uint8)


def _dark_face(h: int = 112, w: int = 112) -> np.ndarray:
    return np.full((h, w, 3), 10, dtype=np.uint8)


def _bright_face(h: int = 112, w: int = 112) -> np.ndarray:
    return np.full((h, w, 3), 250, dtype=np.uint8)


# ---------------------------------------------------------------------------
# Shared assessor fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def assessor():
    return FaceQualityAssessor()


def _assess(assessor, image, confidence=0.92):
    return assessor.assess(
        image=image,
        candidate_id="cand-001",
        track_id="track-001",
        camera_id=1,
        timestamp=_ts(),
        frame_reference="cam1-frame-0001",
        face_bbox=_bbox(),
        face_detection_confidence=confidence,
        frame_width=1920,
        frame_height=1080,
    )


# ---------------------------------------------------------------------------
# Basic output structure
# ---------------------------------------------------------------------------


class TestOutputStructure:

    def test_result_has_all_fields(self, assessor):
        result = _assess(assessor, _sharp_face())
        assert hasattr(result, "candidate_id")
        assert hasattr(result, "quality_score")
        assert hasattr(result, "quality_status")
        assert hasattr(result, "is_match_ready")
        assert hasattr(result, "rejection_reason")
        assert hasattr(result, "reason")

    def test_quality_score_in_range(self, assessor):
        result = _assess(assessor, _sharp_face())
        assert 0.0 <= result.quality_score <= 1.0

    def test_component_scores_in_range(self, assessor):
        result = _assess(assessor, _sharp_face())
        for attr in ("sharpness_score", "brightness_score", "contrast_score",
                     "face_size_score", "pose_score", "occlusion_score"):
            val = getattr(result, attr)
            assert 0.0 <= val <= 1.0, f"{attr}={val} out of range"

    def test_candidate_id_preserved(self, assessor):
        result = _assess(assessor, _sharp_face())
        assert result.candidate_id == "cand-001"

    def test_track_id_preserved(self, assessor):
        result = _assess(assessor, _sharp_face())
        assert result.track_id == "track-001"


# ---------------------------------------------------------------------------
# AI Safety Invariant Tests
# ---------------------------------------------------------------------------


class TestSafetyInvariants:

    def test_result_has_no_identity_label(self, assessor):
        """Quality result must NOT expose any identity decision field."""
        result = _assess(assessor, _sharp_face())
        for forbidden in ("identity", "person_id", "match_confidence",
                          "recognition_score", "biometric_score"):
            assert not hasattr(result, forbidden), (
                f"Safety violation: FaceQualityResult has forbidden attribute '{forbidden}'"
            )

    def test_quality_score_is_not_identity_probability(self, assessor):
        """quality_score should stay below 1.0 and never equal confidence."""
        result = _assess(assessor, _sharp_face(), confidence=0.99)
        # Should never trivially equal 0.99 (would imply passthrough of confidence as score)
        assert result.quality_score != pytest.approx(0.99, abs=0.005), (
            "quality_score appears to be a passthrough of detection_confidence — "
            "this violates the safety invariant."
        )


# ---------------------------------------------------------------------------
# Per-defect rejection tests
# ---------------------------------------------------------------------------


class TestRejectionPaths:

    def test_tiny_face_rejected_too_small(self, assessor):
        result = _assess(assessor, _tiny_face(20, 20))
        assert result.is_match_ready is False
        assert result.rejection_reason == RejectionReason.FACE_TOO_SMALL
        assert result.quality_status in (QualityClassification.POOR, QualityClassification.INVALID)

    def test_blurry_face_rejected(self, assessor):
        result = _assess(assessor, _blurry_face())
        # Heavily blurred images should be rejected — either blur or size
        assert result.is_match_ready is False
        assert result.rejection_reason in (
            RejectionReason.EXCESSIVE_BLUR,
            RejectionReason.FACE_TOO_SMALL,
            RejectionReason.LOW_CONTRAST,  # flat blurry image can also be low contrast
        )

    def test_dark_face_rejected(self, assessor):
        result = _assess(assessor, _dark_face())
        assert result.is_match_ready is False
        # Uniform dark image has zero variance → detected as blur before lighting check
        assert result.rejection_reason in (
            RejectionReason.INSUFFICIENT_LIGHT,
            RejectionReason.LOW_CONTRAST,
            RejectionReason.EXCESSIVE_BLUR,  # uniform dark = zero sharpness variance
        )

    def test_overexposed_face_rejected(self, assessor):
        result = _assess(assessor, _bright_face())
        assert result.is_match_ready is False
        # Uniform bright image has zero variance → detected as blur before overexposure check
        assert result.rejection_reason in (
            RejectionReason.OVEREXPOSED,
            RejectionReason.LOW_CONTRAST,
            RejectionReason.EXCESSIVE_BLUR,  # uniform white = zero sharpness variance
        )

    def test_invalid_none_image(self, assessor):
        result = _assess(assessor, None)
        assert result.quality_status == QualityClassification.INVALID
        assert result.is_match_ready is False
        assert result.rejection_reason == RejectionReason.INVALID_IMAGE

    def test_invalid_empty_array(self, assessor):
        result = _assess(assessor, np.zeros((0, 0, 3), dtype=np.uint8))
        assert result.quality_status == QualityClassification.INVALID
        assert result.is_match_ready is False

    def test_low_detection_confidence(self, assessor):
        # Confidence well below 0.50 should be rejected
        result = _assess(assessor, _sharp_face(), confidence=0.30)
        assert result.is_match_ready is False


# ---------------------------------------------------------------------------
# Good face path
# ---------------------------------------------------------------------------


class TestGoodFacePath:

    def test_sharp_face_has_positive_score(self, assessor):
        result = _assess(assessor, _sharp_face())
        assert result.quality_score > 0.0

    def test_classification_is_valid_enum(self, assessor):
        result = _assess(assessor, _sharp_face())
        assert isinstance(result.quality_status, QualityClassification)

    def test_reason_is_nonempty_string(self, assessor):
        result = _assess(assessor, _sharp_face())
        assert isinstance(result.reason, str) and len(result.reason) > 0


# ---------------------------------------------------------------------------
# Score normalization
# ---------------------------------------------------------------------------


class TestScoreNormalization:

    def test_scores_never_exceed_one(self, assessor):
        """No individual component score should ever exceed 1.0."""
        for image in [_sharp_face(), _blurry_face(), _dark_face(), _bright_face()]:
            result = _assess(assessor, image)
            for attr in ("quality_score", "sharpness_score", "brightness_score",
                         "contrast_score", "face_size_score", "pose_score"):
                val = getattr(result, attr)
                assert val <= 1.0, f"{attr}={val} exceeds 1.0 for image type"

    def test_occlusion_score_never_exceeds_one(self, assessor):
        for image in [_sharp_face(), _blurry_face()]:
            result = _assess(assessor, image)
            assert result.occlusion_score <= 1.0

    def test_scores_never_below_zero(self, assessor):
        for image in [_sharp_face(), _dark_face()]:
            result = _assess(assessor, image)
            for attr in ("quality_score", "sharpness_score", "brightness_score",
                         "contrast_score", "face_size_score", "pose_score", "occlusion_score"):
                val = getattr(result, attr)
                assert val >= 0.0, f"{attr}={val} below 0.0"


# ---------------------------------------------------------------------------
# Failure resilience
# ---------------------------------------------------------------------------


class TestFailureResilience:

    def test_random_noise_does_not_raise(self, assessor):
        rng = np.random.default_rng(99)
        for _ in range(5):
            noise = rng.integers(0, 255, (64, 64, 3), dtype=np.uint8)
            result = _assess(assessor, noise)
            assert hasattr(result, "quality_score")

    def test_grayscale_image_handled(self, assessor):
        """Some cameras produce single-channel images. Should not crash."""
        gray = np.full((100, 100), 128, dtype=np.uint8)
        # Should not raise, may come back INVALID but should not throw
        try:
            result = _assess(assessor, gray)
            assert hasattr(result, "is_match_ready")
        except Exception as exc:
            pytest.fail(f"Assessor raised unexpected exception on grayscale input: {exc}")
