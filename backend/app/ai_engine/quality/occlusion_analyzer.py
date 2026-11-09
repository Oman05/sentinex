"""
Module 6 – Occlusion Analyzer
===============================
Estimates visual obstruction across critical facial regions (eyes, nose, mouth)
caused by masks, sunglasses, edge clipping, or objects.
"""

from __future__ import annotations

from dataclasses import dataclass
import cv2
import numpy as np

from app.ai_engine.config.quality_settings import quality_settings
from app.ai_engine.schemas.quality import OcclusionLevel


@dataclass(frozen=True)
class OcclusionAnalysisResult:
    """Outcome of occlusion evaluation."""
    occlusion_score: float
    occlusion_level: OcclusionLevel
    is_acceptable_occlusion: bool
    affected_regions: list[str]


class OcclusionAnalyzer:
    """
    Evaluates obstruction of primary facial landmarks and features.
    Computes a continuous occlusion score [0.0, 1.0] and categorical level.
    """

    def __init__(self, max_occlusion: float | None = None) -> None:
        self.max_occlusion = (
            max_occlusion
            if max_occlusion is not None
            else quality_settings.MAX_OCCLUSION_SCORE
        )

    def analyze(self, face_bgr: np.ndarray) -> OcclusionAnalysisResult:
        """
        Evaluate facial obstruction on a BGR face crop.
        """
        if face_bgr is None or face_bgr.size == 0:
            return OcclusionAnalysisResult(
                occlusion_score=1.0,
                occlusion_level=OcclusionLevel.SEVERE,
                is_acceptable_occlusion=False,
                affected_regions=["entire_frame"],
            )

        h, w = face_bgr.shape[:2]
        if h < 10 or w < 10:
            return OcclusionAnalysisResult(
                occlusion_score=0.8,
                occlusion_level=OcclusionLevel.SEVERE,
                is_acceptable_occlusion=False,
                affected_regions=["resolution_truncated"],
            )

        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY) if face_bgr.ndim == 3 else face_bgr

        # Segment into three anatomical regions
        # 1. Upper band (eyes / forehead): 0% to 35%
        # 2. Mid band (nose / cheeks): 35% to 65%
        # 3. Lower band (mouth / chin): 65% to 100%
        h_upper = int(h * 0.35)
        h_mid = int(h * 0.65)

        upper_band = gray[:h_upper, :]
        mid_band = gray[h_upper:h_mid, :]
        lower_band = gray[h_mid:, :]

        affected: list[str] = []
        occlusion_penalties = 0.0

        # Feature 1: Texture homogeneity check (e.g. surgical mask covering lower band)
        # Natural faces have textured features (mouth, lips, nose, eyes); flat uniform color indicates covering
        for name, band in [("eyes", upper_band), ("nose", mid_band), ("mouth", lower_band)]:
            if band.size > 0:
                band_std = float(np.std(band))
                # Very flat variance indicates uniform patch/mask or blocked sensor
                if band_std < 8.0:
                    affected.append(f"{name}_uniform_patch")
                    occlusion_penalties += 0.35
                elif band_std < 14.0:
                    affected.append(f"{name}_low_detail")
                    occlusion_penalties += 0.15

        # Feature 2: Dark obstruction check (e.g. solid dark sunglasses in upper band)
        if upper_band.size > 0:
            upper_mean = float(np.mean(upper_band))
            mid_mean = float(np.mean(mid_band)) if mid_band.size > 0 else upper_mean
            # Extreme brightness disparity between eye region and face indicates dark sunglasses
            if upper_mean < 25.0 and mid_mean > 60.0:
                affected.append("sunglasses_detected")
                occlusion_penalties += 0.40

        # Feature 3: Image boundary truncation (person partially outside frame)
        # Check border intensity variance
        border_pixels = np.concatenate([
            gray[0, :], gray[-1, :], gray[:, 0], gray[:, -1]
        ])
        if float(np.std(border_pixels)) < 5.0 and float(np.mean(border_pixels)) < 15.0:
            affected.append("boundary_clipped")
            occlusion_penalties += 0.20

        # Normalized occlusion score [0.0, 1.0]
        final_score = float(np.clip(occlusion_penalties, 0.0, 1.0))

        if final_score < 0.20:
            level = OcclusionLevel.CLEAR
        elif final_score <= self.max_occlusion:
            level = OcclusionLevel.PARTIAL
        else:
            level = OcclusionLevel.SEVERE

        is_acceptable = final_score < self.max_occlusion

        return OcclusionAnalysisResult(
            occlusion_score=round(final_score, 4),
            occlusion_level=level,
            is_acceptable_occlusion=is_acceptable,
            affected_regions=affected,
        )
