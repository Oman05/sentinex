"""Module 5 & 6 Schemas Package."""

from app.ai_engine.schemas.observations import (
    BoundingBox,
    CandidateObservation,
    FaceDetection,
    PersonDetection,
    ProcessingStatus,
    QualityStatus,
    TrackState,
    TrackStatus,
)
from app.ai_engine.schemas.quality import (
    ExposureStatus,
    FaceQualityMetrics,
    FaceQualityResult,
    MultiFrameAssessRequest,
    MultiFrameAssessResponse,
    OcclusionLevel,
    PoseClassification,
    QualityAssessRequest,
    QualityClassification,
    QualityTelemetryResponse,
    RejectionReason,
)

__all__ = [
    "BoundingBox",
    "CandidateObservation",
    "ExposureStatus",
    "FaceDetection",
    "FaceQualityMetrics",
    "FaceQualityResult",
    "MultiFrameAssessRequest",
    "MultiFrameAssessResponse",
    "OcclusionLevel",
    "PersonDetection",
    "PoseClassification",
    "ProcessingStatus",
    "QualityAssessRequest",
    "QualityClassification",
    "QualityStatus",
    "QualityTelemetryResponse",
    "RejectionReason",
    "TrackState",
    "TrackStatus",
]
