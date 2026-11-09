"""
Module 6 – Face Size & Resolution Analyzer
===========================================
Measures facial dimensions (width, height, area) and relative resolution
against full-frame dimensions. Rejects faces smaller than configurable limits.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from app.ai_engine.config.quality_settings import quality_settings


@dataclass(frozen=True)
class FaceSizeAnalysisResult:
    """Outcome of face resolution and dimension analysis."""
    face_width: int
    face_height: int
    face_area: int
    relative_face_size: float
    face_size_score: float
    is_sufficient_size: bool


class FaceSizeAnalyzer:
    """Evaluates face crop dimensions against minimum and optimal benchmarks."""

    def __init__(
        self,
        min_width: int | None = None,
        min_height: int | None = None,
        optimal_size: int | None = None,
    ) -> None:
        self.min_width = (
            min_width if min_width is not None else quality_settings.MIN_FACE_WIDTH
        )
        self.min_height = (
            min_height if min_height is not None else quality_settings.MIN_FACE_HEIGHT
        )
        self.optimal_size = (
            optimal_size if optimal_size is not None else quality_settings.OPTIMAL_FACE_SIZE
        )

    def analyze(
        self,
        face_width: int,
        face_height: int,
        frame_width: int | None = None,
        frame_height: int | None = None,
    ) -> FaceSizeAnalysisResult:
        """
        Evaluate face dimensions.
        """
        w = max(0, int(face_width))
        h = max(0, int(face_height))
        area = w * h

        # Calculate relative face size if full frame dimensions available
        rel_size = 0.0
        if frame_width and frame_height and frame_width > 0 and frame_height > 0:
            rel_size = area / float(frame_width * frame_height)

        is_sufficient = (w >= self.min_width) and (h >= self.min_height)

        # Normalized resolution score
        # Benchmark dimension is min(w, h)
        min_dim = min(w, h)
        if not is_sufficient or min_dim <= 0:
            # Score proportional to fraction of min_width, capped at 0.4
            ratio = min_dim / max(1.0, float(self.min_width))
            norm_score = float(np.clip(ratio * 0.4, 0.0, 0.4))
        else:
            # Scaling from 0.5 at min dimension up to 1.0 at optimal_size
            span = max(1.0, float(self.optimal_size - self.min_width))
            above_min = max(0.0, float(min_dim - self.min_width))
            norm_score = 0.5 + 0.5 * min(1.0, above_min / span)

        return FaceSizeAnalysisResult(
            face_width=w,
            face_height=h,
            face_area=area,
            relative_face_size=round(rel_size, 6),
            face_size_score=round(norm_score, 4),
            is_sufficient_size=is_sufficient,
        )
