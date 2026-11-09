"""
Tests for Module 6 – Lighting & Exposure Analyzer
==================================================
Validates luminance analysis, dynamic range, underexposure, overexposure,
and flat contrast detection.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.ai_engine.quality.lighting_analyzer import LightingAnalyzer
from app.ai_engine.schemas.quality import ExposureStatus


class TestLightingAnalyzer:

    def test_normal_lighting_passes(self):
        analyzer = LightingAnalyzer(min_brightness=40.0, max_brightness=220.0, min_contrast=20.0)
        # Synthetic face with balanced luminance and rich contrast
        normal_face = np.full((100, 100, 3), 130, dtype=np.uint8)
        normal_face[20:80, 20:80] = 70
        normal_face[40:60, 40:60] = 190

        res = analyzer.analyze(normal_face)
        assert res.exposure_status == ExposureStatus.NORMAL
        assert res.is_usable_lighting is True
        assert res.brightness_score > 0.60
        assert res.contrast_score > 0.50

    def test_underexposed_dark_face_fails(self):
        analyzer = LightingAnalyzer(min_brightness=40.0)
        # Extremely dark image (mean < 25)
        dark_face = np.full((100, 100, 3), 18, dtype=np.uint8)
        dark_face[40:60, 40:60] = 28

        res = analyzer.analyze(dark_face)
        assert res.exposure_status == ExposureStatus.UNDEREXPOSED
        assert res.is_usable_lighting is False
        assert res.brightness_raw < 40.0

    def test_overexposed_washed_out_face_fails(self):
        analyzer = LightingAnalyzer(max_brightness=220.0)
        # Saturated / washed-out image (mean > 230)
        bright_face = np.full((100, 100, 3), 245, dtype=np.uint8)
        bright_face[40:60, 40:60] = 255

        res = analyzer.analyze(bright_face)
        assert res.exposure_status == ExposureStatus.OVEREXPOSED
        assert res.is_usable_lighting is False
        assert res.brightness_raw > 220.0

    def test_low_contrast_flat_face_fails(self):
        analyzer = LightingAnalyzer(min_contrast=20.0)
        # Uniform grey patch: correct average brightness (128) but zero contrast
        flat_face = np.full((100, 100, 3), 128, dtype=np.uint8)

        res = analyzer.analyze(flat_face)
        assert res.exposure_status == ExposureStatus.LOW_CONTRAST
        assert res.is_usable_lighting is False
        assert res.contrast_raw < 5.0
