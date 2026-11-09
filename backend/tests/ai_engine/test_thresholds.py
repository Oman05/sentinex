"""
Tests for Module 7 – Decision Thresholds & Calibration
=======================================================
Verifies decision states (NO_CANDIDATE, LOW_SIMILARITY, POSSIBLE_MATCH,
HIGH_PRIORITY_REVIEW) and ensures IDENTITY_CONFIRMED is never outputted.
"""

from __future__ import annotations

import pytest

from app.ai_engine.matching.threshold_manager import ThresholdManager
from app.ai_engine.schemas.matching import (
    CalibrationStatus,
    MatchDecisionState,
)


@pytest.fixture
def manager():
    return ThresholdManager(
        review_threshold=0.70,
        high_priority_threshold=0.85,
        low_similarity_cutoff=0.40,
        calibration_enabled=False,
    )


class TestDecisionTiers:

    def test_high_priority_review(self, manager):
        assert manager.evaluate_decision_state(0.95) == MatchDecisionState.HIGH_PRIORITY_REVIEW
        assert manager.evaluate_decision_state(0.85) == MatchDecisionState.HIGH_PRIORITY_REVIEW

    def test_possible_match(self, manager):
        assert manager.evaluate_decision_state(0.84) == MatchDecisionState.POSSIBLE_MATCH
        assert manager.evaluate_decision_state(0.70) == MatchDecisionState.POSSIBLE_MATCH

    def test_low_similarity(self, manager):
        assert manager.evaluate_decision_state(0.69) == MatchDecisionState.LOW_SIMILARITY
        assert manager.evaluate_decision_state(0.40) == MatchDecisionState.LOW_SIMILARITY

    def test_no_candidate(self, manager):
        assert manager.evaluate_decision_state(0.39) == MatchDecisionState.NO_CANDIDATE
        assert manager.evaluate_decision_state(0.10) == MatchDecisionState.NO_CANDIDATE

    def test_never_declares_confirmed_identity(self, manager):
        # Even with perfect 1.0 similarity, state is HIGH_PRIORITY_REVIEW, never CONFIRMED
        state = manager.evaluate_decision_state(1.0)
        assert state != "IDENTITY_CONFIRMED"
        assert state == MatchDecisionState.HIGH_PRIORITY_REVIEW


class TestConfidenceCalibration:

    def test_uncalibrated_by_default(self, manager):
        state, cal_score, cal_status = manager.evaluate_candidate(0.80)
        assert state == MatchDecisionState.POSSIBLE_MATCH
        assert cal_score is None
        assert cal_status == CalibrationStatus.NOT_CALIBRATED

    def test_calibrated_when_enabled(self):
        cal_mgr = ThresholdManager(
            review_threshold=0.70,
            high_priority_threshold=0.85,
            calibration_enabled=True,
        )
        state, cal_score, cal_status = cal_mgr.evaluate_candidate(0.80)
        assert state == MatchDecisionState.POSSIBLE_MATCH
        assert cal_score is not None
        assert 0.0 <= cal_score <= 1.0
        assert cal_status == CalibrationStatus.CALIBRATED
