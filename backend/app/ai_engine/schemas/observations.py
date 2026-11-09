"""
Module 5 – Pydantic Schemas for AI Video Processing
=====================================================
These are the canonical data structures that travel between the sub-components
of the AI pipeline and are passed to downstream modules (Module 6 and Module 7).

Important design rule:
    None of these schemas carry an identity label, a case reference, or any
    field that could be interpreted as a positive identification. They are
    *candidate observations* only.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class QualityStatus(str, Enum):
    """
    Coarse quality assessment produced by Module 5.
    A fine-grained quality score is assigned by Module 6.
    """

    PENDING = "PENDING"
    """Quality not yet assessed (default when leaving Module 5)."""

    ACCEPTABLE = "ACCEPTABLE"
    """Basic quality checks passed; may proceed to Module 6."""

    POOR = "POOR"
    """Frame quality too low for reliable face recognition; flagged but not discarded."""

    UNUSABLE = "UNUSABLE"
    """Frame is unsuitable for matching (e.g., face occluded, extreme blur)."""


class ProcessingStatus(str, Enum):
    """Lifecycle state of a candidate observation through the pipeline."""

    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    PREPROCESSING = "PREPROCESSING"
    DETECTING = "DETECTING"
    TRACKING = "TRACKING"
    PENDING_FACE_QUALITY = "PENDING_FACE_QUALITY"
    """Passed to Module 6 for quality assessment."""

    PENDING_MATCHING = "PENDING_MATCHING"
    """Passed to Module 7 for candidate matching."""

    DISCARDED = "DISCARDED"
    """Filtered out (duplicate, poor quality, validation failure)."""

    ERROR = "ERROR"
    """An error occurred during processing."""


class TrackStatus(str, Enum):
    """Lifecycle state of a short-term person track."""

    ACTIVE = "ACTIVE"
    """Track has been matched in recent frames."""

    LOST = "LOST"
    """Track was not matched in the last frame but has not yet expired."""

    EXPIRED = "EXPIRED"
    """Track has exceeded MAX_TRACK_AGE without a match and has been purged."""


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


class BoundingBox(BaseModel):
    """
    Axis-aligned bounding box in absolute pixel coordinates.
    Origin (0, 0) is the top-left corner of the frame.
    """

    x1: float = Field(..., description="Left edge (pixels)")
    y1: float = Field(..., description="Top edge (pixels)")
    x2: float = Field(..., description="Right edge (pixels)")
    y2: float = Field(..., description="Bottom edge (pixels)")

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def centre(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    def iou(self, other: BoundingBox) -> float:
        """Compute Intersection-over-Union with another bounding box."""
        ix1 = max(self.x1, other.x1)
        iy1 = max(self.y1, other.y1)
        ix2 = min(self.x2, other.x2)
        iy2 = min(self.y2, other.y2)

        inter_w = max(0.0, ix2 - ix1)
        inter_h = max(0.0, iy2 - iy1)
        intersection = inter_w * inter_h

        union = self.area + other.area - intersection
        if union <= 0:
            return 0.0
        return intersection / union

    def to_xyxy(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)

    def clamp(self, frame_width: int, frame_height: int) -> BoundingBox:
        """Return a new BoundingBox clamped to frame boundaries."""
        return BoundingBox(
            x1=max(0.0, min(self.x1, frame_width)),
            y1=max(0.0, min(self.y1, frame_height)),
            x2=max(0.0, min(self.x2, frame_width)),
            y2=max(0.0, min(self.y2, frame_height)),
        )


# ---------------------------------------------------------------------------
# Detection results
# ---------------------------------------------------------------------------


class PersonDetection(BaseModel):
    """
    A single person detected in a CCTV frame.

    This is a *perception result* — not an identification. The confidence
    field reflects the object-detection model's class confidence, which
    must not be interpreted as identity confidence.
    """

    detection_id: str = Field(
        default_factory=lambda: f"DET-{uuid4().hex[:12].upper()}",
        description="Unique identifier for this detection event.",
    )
    camera_id: int = Field(..., description="ID of the camera that produced the frame.")
    timestamp: datetime = Field(..., description="UTC timestamp when the frame was captured.")
    bounding_box: BoundingBox = Field(..., description="Person bounding box in frame coordinates.")
    detection_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Object-detection model confidence. "
            "This is NOT identity confidence."
        ),
    )
    frame_reference: str = Field(
        ..., description="Opaque reference string linking back to the originating frame."
    )
    frame_width: int = Field(..., description="Width of the source frame in pixels.")
    frame_height: int = Field(..., description="Height of the source frame in pixels.")


class FaceDetection(BaseModel):
    """
    A face region detected within a previously detected person's crop.

    Face detection is a *perception result* — not recognition. The
    face_detection_confidence reflects the face-detector's score only.
    """

    face_detection_id: str = Field(
        default_factory=lambda: f"FACE-{uuid4().hex[:12].upper()}",
        description="Unique identifier for this face detection event.",
    )
    person_detection_id: str = Field(
        ..., description="detection_id of the parent PersonDetection."
    )
    bounding_box: BoundingBox = Field(
        ..., description="Face bounding box in original frame coordinates."
    )
    face_detection_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Face-detector confidence score. NOT recognition confidence.",
    )
    frame_reference: str = Field(..., description="Frame reference inherited from the parent detection.")
    timestamp: datetime = Field(..., description="UTC timestamp of the originating frame.")
    landmark_points: Optional[list[tuple[float, float]]] = Field(
        default=None,
        description="Optional facial landmark coordinates returned by the detector.",
    )


# ---------------------------------------------------------------------------
# Tracking
# ---------------------------------------------------------------------------


class TrackState(BaseModel):
    """
    Short-term person track maintained across consecutive frames.

    A track groups successive detections of the same physical person
    within a single camera view. It does NOT represent an identified individual.
    """

    track_id: str = Field(
        ..., description="Unique track identifier (e.g. TRACK-00001)."
    )
    camera_id: int = Field(..., description="Camera to which this track belongs.")
    first_seen: datetime = Field(
        ..., description="UTC timestamp of the first detection in this track."
    )
    last_seen: datetime = Field(
        ..., description="UTC timestamp of the most recent matched detection."
    )
    current_bounding_box: BoundingBox = Field(
        ..., description="Bounding box from the most recently matched frame."
    )
    observation_count: int = Field(
        default=1,
        ge=1,
        description="Total number of matched detections accumulated in this track.",
    )
    best_frame_reference: str = Field(
        ...,
        description=(
            "Frame reference for the observation with the highest combined "
            "person + face detection confidence — used for downstream processing."
        ),
    )
    best_person_confidence: float = Field(
        default=0.0, description="Person detection confidence of the best observation."
    )
    best_face_confidence: float = Field(
        default=0.0, description="Face detection confidence of the best observation (0 if no face)."
    )
    status: TrackStatus = Field(default=TrackStatus.ACTIVE)
    missed_frames: int = Field(
        default=0,
        description="Number of consecutive frames in which this track had no match.",
    )
    last_emit_frame: int = Field(
        default=0,
        description="Pipeline frame counter when a candidate was last emitted for this track.",
    )


# ---------------------------------------------------------------------------
# Candidate Observation (Module 5 output — input to Modules 6 & 7)
# ---------------------------------------------------------------------------


class CandidateObservation(BaseModel):
    """
    Standardised output object from Module 5 AI Video Processing.

    This is the **interface contract** between Module 5 and the downstream
    modules (Module 6: Face Quality Assessment, Module 7: Candidate Matching).

    Design invariant: this object carries NO identity label, NO case reference,
    and NO field that implies a positive identification. It represents a
    *candidate observation* that requires further assessment and authorised
    human review.
    """

    candidate_id: str = Field(
        default_factory=lambda: f"CAND-{uuid4().hex[:16].upper()}",
        description="Globally unique identifier for this candidate observation.",
    )
    track_id: str = Field(
        ..., description="ID of the short-term track this observation belongs to."
    )
    camera_id: int = Field(..., description="Source camera ID.")
    camera_code: str = Field(default="", description="Human-readable camera code.")
    timestamp: datetime = Field(
        ..., description="UTC timestamp of the best source frame."
    )
    location: Optional[str] = Field(
        default=None, description="Human-readable camera location name."
    )
    department_id: int = Field(
        ..., description="Department ID that owns this camera."
    )

    # Geometry
    person_bbox: BoundingBox = Field(
        ..., description="Person bounding box from the best observation frame."
    )
    face_bbox: Optional[BoundingBox] = Field(
        default=None,
        description="Face bounding box if a usable face was detected; None otherwise.",
    )

    # Confidence scores (perception — NOT identity confidence)
    person_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Object-detection confidence for the person. "
            "Must NOT be interpreted as identity confidence."
        ),
    )
    face_confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Face-detector confidence if a face was found. "
            "Must NOT be interpreted as identity confidence."
        ),
    )

    # Frame reference
    frame_reference: str = Field(
        ...,
        description="Opaque reference to the best-quality source frame.",
    )

    # Status
    quality_status: QualityStatus = Field(
        default=QualityStatus.PENDING,
        description=(
            "Coarse quality flag set by Module 5; "
            "fine-grained quality is assessed by Module 6."
        ),
    )
    processing_status: ProcessingStatus = Field(
        default=ProcessingStatus.PENDING_FACE_QUALITY,
        description="Current lifecycle state of this candidate.",
    )

    # Observation summary
    observation_count: int = Field(
        default=1,
        description="Number of frames in the source track at emission time.",
    )
    has_face: bool = Field(
        default=False,
        description="True if a usable face bounding box is present.",
    )

    # Landmark data (optional — passed through for Module 6)
    landmark_points: Optional[list[tuple[float, float]]] = Field(
        default=None,
        description="Optional facial landmarks from the face detector.",
    )

    # In-memory face crop payload for downstream Module 6 & 7 processing
    face_crop_base64: Optional[str] = Field(
        default=None,
        description="Base64 encoded JPEG face crop for in-memory pipeline handover.",
    )
