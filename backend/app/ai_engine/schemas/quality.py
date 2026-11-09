"""
Module 6 – Pydantic Schemas for Face Quality Assessment
=========================================================
Canonical data structures representing face quality evaluation results,
rejection criteria, multi-frame best-observation selection, and API payloads.

AI Safety Invariant:
    None of these schemas carry an identity label, case reference, or identity
    confidence score. The quality_score represents image usability and sensor
    quality, NOT the probability that a person matches a known record.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from app.ai_engine.schemas.observations import BoundingBox


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class QualityClassification(str, Enum):
    """Categorical quality tier based on composite quality score and defect checks."""

    EXCELLENT = "EXCELLENT"
    """Exceptional sharpness, frontal pose, even illumination."""

    GOOD = "GOOD"
    """High quality observation, fully suitable for reliable face recognition."""

    ACCEPTABLE = "ACCEPTABLE"
    """Adequate quality; satisfies minimum thresholds for downstream matching."""

    POOR = "POOR"
    """Sub-threshold observation; rejected from matching to prevent false positives."""

    INVALID = "INVALID"
    """Corrupted, unreadable, or missing face image."""


class PoseClassification(str, Enum):
    """Categorical orientation estimate of the face relative to the camera."""

    FRONTAL = "FRONTAL"
    """Near-direct facing (yaw/pitch within tight frontal bounds)."""

    SLIGHTLY_ANGLED = "SLIGHTLY_ANGLED"
    """Mild angle; usable for most modern face recognition models."""

    STRONGLY_ANGLED = "STRONGLY_ANGLED"
    """Profile or steep perspective; high risk of recognition error."""

    UNKNOWN = "UNKNOWN"
    """Landmarks insufficient to compute reliable pose angle."""


class ExposureStatus(str, Enum):
    """Illumination and contrast classification of the face region."""

    NORMAL = "NORMAL"
    UNDEREXPOSED = "UNDEREXPOSED"
    OVEREXPOSED = "OVEREXPOSED"
    LOW_CONTRAST = "LOW_CONTRAST"
    UNEVEN_ILLUMINATION = "UNEVEN_ILLUMINATION"


class OcclusionLevel(str, Enum):
    """Obstruction level of primary facial features."""

    CLEAR = "CLEAR"
    PARTIAL = "PARTIAL"
    SEVERE = "SEVERE"


class RejectionReason(str, Enum):
    """Standardized machine-readable explanation for why a face is not match-ready."""

    NONE = "NONE"
    FACE_TOO_SMALL = "FACE_TOO_SMALL"
    EXCESSIVE_BLUR = "EXCESSIVE_BLUR"
    INSUFFICIENT_LIGHT = "INSUFFICIENT_LIGHT"
    OVEREXPOSED = "OVEREXPOSED"
    LOW_CONTRAST = "LOW_CONTRAST"
    UNEVEN_ILLUMINATION = "UNEVEN_ILLUMINATION"
    SEVERE_POSE = "SEVERE_POSE"
    HIGH_OCCLUSION = "HIGH_OCCLUSION"
    INVALID_IMAGE = "INVALID_IMAGE"
    LOW_DETECTION_CONFIDENCE = "LOW_DETECTION_CONFIDENCE"


# ---------------------------------------------------------------------------
# Detailed Metrics Breakdown
# ---------------------------------------------------------------------------


class FaceQualityMetrics(BaseModel):
    """Granular technical metrics computed during face quality evaluation."""

    sharpness_raw: float = Field(
        ..., description="Raw Variance of Laplacian value."
    )
    sharpness_score: float = Field(
        ..., ge=0.0, le=1.0, description="Normalized sharpness score (0.0 to 1.0)."
    )

    brightness_raw: float = Field(
        ..., description="Mean luminance value (0.0 to 255.0)."
    )
    brightness_score: float = Field(
        ..., ge=0.0, le=1.0, description="Normalized illumination usability score."
    )

    contrast_raw: float = Field(
        ..., description="Standard deviation of luminance (RMS contrast)."
    )
    contrast_score: float = Field(
        ..., ge=0.0, le=1.0, description="Normalized contrast score."
    )
    exposure_status: ExposureStatus = Field(
        default=ExposureStatus.NORMAL, description="Exposure classification."
    )
    illumination_uniformity: Optional[float] = Field(
        default=1.0, ge=0.0, le=1.0, description="Uniformity ratio between facial halves (1.0 = perfectly even)."
    )
    gradient_magnitude: Optional[float] = Field(
        default=None, description="Mean Tenengrad/Sobel gradient magnitude for edge sharpness."
    )

    face_width: int = Field(..., ge=0, description="Face crop width in pixels.")
    face_height: int = Field(..., ge=0, description="Face crop height in pixels.")
    face_area: int = Field(..., ge=0, description="Pixel area of face bounding box.")
    relative_face_size: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Face area relative to source frame area."
    )
    face_size_score: float = Field(
        ..., ge=0.0, le=1.0, description="Normalized resolution score."
    )

    estimated_yaw: float = Field(default=0.0, description="Estimated yaw in degrees.")
    estimated_pitch: float = Field(default=0.0, description="Estimated pitch in degrees.")
    estimated_roll: float = Field(default=0.0, description="Estimated roll in degrees.")
    pose_classification: PoseClassification = Field(
        default=PoseClassification.UNKNOWN, description="Pose classification category."
    )
    pose_score: float = Field(
        ..., ge=0.0, le=1.0, description="Normalized pose suitability score (1.0 = frontal)."
    )

    occlusion_score: float = Field(
        ..., ge=0.0, le=1.0, description="Estimated occlusion level (0.0 = clear, 1.0 = obstructed)."
    )
    occlusion_level: OcclusionLevel = Field(
        default=OcclusionLevel.CLEAR, description="Categorical occlusion level."
    )

    detection_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Face detector confidence score from Module 5."
    )


# ---------------------------------------------------------------------------
# Standardized Face Quality Result (Module 6 Output)
# ---------------------------------------------------------------------------


class FaceQualityResult(BaseModel):
    """
    Standardized result contract for Face Quality Assessment.
    Communicates whether an observation is match-ready for Module 7.
    """

    assessment_id: str = Field(
        default_factory=lambda: f"FQR-{uuid4().hex[:12].upper()}",
        description="Unique identifier for this quality evaluation event.",
    )
    candidate_id: str = Field(..., description="Originating Module 5 candidate ID.")
    track_id: str = Field(..., description="Short-term person track ID.")
    camera_id: int = Field(..., description="Camera ID that captured the observation.")
    timestamp: datetime = Field(..., description="UTC frame capture timestamp.")

    # Core scores
    sharpness_score: float = Field(..., ge=0.0, le=1.0)
    brightness_score: float = Field(..., ge=0.0, le=1.0)
    contrast_score: float = Field(..., ge=0.0, le=1.0)
    face_size_score: float = Field(..., ge=0.0, le=1.0)
    pose_score: float = Field(..., ge=0.0, le=1.0)
    occlusion_score: float = Field(..., ge=0.0, le=1.0)
    detection_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Detector confidence score. NOT identity confidence.",
    )

    # Composite evaluation
    quality_score: float = Field(
        ..., ge=0.0, le=1.0, description="Normalized composite quality score."
    )
    quality_status: QualityClassification = Field(
        ..., description="Categorical quality tier (EXCELLENT, GOOD, ACCEPTABLE, POOR, INVALID)."
    )

    # Gating decision for downstream Module 7
    is_match_ready: bool = Field(
        ..., description="True if face meets all quality standards to proceed to candidate matching."
    )
    reason: str = Field(
        ..., description="Human-readable assessment rationale."
    )
    rejection_reason: RejectionReason = Field(
        default=RejectionReason.NONE,
        description="Machine-readable rejection cause if not match ready.",
    )

    # Provenance
    best_frame_reference: str = Field(
        ..., description="Opaque source frame reference string."
    )
    camera_location: Optional[str] = Field(default=None)
    department_id: Optional[int] = Field(default=None)
    metrics: Optional[FaceQualityMetrics] = Field(
        default=None, description="Detailed component breakdown."
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Evaluation timestamp."
    )


# ---------------------------------------------------------------------------
# API Request & Response Schemas
# ---------------------------------------------------------------------------


class QualityAssessRequest(BaseModel):
    """Payload for assessing face quality of a single candidate observation."""

    candidate_id: str = Field(..., description="Candidate ID from Module 5.")
    track_id: str = Field(..., description="Track ID.")
    camera_id: int = Field(..., description="Camera ID.")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    frame_reference: str = Field(..., description="Source frame reference.")
    face_bbox: BoundingBox = Field(..., description="Face bounding box.")
    face_detection_confidence: float = Field(
        default=0.90, ge=0.0, le=1.0, description="Detector confidence."
    )
    camera_location: Optional[str] = None
    department_id: Optional[int] = None
    face_image_reference: Optional[str] = Field(
        default=None, description="Optional image file path, URI, or storage reference."
    )
    face_image_base64: Optional[str] = Field(
        default=None, description="Optional base64 encoded face crop (JPEG/PNG)."
    )
    landmark_points: Optional[list[tuple[float, float]]] = Field(
        default=None, description="Optional 5-point facial landmarks."
    )
    frame_width: Optional[int] = Field(default=1920)
    frame_height: Optional[int] = Field(default=1080)


class MultiFrameAssessRequest(BaseModel):
    """Payload for multi-frame track evaluation and best-frame selection."""

    track_id: str = Field(..., description="Track identifier.")
    candidates: list[QualityAssessRequest] = Field(
        ..., min_length=1, description="List of candidate observations for this track."
    )


class MultiFrameAssessResponse(BaseModel):
    """Result of multi-frame quality ranking and best-frame selection."""

    track_id: str
    total_observations: int
    usable_observations: int
    rejected_observations: int
    best_observation: Optional[FaceQualityResult]
    ranked_candidates: list[FaceQualityResult]
    selection_reason: str


class QualityTelemetryResponse(BaseModel):
    """Operational and research telemetry metrics."""

    faces_received: int
    faces_assessed: int
    faces_rejected: int
    faces_passed: int
    pass_rate: float
    rejection_rate: float
    average_quality_score: float
    average_quality_processing_time: float = Field(
        default=0.0, description="Average quality processing time in seconds (Section 19)."
    )
    average_processing_latency_ms: float
    active_camera_count: int
    camera_telemetry: Optional[dict[str, Any]] = Field(
        default=None, description="Per-camera telemetry breakdown (Section 19)."
    )
    snapshot_at: str
