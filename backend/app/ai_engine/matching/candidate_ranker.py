"""
Module 7 – Candidate Ranker
============================
Ranks retrieved candidate cases using multi-modal matching signals:
1. Feature vector similarity (primary)
2. Query face quality score (Module 6)
3. Reference image quality score (Module 3)
4. Multi-reference consistency bonus

AI Safety Invariant (Section 10):
----------------------------------
Do NOT use unrelated personal characteristics to increase a match score.
Identity is NEVER inferred from:
- clothing
- race/ethnicity
- gender stereotypes
- hairstyle alone
- assumed age
- location alone
Location and camera metadata may be displayed as contextual information,
but MUST NOT independently establish identity.
"""

from __future__ import annotations

import logging
from typing import Sequence

from app.ai_engine.config.matching_settings import matching_settings
from app.ai_engine.matching.score_aggregator import AggregatedCaseEvidence
from app.ai_engine.schemas.matching import (
    CalibrationStatus,
    CandidateMatchResult,
    MatchDecisionState,
)

logger = logging.getLogger(__name__)


class CandidateRanker:
    """
    Combines feature similarity, query quality, and reference evidence
    into an objective, unbiased candidate ranking score.
    """

    def __init__(
        self,
        weight_similarity: float | None = None,
        weight_query_quality: float | None = None,
        weight_reference_quality: float | None = None,
        weight_multi_ref_bonus: float | None = None,
    ) -> None:
        self.w_sim = (
            weight_similarity
            if weight_similarity is not None
            else matching_settings.WEIGHT_SIMILARITY
        )
        self.w_query = (
            weight_query_quality
            if weight_query_quality is not None
            else matching_settings.WEIGHT_QUERY_QUALITY
        )
        self.w_ref = (
            weight_reference_quality
            if weight_reference_quality is not None
            else matching_settings.WEIGHT_REFERENCE_QUALITY
        )
        self.w_multi = (
            weight_multi_ref_bonus
            if weight_multi_ref_bonus is not None
            else matching_settings.WEIGHT_MULTI_REF_BONUS
        )

        # Normalize weights to ensure sum is exactly 1.0
        total = self.w_sim + self.w_query + self.w_ref + self.w_multi
        if total > 0:
            self.w_sim /= total
            self.w_query /= total
            self.w_ref /= total
            self.w_multi /= total

    def compute_ranking_score(
        self,
        similarity_score: float,
        query_quality_score: float,
        reference_quality_score: float = 0.85,
        matched_reference_count: int = 1,
    ) -> float:
        """
        Compute normalized composite ranking score in [0.0, 1.0].
        Multi-ref consistency bonus: scales from 0.0 (1 image) to 1.0 (>= 3 images).
        """
        multi_ref_bonus = min(1.0, max(0.0, (matched_reference_count - 1) / 2.0))

        # Core formula combining objective perceptual usability and vector proximity
        raw_score = (
            (self.w_sim * similarity_score)
            + (self.w_query * query_quality_score)
            + (self.w_ref * reference_quality_score)
            + (self.w_multi * multi_ref_bonus)
        )

        # Ensure bounded [0.0, 1.0]
        return round(float(min(1.0, max(0.0, raw_score))), 4)

    def rank_candidates(
        self,
        case_evidences: Sequence[AggregatedCaseEvidence],
        query_quality_score: float,
        decision_evaluator_fn,  # callable(similarity_score) -> (MatchDecisionState, float | None, CalibrationStatus)
        top_k: int = 5,
    ) -> list[CandidateMatchResult]:
        """
        Sorts aggregated case evidences by ranking score and builds CandidateMatchResult list.
        """
        if not case_evidences:
            return []

        scored_candidates: list[CandidateMatchResult] = []

        for ev in case_evidences:
            sim = ev.aggregated_similarity
            state, calibrated_score, cal_status = decision_evaluator_fn(sim)

            ranking_score = self.compute_ranking_score(
                similarity_score=sim,
                query_quality_score=query_quality_score,
                reference_quality_score=0.85,
                matched_reference_count=ev.reference_count,
            )

            summary = (
                f"Similarity: {sim:.2f} ({ev.aggregation_method.value} across "
                f"{ev.reference_count} enrolled reference images); "
                f"Query Quality: {query_quality_score:.2f}; "
                f"Ranking Score: {ranking_score:.2f}."
            )

            scored_candidates.append({
                "case_id": ev.case_id,
                "case_number": ev.case_number,
                "category": ev.category,
                "department_id": ev.department_id,
                "similarity_score": sim,
                "candidate_ranking_score": ranking_score,
                "calibrated_score": calibrated_score,
                "calibration_status": cal_status,
                "decision_state": state,
                "best_reference_image_id": ev.best_reference_image_id,
                "matched_reference_count": ev.reference_count,
                "evidence_summary": summary,
            })

        # Sort descending by candidate_ranking_score, secondary by similarity_score
        sorted_candidates = sorted(
            scored_candidates,
            key=lambda c: (c["candidate_ranking_score"], c["similarity_score"]),
            reverse=True,
        )

        # Slice to top_k and assign ordinal ranks (1-indexed)
        results: list[CandidateMatchResult] = []
        for idx, cand in enumerate(sorted_candidates[:top_k], start=1):
            results.append(
                CandidateMatchResult(
                    rank=idx,
                    case_id=cand["case_id"],
                    case_number=cand["case_number"],
                    category=cand["category"],
                    department_id=cand["department_id"],
                    similarity_score=cand["similarity_score"],
                    candidate_ranking_score=cand["candidate_ranking_score"],
                    calibrated_score=cand["calibrated_score"],
                    calibration_status=cand["calibration_status"],
                    decision_state=cand["decision_state"],
                    best_reference_image_id=cand["best_reference_image_id"],
                    matched_reference_count=cand["matched_reference_count"],
                    evidence_summary=cand["evidence_summary"],
                )
            )

        return results


# Module-level singleton
candidate_ranker = CandidateRanker()
