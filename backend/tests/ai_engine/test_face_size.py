"""
Tests for Module 6 – Face Size & Resolution Analyzer
======================================================
Validates absolute dimension thresholds, relative resolution against source
frame, and normalized resolution scoring.
"""

from __future__ import annotations

import pytest

from app.ai_engine.quality.face_size_analyzer import FaceSizeAnalyzer


class TestFaceSizeAnalyzer:

    def test_adequate_resolution_passes(self):
        analyzer = FaceSizeAnalyzer(min_width=40, min_height=40, optimal_size=112)
        res = analyzer.analyze(face_width=120, face_height=120, frame_width=1920, frame_height=1080)
        assert res.is_sufficient_size is True
        assert res.face_width == 120
        assert res.face_height == 120
        assert res.face_area == 14400
        assert res.relative_face_size > 0.005
        assert res.face_size_score >= 0.95

    def test_undersized_face_fails(self):
        analyzer = FaceSizeAnalyzer(min_width=40, min_height=40)
        res = analyzer.analyze(face_width=24, face_height=28)
        assert res.is_sufficient_size is False
        assert res.face_size_score <= 0.40

    def test_borderline_minimum_size(self):
        analyzer = FaceSizeAnalyzer(min_width=40, min_height=40)
        res = analyzer.analyze(face_width=40, face_height=40)
        assert res.is_sufficient_size is True
        assert res.face_size_score == pytest.approx(0.50, abs=0.05)
