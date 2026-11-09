"""
Module 6 – Lighting & Exposure Analyzer
=========================================
Evaluates illumination, dynamic range, and contrast in face regions.
Detects underexposure, overexposure, and washed-out/flat contrast.
"""

from __future__ import annotations

from dataclasses import dataclass
import cv2
import numpy as np

from app.ai_engine.config.quality_settings import quality_settings
from app.ai_engine.schemas.quality import ExposureStatus


@dataclass(frozen=True)
class LightingAnalysisResult:
    """Detailed outcome of illumination and contrast analysis."""
    brightness_raw: float
    brightness_score: float
    contrast_raw: float
    contrast_score: float
    exposure_status: ExposureStatus
    is_usable_lighting: bool
    illumination_uniformity: float = 1.0


class LightingAnalyzer:
    """Stateless lighting and contrast evaluation for face crops."""

    def __init__(
        self,
        min_brightness: float | None = None,
        max_brightness: float | None = None,
        min_contrast: float | None = None,
        max_uneven_ratio: float | None = None,
    ) -> None:
        self.min_brightness = (
            min_brightness
            if min_brightness is not None
            else quality_settings.MIN_BRIGHTNESS_SCORE
        )
        self.max_brightness = (
            max_brightness
            if max_brightness is not None
            else quality_settings.MAX_BRIGHTNESS_SCORE
        )
        self.min_contrast = (
            min_contrast
            if min_contrast is not None
            else quality_settings.MIN_CONTRAST_SCORE
        )
        self.max_uneven_ratio = (
            max_uneven_ratio
            if max_uneven_ratio is not None
            else quality_settings.MAX_UNEVEN_ILLUMINATION_RATIO
        )

    def analyze(self, image_bgr: np.ndarray) -> LightingAnalysisResult:
        """
        Evaluate brightness, contrast, and illumination uniformity on a BGR face crop.
        """
        if image_bgr is None or image_bgr.size == 0:
            return LightingAnalysisResult(
                brightness_raw=0.0,
                brightness_score=0.0,
                contrast_raw=0.0,
                contrast_score=0.0,
                exposure_status=ExposureStatus.UNDEREXPOSED,
                is_usable_lighting=False,
                illumination_uniformity=0.0,
            )

        # Convert to grayscale / luminance
        if image_bgr.ndim == 3:
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        else:
            gray = image_bgr

        mean_val = float(np.mean(gray))
        std_val = float(np.std(gray))

        # Check bilateral illumination disparity (uneven side lighting)
        mid_x = gray.shape[1] // 2
        if mid_x > 0:
            left_mean = float(np.mean(gray[:, :mid_x]))
            right_mean = float(np.mean(gray[:, mid_x:]))
            disparity = abs(left_mean - right_mean)
        else:
            disparity = 0.0
        illum_uniformity = float(np.clip(1.0 - (disparity / 100.0), 0.0, 1.0))

        # Classify exposure status
        if mean_val < self.min_brightness:
            status = ExposureStatus.UNDEREXPOSED
        elif mean_val > self.max_brightness:
            status = ExposureStatus.OVEREXPOSED
        elif std_val < self.min_contrast:
            status = ExposureStatus.LOW_CONTRAST
        elif disparity > self.max_uneven_ratio:
            status = ExposureStatus.UNEVEN_ILLUMINATION
        else:
            status = ExposureStatus.NORMAL

        # Normalized brightness score: optimal luminance is ~128
        # Falls off smoothly towards 0 or 255
        diff_from_optimal = abs(mean_val - 128.0)
        norm_brightness = max(0.0, 1.0 - (diff_from_optimal / 128.0))

        # Penalize severely out-of-range brightness
        if mean_val < self.min_brightness:
            norm_brightness *= (mean_val / max(1.0, self.min_brightness))
        elif mean_val > self.max_brightness:
            overage = 255.0 - mean_val
            allowed_overage = max(1.0, 255.0 - self.max_brightness)
            norm_brightness *= max(0.0, overage / allowed_overage)

        norm_brightness = float(np.clip(norm_brightness, 0.0, 1.0))

        # Normalized contrast score (standard deviation up to benchmark ~60 is optimal)
        benchmark_contrast = 60.0
        norm_contrast = float(np.clip(std_val / benchmark_contrast, 0.0, 1.0))

        is_usable = (status == ExposureStatus.NORMAL)

        return LightingAnalysisResult(
            brightness_raw=round(mean_val, 2),
            brightness_score=round(norm_brightness, 4),
            contrast_raw=round(std_val, 2),
            contrast_score=round(norm_contrast, 4),
            exposure_status=status,
            is_usable_lighting=is_usable,
            illumination_uniformity=round(illum_uniformity, 4),
        )

    @staticmethod
    def generate_normalized_copy(image_bgr: np.ndarray) -> np.ndarray:
        """
        Generate an optional illumination-normalized processing copy of the face
        crop (e.g. using CLAHE on LAB luminance channel) without modifying the original.
        Per Section 5: Preserves the original observation and provides a normalized copy.
        """
        if image_bgr is None or image_bgr.size == 0:
            return image_bgr
        try:
            lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            cl = clahe.apply(l_channel)
            merged = cv2.merge((cl, a_channel, b_channel))
            return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
        except Exception:
            return image_bgr.copy()
