"""
Tests for Module 6 – PoseEstimator
====================================
Validates yaw/pitch/roll estimation from 5-point landmarks and the
symmetry-based fallback when landmarks are absent.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.ai_engine.quality.pose_estimator import PoseEstimator
from app.ai_engine.schemas.quality import PoseClassification


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def estimator():
    return PoseEstimator(max_yaw=30.0, max_pitch=25.0, max_roll=20.0)


def _frontal_landmarks():
    """Symmetric 5-point landmark set for a perfectly frontal face."""
    return [
        (30.0, 20.0),   # left_eye
        (70.0, 20.0),   # right_eye
        (50.0, 45.0),   # nose (centred)
        (35.0, 65.0),   # left_mouth
        (65.0, 65.0),   # right_mouth
    ]


def _angled_landmarks():
    """Asymmetric landmark set simulating a yaw-rotated face (nose shifted right)."""
    return [
        (30.0, 20.0),   # left_eye
        (70.0, 20.0),   # right_eye
        (68.0, 45.0),   # nose shifted far right → large yaw
        (35.0, 65.0),   # left_mouth
        (65.0, 65.0),   # right_mouth
    ]


def _small_face():
    """100x100 mostly-uniform BGR image simulating a symmetric frontal crop."""
    img = np.full((100, 100, 3), 128, dtype=np.uint8)
    return img


def _asymmetric_face():
    """BGR crop with extreme left-right luminance asymmetry."""
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:, :50] = 200   # left half bright
    img[:, 50:] = 20    # right half dark
    return img


# ---------------------------------------------------------------------------
# Landmark-based estimation
# ---------------------------------------------------------------------------


class TestLandmarkPoseEstimation:

    def test_frontal_landmarks_classified_frontal_or_slightly_angled(self, estimator):
        result = estimator.estimate(landmarks=_frontal_landmarks())
        assert result.classification in (
            PoseClassification.FRONTAL,
            PoseClassification.SLIGHTLY_ANGLED,
        )
        assert result.is_acceptable_pose is True
        assert 0.0 <= result.pose_score <= 1.0

    def test_frontal_landmarks_angles_near_zero(self, estimator):
        result = estimator.estimate(landmarks=_frontal_landmarks())
        assert abs(result.roll) < 5.0, f"Expected near-zero roll, got {result.roll}"

    def test_angled_landmarks_exceed_yaw_threshold(self, estimator):
        result = estimator.estimate(landmarks=_angled_landmarks())
        # The nose is shifted dramatically — should yield large yaw
        assert abs(result.yaw) > 10.0, f"Expected significant yaw, got {result.yaw}"

    def test_angled_landmarks_classified_strongly_angled(self, estimator):
        result = estimator.estimate(landmarks=_angled_landmarks())
        # Large yaw should push classification out of frontal
        assert result.classification in (
            PoseClassification.SLIGHTLY_ANGLED,
            PoseClassification.STRONGLY_ANGLED,
        )

    def test_pose_score_range(self, estimator):
        for lm in [_frontal_landmarks(), _angled_landmarks()]:
            result = estimator.estimate(landmarks=lm)
            assert 0.0 <= result.pose_score <= 1.0, f"Out-of-range pose_score: {result.pose_score}"

    def test_max_angle_equals_max_of_abs_angles(self, estimator):
        result = estimator.estimate(landmarks=_frontal_landmarks())
        expected = max(abs(result.yaw), abs(result.pitch), abs(result.roll))
        assert abs(result.max_angle - expected) < 1e-3


# ---------------------------------------------------------------------------
# Symmetry fallback (no landmarks)
# ---------------------------------------------------------------------------


class TestSymmetryFallbackEstimation:

    def test_symmetric_face_returns_acceptable_pose(self, estimator):
        result = estimator.estimate(face_crop=_small_face())
        assert result.is_acceptable_pose is True
        assert result.classification != PoseClassification.UNKNOWN

    def test_asymmetric_face_higher_yaw_than_symmetric(self, estimator):
        sym = estimator.estimate(face_crop=_small_face())
        asym = estimator.estimate(face_crop=_asymmetric_face())
        # Asymmetric should generate a larger inferred yaw
        assert asym.yaw >= sym.yaw

    def test_no_inputs_returns_unknown(self, estimator):
        result = estimator.estimate(landmarks=None, face_crop=None)
        assert result.classification == PoseClassification.UNKNOWN
        assert result.is_acceptable_pose is True  # Unknown defaults to neutral pass
        assert result.pose_score == pytest.approx(0.75)

    def test_empty_image_returns_unknown(self, estimator):
        empty = np.zeros((0, 0, 3), dtype=np.uint8)
        result = estimator.estimate(face_crop=empty)
        assert result.classification == PoseClassification.UNKNOWN


# ---------------------------------------------------------------------------
# Strict threshold config
# ---------------------------------------------------------------------------


class TestStrictThresholds:

    def test_strict_thresholds_reject_slightly_angled(self):
        strict = PoseEstimator(max_yaw=5.0, max_pitch=5.0, max_roll=5.0)
        result = strict.estimate(landmarks=_angled_landmarks())
        # Even "slightly angled" should exceed 5 degrees and be rejected
        if result.max_angle > 5.0:
            assert result.is_acceptable_pose is False

    def test_permissive_thresholds_accept_angled(self):
        permissive = PoseEstimator(max_yaw=89.0, max_pitch=89.0, max_roll=89.0)
        result = permissive.estimate(landmarks=_angled_landmarks())
        assert result.is_acceptable_pose is True
