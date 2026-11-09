"""
Module 7 – Score & Evidence Aggregation
========================================
1. ReferenceScoreAggregator: Aggregates multiple reference image matches
   belonging to the same case (MAXIMUM, AVERAGE, TOP_N).
2. TrackTemporalEvidenceAggregator: Aggregates multi-frame observations
   from the same tracking sequence (BEST_OBSERVATION, AVERAGE, EXPONENTIAL_DECAY).

AI Safety Invariant:
--------------------
Temporal repetition reinforces candidate ranking evidence, but NEVER
bypasses human verification or converts into an automatic confirmed identity.
"""

from __future__ import annotations

import collections
import logging
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from app.ai_engine.config.matching_settings import matching_settings
from app.ai_engine.schemas.matching import (
    ReferenceAggregationMethod,
    TrackAggregationMethod,
)

logger = logging.getLogger(__name__)


@dataclass
class AggregatedCaseEvidence:
    """Summary of matching evidence across multiple reference images for a single case."""

    case_id: int
    case_number: str
    category: str
    department_id: int
    aggregated_similarity: float
    best_similarity: float
    best_reference_image_id: int | None
    reference_count: int
    aggregation_method: ReferenceAggregationMethod
    all_reference_scores: list[tuple[int, float]]  # (image_id, score)


class ReferenceScoreAggregator:
    """
    Aggregates similarity scores across multiple reference images enrolled for a single case.
    A case with 5 photos should evaluate all 5 photos and produce a unified case-level score.
    """

    def __init__(
        self,
        method: ReferenceAggregationMethod | str | None = None,
        top_n: int | None = None,
    ) -> None:
        self.method = (
            ReferenceAggregationMethod(method.upper())
            if isinstance(method, str)
            else (method or ReferenceAggregationMethod(matching_settings.REFERENCE_AGGREGATION_METHOD))
        )
        self.top_n = top_n or matching_settings.REFERENCE_TOP_N_COUNT

    def aggregate_case_references(
        self,
        case_id: int,
        case_number: str,
        category: str,
        department_id: int,
        reference_evaluations: Sequence[tuple[int, float]],  # list of (image_id, similarity_score)
        override_method: ReferenceAggregationMethod | None = None,
    ) -> AggregatedCaseEvidence:
        """
        Combine multiple reference similarity scores into a single case-level score.
        """
        if not reference_evaluations:
            return AggregatedCaseEvidence(
                case_id=case_id,
                case_number=case_number,
                category=category,
                department_id=department_id,
                aggregated_similarity=0.0,
                best_similarity=0.0,
                best_reference_image_id=None,
                reference_count=0,
                aggregation_method=self.method,
                all_reference_scores=[],
            )

        method = override_method or self.method

        # Sort descending by similarity
        sorted_refs = sorted(reference_evaluations, key=lambda x: x[1], reverse=True)
        scores = [score for _, score in sorted_refs]
        best_image_id, best_score = sorted_refs[0]

        if method == ReferenceAggregationMethod.MAXIMUM:
            agg_score = best_score
        elif method == ReferenceAggregationMethod.AVERAGE:
            agg_score = float(np.mean(scores))
        elif method == ReferenceAggregationMethod.TOP_N:
            top_k_scores = scores[: self.top_n]
            agg_score = float(np.mean(top_k_scores))
        else:
            agg_score = best_score

        return AggregatedCaseEvidence(
            case_id=case_id,
            case_number=case_number,
            category=category,
            department_id=department_id,
            aggregated_similarity=round(agg_score, 4),
            best_similarity=round(best_score, 4),
            best_reference_image_id=best_image_id,
            reference_count=len(reference_evaluations),
            aggregation_method=method,
            all_reference_scores=sorted_refs,
        )


class TrackTemporalEvidenceAggregator:
    """
    Maintains temporal track history across consecutive video frames (Module 5 track_id)
    to compute multi-frame smoothed similarity evidence without alert spamming.
    """

    def __init__(
        self,
        method: TrackAggregationMethod | str | None = None,
        max_history: int | None = None,
        decay_factor: float = 0.35,
    ) -> None:
        self.method = (
            TrackAggregationMethod(method.upper())
            if isinstance(method, str)
            else (method or TrackAggregationMethod(matching_settings.TRACK_AGGREGATION_METHOD))
        )
        self.max_history = max_history or matching_settings.MAX_TRACK_OBSERVATIONS
        self.decay_factor = decay_factor

        # Structure: track_id -> case_id -> deque of scores
        self._track_history: dict[str, dict[int, collections.deque[float]]] = {}

    def register_observation(self, track_id: str, case_id: int, similarity_score: float) -> float:
        """
        Add an observation score to the track's temporal history and return the aggregated score.
        """
        if track_id not in self._track_history:
            self._track_history[track_id] = {}

        if case_id not in self._track_history[track_id]:
            self._track_history[track_id][case_id] = collections.deque(maxlen=self.max_history)

        q = self._track_history[track_id][case_id]
        q.append(similarity_score)

        return self.get_aggregated_score(track_id, case_id)

    def get_aggregated_score(self, track_id: str, case_id: int) -> float:
        """Compute the track-level aggregated score for a case."""
        if track_id not in self._track_history or case_id not in self._track_history[track_id]:
            return 0.0

        q = self._track_history[track_id][case_id]
        if not q:
            return 0.0

        scores = list(q)
        if self.method == TrackAggregationMethod.BEST_OBSERVATION:
            return round(max(scores), 4)
        elif self.method == TrackAggregationMethod.AVERAGE:
            return round(float(np.mean(scores)), 4)
        elif self.method == TrackAggregationMethod.EXPONENTIAL_DECAY:
            # Weighted average giving exponentially higher weight to recent frames
            weights = np.exp(np.linspace(-self.decay_factor * (len(scores) - 1), 0, len(scores)))
            weighted_mean = float(np.average(scores, weights=weights))
            return round(weighted_mean, 4)
        else:
            return round(max(scores), 4)

    def get_observation_count(self, track_id: str, case_id: int) -> int:
        """Returns the number of frames evaluated for this track and case."""
        if track_id in self._track_history and case_id in self._track_history[track_id]:
            return len(self._track_history[track_id][case_id])
        return 0

    def clear_track(self, track_id: str) -> None:
        """Remove track history when track expires or leaves camera view."""
        self._track_history.pop(track_id, None)

    def reset_all(self) -> None:
        """Clear all active track histories."""
        self._track_history.clear()


# Module-level singletons
reference_score_aggregator = ReferenceScoreAggregator()
track_evidence_aggregator = TrackTemporalEvidenceAggregator()
