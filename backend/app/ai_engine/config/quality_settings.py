"""
Module 6 – Face Quality Assessment Configuration
==================================================
All thresholds, score weights, cutoffs, and device selection for face quality
assessment are driven by environment variables so they can be tuned per CCTV
environment without modifying source code.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class FaceQualitySettings(BaseSettings):
    """Configuration settings and configurable thresholds for face quality evaluation."""

    # -------------------------------------------------------------------------
    # Face Resolution & Size Thresholds
    # -------------------------------------------------------------------------
    MIN_FACE_WIDTH: int = 40
    """Minimum face bounding box width in pixels."""

    MIN_FACE_HEIGHT: int = 40
    """Minimum face bounding box height in pixels."""

    OPTIMAL_FACE_SIZE: int = 112
    """Benchmark face dimension (width/height) considered optimal (score=1.0)."""

    # -------------------------------------------------------------------------
    # Sharpness / Blur Thresholds
    # -------------------------------------------------------------------------
    MIN_SHARPNESS_SCORE: float = 60.0
    """Variance of Laplacian below which a face is flagged as EXCESSIVE_BLUR."""

    OPTIMAL_SHARPNESS_SCORE: float = 250.0
    """Variance of Laplacian considered sharp/optimal (sharpness_score=1.0)."""

    # -------------------------------------------------------------------------
    # Lighting & Exposure Thresholds
    # -------------------------------------------------------------------------
    MIN_BRIGHTNESS_SCORE: float = 40.0
    """Mean pixel luminance below which face is flagged as INSUFFICIENT_LIGHT."""

    MAX_BRIGHTNESS_SCORE: float = 220.0
    """Mean pixel luminance above which face is flagged as OVEREXPOSED."""

    MAX_EXPOSURE_LEVEL: float = 220.0
    """Alias for maximum brightness/exposure level before flagging OVEREXPOSED."""

    MIN_CONTRAST_SCORE: float = 20.0
    """Pixel luminance standard deviation below which image is LOW_CONTRAST."""

    MAX_UNEVEN_ILLUMINATION_RATIO: float = 45.0
    """Luminance disparity between facial halves before flagging uneven illumination."""

    # -------------------------------------------------------------------------
    # Pose & Angle Limits (in degrees)
    # -------------------------------------------------------------------------
    MAX_POSE_YAW: float = 30.0
    """Maximum allowable estimated yaw angle in degrees before SEVERE_POSE flag."""

    MAX_POSE_PITCH: float = 25.0
    """Maximum allowable estimated pitch angle in degrees before SEVERE_POSE flag."""

    MAX_POSE_ROLL: float = 20.0
    """Maximum allowable estimated roll angle in degrees before SEVERE_POSE flag."""

    MAX_POSE_ANGLE: float = 30.0
    """General maximum allowable pose angle in degrees (alias for pose limits)."""

    # -------------------------------------------------------------------------
    # Occlusion Limits
    # -------------------------------------------------------------------------
    MAX_OCCLUSION_SCORE: float = 0.35
    """Maximum allowable occlusion ratio (0.0=none, 1.0=complete) before HIGH_OCCLUSION."""

    MAX_OCCLUSION_LEVEL: float = 0.35
    """Alias for maximum acceptable occlusion ratio."""

    # -------------------------------------------------------------------------
    # Quality Scoring & Classification Cutoffs
    # -------------------------------------------------------------------------
    MIN_QUALITY_SCORE: float = 0.55
    """Minimum composite quality score (0.0–1.0) required for is_match_ready=True."""

    EXCELLENT_THRESHOLD: float = 0.85
    """Composite score threshold for EXCELLENT classification."""

    GOOD_THRESHOLD: float = 0.70
    """Composite score threshold for GOOD classification."""

    ACCEPTABLE_THRESHOLD: float = 0.55
    """Composite score threshold for ACCEPTABLE classification."""

    # -------------------------------------------------------------------------
    # Scoring Component Weights (Must sum to 1.0)
    # -------------------------------------------------------------------------
    WEIGHT_SHARPNESS: float = 0.25
    WEIGHT_LIGHTING: float = 0.20
    WEIGHT_CONTRAST: float = 0.15
    WEIGHT_SIZE: float = 0.15
    WEIGHT_POSE: float = 0.15
    WEIGHT_OCCLUSION: float = 0.10

    # -------------------------------------------------------------------------
    # Persistence & Behavior Flags
    # -------------------------------------------------------------------------
    PERSIST_QUALITY_RESULTS: bool = True
    """Whether to write rows to the face_quality_results database table."""

    MAX_TRACK_HISTORY_FRAMES: int = 50
    """Maximum observations retained per track in the best-frame selector."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# Module-level singleton
quality_settings = FaceQualitySettings()
