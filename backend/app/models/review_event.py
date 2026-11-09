"""
Module 8 – Human Verification & Investigation Dashboard ORM Models
===================================================================
Database models for the authorized human review workflow.

AI Safety Invariant:
    ReviewDecision values represent operational decisions made by authorized
    human examiners — they NEVER constitute an algorithmic identity
    confirmation.  The string "CONFIRM_FOR_ACTION" means: "examiner approves
    proceeding to the next authorized operational step."  It does NOT mean
    the AI system has established identity.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


# ---------------------------------------------------------------------------
# Enumerations stored as VARCHAR in the database
# ---------------------------------------------------------------------------


class ReviewDecision(str, Enum):
    """
    Authorized examiner decision on a possible match event.

    IMPORTANT: These decisions represent operational review outcomes made by
    a human examiner.  They are NOT algorithmic identity confirmations.
    """

    CONFIRM_FOR_ACTION = "CONFIRM_FOR_ACTION"
    """
    Examiner determines the event warrants proceeding to the next authorized
    operational step (e.g. field verification, further investigation).
    This does NOT mean the AI has confirmed the person's identity.
    """

    REJECTED = "REJECTED"
    """Examiner determines the possible match is a false positive."""

    NEED_MORE_EVIDENCE = "NEED_MORE_EVIDENCE"
    """Examiner requests additional evidence before reaching a decision."""


class ReviewStatus(str, Enum):
    """Lifecycle status for a ReviewEvent record."""

    PENDING_REVIEW = "PENDING_REVIEW"
    """In queue; not yet claimed by an examiner."""

    UNDER_REVIEW = "UNDER_REVIEW"
    """Actively being examined by an assigned examiner."""

    CONFIRMED_FOR_ACTION = "CONFIRMED_FOR_ACTION"
    """Examiner confirmed for action (maps to ReviewDecision.CONFIRM_FOR_ACTION)."""

    REJECTED = "REJECTED"
    """Examiner rejected as false positive."""

    NEED_MORE_EVIDENCE = "NEED_MORE_EVIDENCE"
    """Further evidence required before a decision can be made."""


class TaskStatus(str, Enum):
    """Status for an investigation task raised after a review decision."""

    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TaskPriority(str, Enum):
    """Priority level for an investigation task."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------


class ReviewEventDB(Base):
    """
    Persistent record for each possible match event entering Module 8.

    One ReviewEventDB is created per PossibleMatchEvent (from Module 7).
    The reviewer interacts with this record to register their decision.
    """

    __tablename__ = "review_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Reference to the Module 7 match event
    match_event_id: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False,
        comment="event_id from match_events table (Module 7)",
    )
    case_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("cases.id"), nullable=True, index=True
    )
    case_number: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(
        String(20), nullable=True, index=True,
        comment="MISSING or WANTED",
    )

    # Similarity signal fields (read-only from Module 7; never modified here)
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    candidate_ranking_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    query_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decision_state: Mapped[str] = mapped_column(
        String(30), nullable=False, default="POSSIBLE_MATCH",
        comment="AI algorithmic decision state from Module 7 (e.g. POSSIBLE_MATCH)",
    )

    # Camera / detection context
    camera_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("cameras.id"), nullable=True, index=True
    )
    camera_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    track_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Review workflow fields
    status: Mapped[str] = mapped_column(
        String(30), nullable=False,
        default=ReviewStatus.PENDING_REVIEW.value,
        index=True,
    )
    priority: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    face_quality_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    observation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detection_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    assigned_to: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True,
        comment="User ID of the assigned examiner",
    )
    decision: Mapped[str | None] = mapped_column(
        String(30), nullable=True,
        comment="Examiner decision: CONFIRM_FOR_ACTION | REJECTED | NEED_MORE_EVIDENCE",
    )
    decision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_request_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    review_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decision_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Module 9 integration flag
    module9_notified: Mapped[bool] = mapped_column(
        Integer, default=False, nullable=False,
        comment="True once Module 9 alert has been dispatched for this event",
    )


class ReviewAuditLogDB(Base):
    """
    Append-only audit trail for all actions taken on a ReviewEventDB.

    IMPORTANT: Records in this table must NEVER be updated or deleted by
    the application layer.  Only INSERT is permitted.
    """

    __tablename__ = "review_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    review_event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("review_events.id"), nullable=False, index=True
    )
    actor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
        comment="User who performed the action",
    )
    actor_username: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(
        String(60), nullable=False, index=True,
        comment="e.g. START_REVIEW | CONFIRM_FOR_ACTION | REJECTED | ASSIGN | EVIDENCE_REQUEST",
    )
    previous_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )


class InvestigationTaskDB(Base):
    """
    Investigation task created after a review decision.

    Tasks are raised for events where additional field investigation
    or supervisory action is required following a CONFIRM_FOR_ACTION decision.
    """

    __tablename__ = "investigation_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    review_event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("review_events.id"), nullable=False, index=True
    )
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id"), nullable=False, index=True
    )
    case_number: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(30), nullable=False,
        default=TaskStatus.OPEN.value,
        index=True,
    )
    priority: Mapped[str] = mapped_column(
        String(20), nullable=False,
        default=TaskPriority.MEDIUM.value,
        index=True,
    )
    assigned_to: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
