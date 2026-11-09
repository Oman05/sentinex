"""
Module 8 – Pydantic Schemas for Human Verification & Investigation Dashboard
=============================================================================

AI Safety Invariant:
    All similarity scores presented to examiners MUST be accompanied by the
    disclaimer: "This score is an algorithmic similarity signal and does not
    independently establish identity."

    ReviewDecision values are operational review outcomes; they are NOT
    algorithmic identity confirmations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.review_event import ReviewDecision, ReviewStatus, TaskPriority, TaskStatus


# ---------------------------------------------------------------------------
# Shared disclaimer (embedded in all score-bearing schemas)
# ---------------------------------------------------------------------------

SIMILARITY_DISCLAIMER = (
    "This score is an algorithmic similarity signal and does not "
    "independently establish identity."
)


# ---------------------------------------------------------------------------
# Review Event Schemas
# ---------------------------------------------------------------------------


class ReviewEventSummary(BaseModel):
    """Lightweight summary for listing review events."""

    id: int
    match_event_id: str
    case_id: int
    case_number: str
    category: str
    similarity_score: float
    candidate_ranking_score: float
    rank: Optional[int] = None
    decision_state: str
    status: str
    assigned_to: Optional[int] = None
    camera_location: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    similarity_score_disclaimer: str = Field(
        default=SIMILARITY_DISCLAIMER,
        description="AI safety disclaimer — never interpret similarity as guaranteed identity.",
    )
    priority: Optional[str] = None
    face_quality_label: Optional[str] = None
    observation_count: Optional[int] = None
    detection_quality_score: Optional[float] = None

    model_config = {"from_attributes": True}


class ReviewEventDetail(BaseModel):
    """Full detail view of a review event for the examiner dashboard."""

    id: int
    match_event_id: str
    case_id: int
    case_number: str
    category: str
    similarity_score: float
    candidate_ranking_score: float
    query_quality_score: Optional[float] = None
    rank: Optional[int] = None
    decision_state: str
    camera_id: Optional[int] = None
    camera_location: Optional[str] = None
    track_id: Optional[str] = None
    model_name: Optional[str] = None
    model_version: Optional[str] = None

    status: str
    assigned_to: Optional[int] = None
    decision: Optional[str] = None
    decision_notes: Optional[str] = None
    evidence_request_notes: Optional[str] = None

    created_at: datetime
    updated_at: datetime
    review_started_at: Optional[datetime] = None
    decision_at: Optional[datetime] = None
    module9_notified: bool = False

    similarity_score_disclaimer: str = Field(
        default=SIMILARITY_DISCLAIMER,
        description="AI safety disclaimer — never interpret similarity as guaranteed identity.",
    )
    priority: Optional[str] = None
    face_quality_label: Optional[str] = None
    observation_count: Optional[int] = None
    detection_quality_score: Optional[float] = None

    model_config = {"from_attributes": True}


class ReviewEventIngestRequest(BaseModel):
    """Payload to ingest a Module 7 match event into the review queue."""

    match_event_id: str = Field(..., description="Unique event_id from Module 7")
    case_id: int
    case_number: str
    category: str = Field(..., pattern="^(MISSING|WANTED)$")
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    candidate_ranking_score: float = Field(..., ge=0.0, le=1.0)
    decision_state: str
    query_quality_score: Optional[float] = None
    rank: Optional[int] = None
    camera_id: Optional[int] = None
    camera_location: Optional[str] = None
    track_id: Optional[str] = None
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    priority: Optional[str] = None
    face_quality_label: Optional[str] = None
    observation_count: Optional[int] = None
    detection_quality_score: Optional[float] = None


class StartReviewRequest(BaseModel):
    """Request to claim and begin reviewing a pending event."""

    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional opening remarks from the examiner.",
    )


class ReviewDecisionRequest(BaseModel):
    """
    Examiner's decision on a possible match event.

    Allowed decisions:
    - CONFIRM_FOR_ACTION  – proceed to next authorized operational step
    - REJECTED            – false positive, no action required
    - NEED_MORE_EVIDENCE  – further evidence required before deciding
    """

    decision: ReviewDecision = Field(
        ...,
        description="Examiner decision. Must be one of: CONFIRM_FOR_ACTION, REJECTED, NEED_MORE_EVIDENCE.",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Mandatory rationale for the decision (recommended).",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "decision": "CONFIRM_FOR_ACTION",
                "notes": (
                    "Examiner has reviewed CCTV frame, compared reference image, "
                    "and determined that field verification is warranted. "
                    "This decision does NOT confirm identity."
                ),
            }
        }
    }


class EvidenceRequestType(str, Enum):
    ADDITIONAL_OBSERVATIONS = "ADDITIONAL_OBSERVATIONS"
    ADDITIONAL_CAMERA_FOOTAGE = "ADDITIONAL_CAMERA_FOOTAGE"
    DIFFERENT_TIME_INTERVAL = "DIFFERENT_TIME_INTERVAL"
    ADDITIONAL_REFERENCE_IMAGE = "ADDITIONAL_REFERENCE_IMAGE"
    REASSIGN_REVIEWER = "REASSIGN_REVIEWER"

class EvidenceRequestRequest(BaseModel):
    """Request for additional evidence from investigators."""

    notes: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Description of what additional evidence is required.",
    )
    request_type: Optional[EvidenceRequestType] = None
    reason: Optional[str] = Field(default=None, max_length=1000)


class AssignRequest(BaseModel):
    """Assign or re-assign a review event to an examiner."""

    examiner_user_id: int = Field(..., description="User ID of the examiner to assign.")
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional assignment notes.",
    )


# ---------------------------------------------------------------------------
# Audit Log Schemas
# ---------------------------------------------------------------------------


class ReviewAuditEntry(BaseModel):
    """A single audit log entry for a review event."""

    id: int
    review_event_id: int
    actor_id: int
    actor_username: str
    action: str
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    notes: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


class ReviewHistory(BaseModel):
    """Full audit history for a review event."""

    review_event_id: int
    match_event_id: str
    case_number: str
    entries: list[ReviewAuditEntry]


# ---------------------------------------------------------------------------
# Investigation Task Schemas
# ---------------------------------------------------------------------------


class InvestigationTaskCreate(BaseModel):
    """Payload to create an investigation task after a confirm-for-action decision."""

    review_event_id: int
    title: str = Field(..., min_length=5, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)
    priority: TaskPriority = TaskPriority.MEDIUM
    assigned_to: Optional[int] = None
    due_date: Optional[datetime] = None


class InvestigationTaskResponse(BaseModel):
    """Investigation task detail."""

    id: int
    review_event_id: int
    case_id: int
    case_number: str
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    assigned_to: Optional[int] = None
    created_by: int
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskUpdateRequest(BaseModel):
    """Update an investigation task's status or resolution."""

    status: Optional[TaskStatus] = None
    assigned_to: Optional[int] = None
    resolution_notes: Optional[str] = Field(default=None, max_length=5000)
    due_date: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Module 9 Notification Hook
