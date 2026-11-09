"""
Module 7 – Decision Thresholds & Calibration Manager
=====================================================
Evaluates candidate similarity scores against configured policy cutoffs
and manages future-ready empirical probability calibration.

AI Safety Invariants (Sections 11 & 12):
----------------------------------------
- Zero Automated Identity Confirmation:
  Under NO circumstances does this module produce an 'IDENTITY_CONFIRMED' state.
- Raw similarity is an algorithmic ranking signal, NOT an identity probability.
- If calibration is unvalidated, calibration_status is explicitly 'NOT_CALIBRATED'.
"""

from __future__ import annotations

import logging
from typing import Tuple

import numpy as np

from app.ai_engine.config.matching_settings import matching_settings
from app.ai_engine.schemas.matching import (
    CalibrationStatus,
    MatchDecisionState,
)

logger = logging.getLogger(__name__)


class ThresholdManager:
    """
    Evaluates similarity scores against configured policy thresholds
    and optionally executes confidence calibration models.
    """

    def __init__(
        self,
        review_threshold: float | None = None,
        high_priority_threshold: float | None = None,
        low_similarity_cutoff: float | None = None,
        calibration_enabled: bool | None = None,
    ) -> None:
        self.review_threshold = (
            review_threshold
            if review_threshold is not None
            else matching_settings.REVIEW_THRESHOLD
        )
        self.high_priority_threshold = (
            high_priority_threshold
            if high_priority_threshold is not None
            else matching_settings.HIGH_PRIORITY_THRESHOLD
        )
        self.low_cutoff = (
            low_similarity_cutoff
            if low_similarity_cutoff is not None
            else matching_settings.LOW_SIMILARITY_CUTOFF
        )
        self.calibration_enabled = (
            calibration_enabled
            if calibration_enabled is not None
            else matching_settings.CALIBRATION_ENABLED
        )

    def evaluate_decision_state(self, similarity_score: float) -> MatchDecisionState:
        """
        Classifies similarity score into standardized decision states:
        - HIGH_PRIORITY_REVIEW: >= high_priority_threshold (default 0.85)
        - POSSIBLE_MATCH: >= review_threshold (default 0.70)
        - LOW_SIMILARITY: >= low_cutoff (default 0.40)
        - NO_CANDIDATE: < low_cutoff (default 0.40)
        """
        if similarity_score >= self.high_priority_threshold:
            return MatchDecisionState.HIGH_PRIORITY_REVIEW
        elif similarity_score >= self.review_threshold:
            return MatchDecisionState.POSSIBLE_MATCH
        elif similarity_score >= self.low_cutoff:
            return MatchDecisionState.LOW_SIMILARITY
        else:
            return MatchDecisionState.NO_CANDIDATE

    def calibrate_score(self, similarity_score: float) -> float:
        """
        Applies empirical calibration model (e.g. Platt logistic scaling)
        to map raw vector similarity into a calibrated score.
        """
        # Logistic sigmoid: 1 / (1 + exp(-(slope * x + intercept)))
        slope = matching_settings.CALIBRATION_SLOPE
        intercept = matching_settings.CALIBRATION_INTERCEPT
        z = (slope * similarity_score) + intercept
        # Bounded sigmoid
        sig = 1.0 / (1.0 + np.exp(-z))
        return round(float(sig), 4)

    def evaluate_candidate(
        self, similarity_score: float
    ) -> Tuple[MatchDecisionState, float | None, CalibrationStatus]:
        """
        Full evaluation returning:
        (decision_state, calibrated_score_or_none, calibration_status)
        """
        state = self.evaluate_decision_state(similarity_score)

        if self.calibration_enabled:
            cal_score = self.calibrate_score(similarity_score)
            cal_status = CalibrationStatus.CALIBRATED
        else:
            cal_score = None
            cal_status = CalibrationStatus.NOT_CALIBRATED

        return state, cal_score, cal_status


# Module-level singleton
threshold_manager = ThresholdManager()
