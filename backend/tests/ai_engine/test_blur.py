"""
Tests for Module 6 – Blur / Sharpness Analyzer
================================================
Validates Laplacian variance measurement, blur detection, score normalization,
and threshold configuration.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.ai_engine.quality.blur_analyzer import BlurAnalyzer


@pytest.fixture
def sharp_face_crop() -> np.ndarray:
    """Create a high-contrast synthetic image with sharp edges and rich textures."""
    img = np.zeros((120, 120, 3), dtype=np.uint8)
    img[::4, ::4] = (255, 255, 255)
    img[1::4, 1::4] = (50, 180, 220)
    # Draw high-contrast facial feature representations
    cv2.circle(img, (40, 40), 12, (20, 20, 20), -1)
    cv2.circle(img, (80, 40), 12, (20, 20, 20), -1)
    cv2.line(img, (60, 50), (60, 75), (0, 0, 0), 3)
    cv2.ellipse(img, (60, 95), (25, 10), 0, 0, 180, (0, 0, 0), 3)
    return img


@pytest.fixture
def blurred_face_crop(sharp_face_crop: np.ndarray) -> np.ndarray:
    """Apply severe Gaussian blur to simulate camera motion or defocus."""
    return cv2.GaussianBlur(sharp_face_crop, (25, 25), 10.0)


class TestBlurAnalyzer:

    def test_sharp_image_passes(self, sharp_face_crop: np.ndarray):
        analyzer = BlurAnalyzer(min_sharpness=50.0, optimal_sharpness=200.0)
        res = analyzer.analyze(sharp_face_crop)
        assert res.is_sharp is True
        assert res.is_excessive_blur is False
        assert res.sharpness_raw > 50.0
        assert res.sharpness_score > 0.50

    def test_severely_blurred_image_fails(self, blurred_face_crop: np.ndarray):
        analyzer = BlurAnalyzer(min_sharpness=60.0)
        res = analyzer.analyze(blurred_face_crop)
        assert res.is_sharp is False
        assert res.is_excessive_blur is True
        assert res.sharpness_raw < 60.0
        assert res.sharpness_score < 0.35

    def test_empty_or_none_image_handling(self):
        analyzer = BlurAnalyzer()
        res_none = analyzer.analyze(None)  # type: ignore
        assert res_none.is_sharp is False
        assert res_none.is_excessive_blur is True
        assert res_none.sharpness_raw == 0.0

        empty_img = np.zeros((0, 0, 3), dtype=np.uint8)
        res_empty = analyzer.analyze(empty_img)
        assert res_empty.is_sharp is False

    def test_configurable_threshold_override(self, sharp_face_crop: np.ndarray):
        # Setting an unattainable threshold should flag even sharp images as blurred.
        # The synthetic grid fixture produces a raw sharpness > 100,000, so we use
        # a sufficiently high threshold to guarantee the flag regardless of image content.
        strict_analyzer = BlurAnalyzer(min_sharpness=10_000_000.0)
        res = strict_analyzer.analyze(sharp_face_crop)
        assert res.is_sharp is False
        assert res.is_excessive_blur is True
