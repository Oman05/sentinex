"""
Module 6 – Blur / Sharpness Analyzer
=====================================
Evaluates the focus and edge sharpness of face crops using the Variance of
Laplacian and gradient magnitude metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
import cv2
import numpy as np

from app.ai_engine.config.quality_settings import quality_settings


@dataclass(frozen=True)
class BlurAnalysisResult:
    """Result of sharpness and blur analysis."""
    sharpness_raw: float
    sharpness_score: float
    is_sharp: bool
    is_excessive_blur: bool
    gradient_magnitude: float = 0.0


class BlurAnalyzer:
    """
    Stateless analyzer measuring facial focus and blur severity.
    Thresholds are fully configurable via FaceQualitySettings.
    """

    def __init__(
        self,
        min_sharpness: float | None = None,
        optimal_sharpness: float | None = None,
    ) -> None:
        self.min_sharpness = (
            min_sharpness
            if min_sharpness is not None
            else quality_settings.MIN_SHARPNESS_SCORE
        )
        self.optimal_sharpness = (
            optimal_sharpness
            if optimal_sharpness is not None
            else quality_settings.OPTIMAL_SHARPNESS_SCORE
        )

    def analyze(self, image_bgr: np.ndarray) -> BlurAnalysisResult:
        """
        Evaluate focus and blur on a BGR face crop.
        
        Returns:
            BlurAnalysisResult with raw variance, normalized score, and flags.
        """
        if image_bgr is None or image_bgr.size == 0:
            return BlurAnalysisResult(
                sharpness_raw=0.0,
                sharpness_score=0.0,
                is_sharp=False,
                is_excessive_blur=True,
            )

        # Convert to grayscale for gradient calculation
        if image_bgr.ndim == 3:
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        else:
            gray = image_bgr

        # Variance of Laplacian (high variance = sharp edges; low = blurry)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        raw_variance = float(laplacian.var())

        # Gradient-based sharpness measurement (Tenengrad operator via Sobel)
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient_mag = float(np.mean(sobel_x**2 + sobel_y**2))

        # Normalize score into [0.0, 1.0] using optimal threshold
        if self.optimal_sharpness <= 0:
            norm_score = 1.0 if raw_variance >= self.min_sharpness else 0.0
        else:
            # Smooth saturation scaling up to 1.0
            ratio = raw_variance / self.optimal_sharpness
            norm_score = float(np.clip(ratio, 0.0, 1.0))

        is_sharp = raw_variance >= self.min_sharpness
        is_excessive_blur = not is_sharp

        return BlurAnalysisResult(
            sharpness_raw=round(raw_variance, 2),
            sharpness_score=round(norm_score, 4),
            is_sharp=is_sharp,
            is_excessive_blur=is_excessive_blur,
            gradient_magnitude=round(gradient_mag, 2),
        )