# ---------------------------------------------------------------------------


class Module9NotificationPayload(BaseModel):
    """
    Payload emitted to Module 9 when an examiner confirms an event for action.

    IMPORTANT: This payload represents a human decision, NOT an algorithmic
    identity assertion.  The field 'examiner_confirmed_for_action' is the
    authoritative signal — it was set by a credentialed examiner, not the AI.
    """

    review_event_id: int
    match_event_id: str
    case_id: int
    case_number: str
    category: str
    similarity_score: float
    similarity_score_disclaimer: str = SIMILARITY_DISCLAIMER
    examiner_confirmed_for_action: bool = True
    examiner_user_id: int
    examiner_notes: Optional[str] = None
    decision_at: datetime


# ---------------------------------------------------------------------------
# Dashboard Analytics / Stats
# ---------------------------------------------------------------------------


class ReviewDashboardStats(BaseModel):
    """Aggregate operational statistics for the Investigation Dashboard."""

    total_events: int = 0
    pending_review: int = 0
    under_review: int = 0
    confirmed_for_action: int = 0
    rejected: int = 0
    need_more_evidence: int = 0
    missing_category_count: int = 0
    wanted_category_count: int = 0
    total_tasks: int = 0
    open_tasks: int = 0
    in_progress_tasks: int = 0
    completed_tasks: int = 0
    similarity_score_disclaimer: str = Field(
        default=SIMILARITY_DISCLAIMER,
        description="AI safety disclaimer — never interpret similarity as guaranteed identity.",
    )

class NotificationItem(BaseModel):
    id: int
    event_type: str
    title: str
    message: str
    review_event_id: Optional[int] = None
    is_read: bool = False
    created_at: datetime
    model_config = {"from_attributes": True}

class TrackObservation(BaseModel):
    observation_id: str
    timestamp: datetime
    quality_label: str
    quality_score: float
    frame_number: Optional[int] = None
    model_config = {"from_attributes": True}

class TrackHistory(BaseModel):
    track_id: str
    observations: list[TrackObservation]
    best_quality_observation_id: Optional[str] = None
