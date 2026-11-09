"""
Module 7 – Pydantic Schemas for Candidate Matching & Ranking
============================================================
Canonical data structures representing match queries, candidate results,
similarity scores, ranking outputs, possible match events, and telemetry.

AI Safety & Privacy Invariants:
-------------------------------
1. Zero Autonomous Identity Confirmation:
   This module NEVER outputs 'IDENTITY_CONFIRMED' or 'This person is definitely X'.
   All candidate alerts require authorized human verification in Module 8.
2. Similarity ≠ Guaranteed Identity Probability:
   Scores represent numerical feature vector closeness, never guaranteed probability.
3. Logical Separation:
   Missing Person and Wanted Person datasets are maintained and queried under
   strict domain separation.
4. Non-Biased Ranking:
   Identity matching is derived solely from face features and image quality;
   it never infers identity from clothing, race, ethnicity, gender, or location alone.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class SearchMode(str, Enum):
    """Supported candidate dataset search scopes."""

    MISSING = "MISSING"
    """Search only against the Missing Person reference dataset."""

    WANTED = "WANTED"
    """Search only against the Wanted Person reference dataset."""

    ALL_ACTIVE_CASES = "ALL_ACTIVE_CASES"
    """Search across all authorized active cases in both datasets."""


class SimilarityMetric(str, Enum):
    """Vector similarity metric used for feature comparison."""

    COSINE = "COSINE"
    """Normalized cosine similarity in range [0.0, 1.0]."""

    EUCLIDEAN = "EUCLIDEAN"
    """Inverted Euclidean distance similarity in range [0.0, 1.0]."""


class ReferenceAggregationMethod(str, Enum):
    """Strategy for aggregating multiple reference image scores for a case."""

    MAXIMUM = "MAXIMUM"
    """Peak similarity score among all enrolled reference images."""

    AVERAGE = "AVERAGE"
    """Mean similarity score across all enrolled reference images."""

    TOP_N = "TOP_N"
    """Average of the top N highest reference similarity scores."""


class TrackAggregationMethod(str, Enum):
    """Strategy for aggregating temporal observations from the same track."""

    BEST_OBSERVATION = "BEST_OBSERVATION"
    """Highest scoring match across the track history."""

    AVERAGE = "AVERAGE"
    """Rolling average of candidate similarity scores across the track."""

    EXPONENTIAL_DECAY = "EXPONENTIAL_DECAY"
    """Recency-weighted exponential decay of candidate similarity scores."""


class MatchDecisionState(str, Enum):
    """Algorithmic decision state based on similarity and policy thresholds."""

    NO_CANDIDATE = "NO_CANDIDATE"
    """No reference observation satisfied minimal similarity criteria."""

    LOW_SIMILARITY = "LOW_SIMILARITY"
    """Candidates found, but scores fall below configured review threshold."""

    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    """Candidate achieved review threshold; forwarded for human verification."""

    HIGH_PRIORITY_REVIEW = "HIGH_PRIORITY_REVIEW"
    """Candidate achieved high priority threshold; expedited for urgent human review."""


class MatchEventStatus(str, Enum):
    """Lifecycle status of a possible match event."""

    PENDING_REVIEW = "PENDING_REVIEW"
    """Awaiting authorized human examiner verification in Module 8."""

    IN_REVIEW = "IN_REVIEW"
    """Under active evaluation by an authorized human examiner."""

    VERIFIED = "VERIFIED"
    """Identity verified by authorized human examiner (Module 8 output)."""

    REJECTED = "REJECTED"
    """Disconfirmed by authorized human examiner as a false candidate."""


class CalibrationStatus(str, Enum):
    """Status indicating whether similarity has been mathematically calibrated."""

    NOT_CALIBRATED = "NOT_CALIBRATED"
    """Raw vector similarity score presented as an algorithmic ranking signal."""

    CALIBRATED = "CALIBRATED"
    """Score calibrated via validated empirical probability scaling."""


# ---------------------------------------------------------------------------
# Inputs & Payloads
# ---------------------------------------------------------------------------


class MatchReadyCandidateInput(BaseModel):
    """
    Standard match-ready candidate observation payload received from Module 6.
    Only observations with is_match_ready=True should enter the matching pipeline.
    """

    candidate_id: str = Field(..., description="Unique candidate observation ID from Module 5/6.")
    track_id: str = Field(..., description="Short-term person tracking ID from Module 5.")
    camera_id: int = Field(..., description="Camera ID that captured the CCTV observation.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the observation.",
    )
    face_image_reference: Optional[str] = Field(
        default=None,
        description="Storage URI or file path to the extracted face crop.",
    )
    face_image_base64: Optional[str] = Field(
        default=None,
        description="Base64 encoded JPEG/PNG face crop for real-time memory passing.",
    )
    face_quality_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Composite face quality score from Module 6.",
    )
    quality_status: str = Field(
        ...,
        description="Module 6 quality classification (EXCELLENT, GOOD, ACCEPTABLE).",
    )
    face_detection_confidence: float = Field(
        default=0.90,
        ge=0.0,
        le=1.0,
        description="Module 5 face detector confidence score.",
    )
    camera_location: Optional[str] = Field(
        default=None,
        description="Contextual camera location description (for reference only).",
    )
    department_id: Optional[int] = Field(
        default=None,
        description="Department ID for multi-tenant data access control.",
    )
    is_match_ready: bool = Field(
        default=True,
        description="Module 6 match-readiness gate flag.",
    )
    search_mode: Optional[SearchMode] = Field(
        default=None,
        description="Optional dataset override (MISSING, WANTED, or ALL_ACTIVE_CASES).",
    )


class DirectQueryFaceRequest(BaseModel):
    """Direct face query request for researcher or investigator image search."""

    face_image_base64: Optional[str] = Field(
        default=None,
        description="Base64 encoded face image.",
    )
    face_image_reference: Optional[str] = Field(
        default=None,
        description="Local file path or storage reference.",
    )
    search_mode: SearchMode = Field(
        default=SearchMode.ALL_ACTIVE_CASES,
        description="Target dataset: MISSING, WANTED, or ALL_ACTIVE_CASES.",
    )
    department_id: Optional[int] = Field(
        default=None,
        description="Optional department scope constraint.",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of candidate records to retrieve.",
    )


# ---------------------------------------------------------------------------
# Embedding & Index Records
# ---------------------------------------------------------------------------


class ReferenceEmbeddingRecord(BaseModel):
    """Internal representation of an enrolled reference image feature vector."""

    embedding_id: str = Field(
        default_factory=lambda: f"EMB-{uuid4().hex[:12].upper()}",
        description="Unique identifier for this feature embedding.",
    )
    image_id: int = Field(..., description="Module 3 ReferenceImage database primary key.")
    case_id: int = Field(..., description="Associated case primary key.")
    case_number: str = Field(..., description="Standard case identifier (e.g. MP-2026-0012).")
    category: str = Field(..., description="Case category: MISSING or WANTED.")
    department_id: int = Field(..., description="Department ID owning the case.")
    model_name: str = Field(..., description="Name of the model used to extract this vector.")
    model_version: str = Field(..., description="Version of the model used for extraction.")
    embedding_dim: int = Field(default=512, description="Vector dimensionality.")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when embedding was computed.",
    )
    is_active: bool = Field(default=True, description="Whether this reference is active in search.")
    reference_quality_score: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Quality metric of the reference image.",
    )


# ---------------------------------------------------------------------------
# Candidate Match Results & Events
# ---------------------------------------------------------------------------


class CandidateMatchResult(BaseModel):
    """
    Ranked candidate case retrieved during vector similarity search.
    Represents an algorithmic recommendation, NOT a confirmed identity.
    """

    rank: int = Field(..., ge=1, description="Ranking position (1 = highest match score).")
    case_id: int = Field(..., description="Database ID of the matched case.")
    case_number: str = Field(..., description="Case reference number (e.g. MP-2026-0012).")
    category: str = Field(..., description="Dataset category: MISSING or WANTED.")
    department_id: int = Field(..., description="Case department identifier.")
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Algorithmic feature vector similarity score (NOT an identity probability).",
    )
    candidate_ranking_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Composite ranking score combining similarity, quality, and multi-ref evidence.",
    )
    calibrated_score: Optional[float] = Field(
        default=None,
        description="Calibrated score if empirical calibration model is active.",
    )
    calibration_status: CalibrationStatus = Field(
        default=CalibrationStatus.NOT_CALIBRATED,
        description="Status of scientific probability calibration.",
    )
    decision_state: MatchDecisionState = Field(
        ...,
        description="Threshold classification (POSSIBLE_MATCH, LOW_SIMILARITY, etc.).",
    )
    best_reference_image_id: Optional[int] = Field(
        default=None,
        description="Image ID of the highest-similarity enrolled reference photo.",
    )
    matched_reference_count: int = Field(
        default=1,
        description="Total active reference images evaluated for this case.",
    )
    evidence_summary: str = Field(
        ...,
        description="Human-readable breakdown of similarity, reference count, and aggregation.",
    )


class PossibleMatchEvent(BaseModel):
    """
    Structured alert event emitted to Module 8: Human Verification Queue
    whenever a candidate achieves POSSIBLE_MATCH or HIGH_PRIORITY_REVIEW.
    """

    event_id: str = Field(
        default_factory=lambda: f"EVT-{uuid4().hex[:12].upper()}",
        description="Unique possible match event identifier.",
    )
    candidate_id: str = Field(..., description="Source observation candidate ID.")
    track_id: str = Field(..., description="Short-term person track ID.")
    camera_id: int = Field(..., description="Source CCTV camera ID.")
    case_id: int = Field(..., description="Matched case database ID.")
    case_number: str = Field(..., description="Matched case number.")
    category: str = Field(..., description="Dataset category: MISSING or WANTED.")
    timestamp: datetime = Field(..., description="CCTV capture timestamp.")
    location: Optional[str] = Field(
        default=None,
        description="Contextual camera location (informational only).",
    )
    similarity_score: float = Field(
        ...,
        description="Algorithmic feature similarity score.",
    )
    candidate_ranking_score: float = Field(
        ...,
        description="Composite candidate ranking score.",
    )
    query_quality_score: float = Field(
        ...,
        description="Module 6 face quality score.",
    )
    reference_quality_information: dict[str, Any] = Field(
        default_factory=dict,
        description="Quality telemetry of matched reference image(s).",
    )
    rank: int = Field(default=1, description="Rank among retrieved candidates.")
    decision_state: MatchDecisionState = Field(
        ...,
        description="Decision tier (POSSIBLE_MATCH or HIGH_PRIORITY_REVIEW).",
    )
    status: MatchEventStatus = Field(
        default=MatchEventStatus.PENDING_REVIEW,
        description="Workflow state in Module 8 (defaults to PENDING_REVIEW).",
    )
    model_name: str = Field(..., description="Name of embedding model.")
    model_version: str = Field(..., description="Version of embedding model.")
    disclaimer: str = Field(
        default=(
            "POSSIBLE MATCH — REQUIRES AUTHORIZED HUMAN VERIFICATION. "
            "This algorithmic signal does NOT constitute a confirmed identity."
        ),
        description="Mandatory legal and safety invariant notice.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when event was created.",
    )


class CandidateSearchResponse(BaseModel):
    """Comprehensive response returned by candidate search operations."""

    query_candidate_id: Optional[str] = Field(
        default=None,
        description="Source candidate observation ID.",
    )
    search_mode: SearchMode = Field(..., description="Active dataset search mode.")
    similarity_metric: SimilarityMetric = Field(..., description="Metric used for comparison.")
    reference_aggregation_method: ReferenceAggregationMethod = Field(
        ..., description="Method used to combine multiple reference images."
    )
    candidates_retrieved: int = Field(..., description="Count of candidate cases returned.")
    decision_state: MatchDecisionState = Field(
        ..., description="Overall highest decision tier among retrieved candidates."
    )
    candidates: list[CandidateMatchResult] = Field(
        default_factory=list,
        description="Ranked candidate cases ordered by candidate_ranking_score.",
    )
    events_created: list[PossibleMatchEvent] = Field(
        default_factory=list,
        description="PossibleMatchEvents emitted to Module 8 queue.",
    )
    latency_ms: float = Field(..., description="Total search pipeline latency in milliseconds.")
    safety_notice: str = Field(
        default=(
            "POSSIBLE MATCH — REQUIRES AUTHORIZED HUMAN VERIFICATION. "
            "Scores represent algorithmic feature similarity, NOT guaranteed identity probability."
        ),
        description="AI Safety invariant compliance statement.",
    )


# ---------------------------------------------------------------------------
# Telemetry & Re-indexing
# ---------------------------------------------------------------------------


class MatchingTelemetryResponse(BaseModel):
    """Operational telemetry and research metrics for Module 7."""

    queries_processed: int = Field(default=0, description="Total face queries evaluated.")
    candidates_retrieved: int = Field(default=0, description="Total candidates returned.")
    possible_matches_created: int = Field(default=0, description="Possible match alerts emitted.")
    high_priority_matches_created: int = Field(default=0, description="High priority alerts emitted.")
    no_candidate_results: int = Field(default=0, description="Queries resulting in NO_CANDIDATE.")
    average_search_latency_ms: float = Field(default=0.0, description="Mean search duration.")
    embedding_generation_latency_ms: float = Field(default=0.0, description="Mean feature extraction duration.")
    vector_search_latency_ms: float = Field(default=0.0, description="Mean vector comparison duration.")
    active_missing_references: int = Field(default=0, description="Active reference images in Missing dataset.")
    active_wanted_references: int = Field(default=0, description="Active reference images in Wanted dataset.")
    total_active_references: int = Field(default=0, description="Total searchable reference embeddings.")
    active_model_name: str = Field(..., description="Currently active embedding model name.")
    active_model_version: str = Field(..., description="Currently active model version.")


class ReindexResponse(BaseModel):
    """Response summary for dataset re-indexing operation."""

    status: str = Field(default="COMPLETED", description="Re-indexing status.")
    total_reference_images_scanned: int = Field(..., description="Total reference records inspected.")
    embeddings_generated: int = Field(..., description="New embeddings successfully computed.")
    embeddings_deactivated: int = Field(..., description="Inactive embeddings pruned.")
    errors_encountered: int = Field(default=0, description="Failed image extractions.")
    model_name: str = Field(..., description="Model used for re-indexing.")
    model_version: str = Field(..., description="Model version used.")
    duration_s: float = Field(..., description="Total execution time in seconds.")
