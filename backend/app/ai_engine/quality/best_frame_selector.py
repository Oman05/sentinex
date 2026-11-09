"""
Module 6 – Best-Frame Selector & Multi-Frame Analyzer
=======================================================
Aggregates multiple face observations across the lifecycle of a person track,
filters out sub-threshold/unusable observations, ranks usable observations by
image quality, and selects the optimal observation for downstream Module 7.
"""

from __future__ import annotations

from collections import deque
import logging
import threading
from typing import Sequence

from app.ai_engine.config.quality_settings import quality_settings
from app.ai_engine.schemas.quality import (
    FaceQualityResult,
    QualityClassification,
)

logger = logging.getLogger(__name__)


class BestFrameSelector:
    """
    Thread-safe multi-frame quality analyzer and best-observation selector.
    Maintains per-track sliding observation windows.
    """

    def __init__(self, max_history: int | None = None) -> None:
        self._max_history = (
            max_history
            if max_history is not None
            else quality_settings.MAX_TRACK_HISTORY_FRAMES
        )
        self._lock = threading.Lock()
        # track_id -> deque of FaceQualityResult
        self._track_history: dict[str, deque[FaceQualityResult]] = {}

    def select_best(
        self,
        observations: Sequence[FaceQualityResult],
    ) -> tuple[FaceQualityResult | None, list[FaceQualityResult], str]:
        """
        Filter, rank, and select the highest-quality usable observation from a list.

        Returns:
            (best_observation, ranked_usable_observations, reason_summary)
        """
        if not observations:
            return None, [], "No observations provided."

        # 1. Filter out invalid and non-match-ready observations
        usable = [
            obs for obs in observations
            if obs.quality_status != QualityClassification.INVALID and obs.is_match_ready
        ]

        if not usable:
            # Fall back to checking if there is at least an acceptable candidate
            usable = [
                obs for obs in observations
                if obs.quality_status not in (QualityClassification.INVALID, QualityClassification.POOR)
            ]

        if not usable:
            return (
                None,
                [],
                f"All {len(observations)} observation(s) rejected due to sub-threshold quality.",
            )

        # 2. Rank candidates primarily by quality_score descending,
        # followed by sharpness_score and resolution.
        ranked = sorted(
            usable,
            key=lambda o: (o.quality_score, o.sharpness_score, o.face_size_score),
            reverse=True,
        )

        best = ranked[0]
        reason = (
            f"Selected best observation (candidate_id={best.candidate_id}) with "
            f"quality_score={best.quality_score:.2f} ({best.quality_status.value}) "
            f"from {len(observations)} total candidate(s)."
        )

        return best, ranked, reason

    def register_observation(
        self, observation: FaceQualityResult
    ) -> tuple[bool, FaceQualityResult]:
        """
        Record an observation into its track's history.
        
        Returns:
            (is_new_best, current_best_for_track)
        """
        with self._lock:
            track_id = observation.track_id
            if track_id not in self._track_history:
                self._track_history[track_id] = deque(maxlen=self._max_history)

            history = self._track_history[track_id]

            # Determine previous best
            prev_best = None
            if history:
                prev_best = max(history, key=lambda o: o.quality_score)

            history.append(observation)

            # Determine current best
            curr_best = max(history, key=lambda o: o.quality_score)
            is_new_best = (
                prev_best is None
                or (curr_best.candidate_id == observation.candidate_id and curr_best.quality_score > prev_best.quality_score)
            )

            return is_new_best, curr_best

    def get_track_history(self, track_id: str) -> list[FaceQualityResult]:
        """Return all stored quality observations for a track."""
        with self._lock:
            history = self._track_history.get(track_id)
            if not history:
                return []
            return list(history)

    def clear_track(self, track_id: str) -> None:
        """Clear memory for a track that has expired or ended."""
        with self._lock:
            self._track_history.pop(track_id, None)

    def reset_all(self) -> None:
        """Clear all track buffers."""
        with self._lock:
            self._track_history.clear()


# Module-level singleton
best_frame_selector = BestFrameSelector()
