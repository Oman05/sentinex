"""
Module 9 – Alert & Department Notification System ORM Models
============================================================
Database models for operational alerts, department recipients, notification
delivery tracking, timeline milestones, and immutable audit logs.

Safety Invariants:
    1. Operational alerts are generated ONLY after human verification
       approval (status = CONFIRMED_FOR_ACTION from Module 8).
    2. AI similarity signals, top rankings, or raw detector outputs NEVER
       directly trigger operational alerts.
    3. Biometric feature vectors, high-resolution faces, and raw CCTV frames
       are NOT serialized in external notification payloads.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class AlertPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    FAILED = "FAILED"


class RecipientType(str, Enum):
    ORIGINATING_DEPARTMENT = "ORIGINATING_DEPARTMENT"
    NEAREST_AUTHORIZED_DEPARTMENT = "NEAREST_AUTHORIZED_DEPARTMENT"
    ESCALATION_RECIPIENT = "ESCALATION_RECIPIENT"


class DeliveryChannel(str, Enum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH_NOTIFICATION = "PUSH_NOTIFICATION"
    SECURE_INTERNAL_API = "SECURE_INTERNAL_API"


class DepartmentType(str, Enum):
    POLICE = "POLICE"
    CYBER_DEFENSE = "CYBER_DEFENSE"
    CENTRAL_DEPARTMENT = "CENTRAL_DEPARTMENT"
    REGIONAL_DEPARTMENT = "REGIONAL_DEPARTMENT"
    OTHER_AUTHORIZED_AGENCY = "OTHER_AUTHORIZED_AGENCY"


class AlertDB(Base):
    """
    Operational Alert raised strictly after Module 8 human confirmation.
    """

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    alert_number: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False,
        comment="Human-readable ID e.g. ALT-2026-000001",
    )
    match_event_id: Mapped[str] = mapped_column(
        String(100), index=True, nullable=False,
        comment="Event ID from match_events / review_events",
    )
    review_event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("review_events.id"), index=True, nullable=False,
    )
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id"), index=True, nullable=False,
    )
    case_number: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    category: Mapped[str] = mapped_column(
        String(20), index=True, nullable=False,
        comment="MISSING or WANTED",
    )

    # Department routing
    originating_department_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("departments.id"), index=True, nullable=False,
        comment="Department that registered the case",
    )
    detected_camera_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("cameras.id"), index=True, nullable=True,
    )
    detected_camera_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    detected_location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    nearest_department_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("departments.id"), index=True, nullable=True,
        comment="Nearest authorized department responsible for camera location",
    )
    routing_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Explanation for why nearest department was chosen (distance, jurisdiction)",
    )
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Lifecycle & status
    priority: Mapped[str] = mapped_column(
        String(20), default=AlertPriority.NORMAL.value, nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(
        String(30), default=AlertStatus.CREATED.value, nullable=False, index=True,
    )

    # Deduplication and repeated observations
    observation_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_observation_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True,
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    recipients = relationship("AlertRecipientDB", back_populates="alert", cascade="all, delete-orphan")
    notifications = relationship("AlertNotificationDB", back_populates="alert", cascade="all, delete-orphan")
    audit_logs = relationship("AlertAuditLogDB", back_populates="alert", cascade="all, delete-orphan")
    timeline = relationship("AlertTimelineDB", back_populates="alert", cascade="all, delete-orphan")


class AlertRecipientDB(Base):
    """
    Designated department recipient for an operational alert.
    """

    __tablename__ = "alert_recipients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    alert_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("alerts.id"), index=True, nullable=False,
    )
    department_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("departments.id"), index=True, nullable=False,
    )
    recipient_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="ORIGINATING_DEPARTMENT | NEAREST_AUTHORIZED_DEPARTMENT | ESCALATION_RECIPIENT",
    )
    delivery_channel: Mapped[str] = mapped_column(
        String(30), default=DeliveryChannel.IN_APP.value, nullable=False, index=True,
    )
    destination_reference: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Target email address, device token, or department code",
    )
    status: Mapped[str] = mapped_column(
        String(30), default=AlertStatus.QUEUED.value, nullable=False, index=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True,
    )

    alert = relationship("AlertDB", back_populates="recipients")


class AlertNotificationDB(Base):
    """
    Individual transmission record for an alert through a specific channel.
    """

    __tablename__ = "alert_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    alert_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("alerts.id"), index=True, nullable=False,
    )
    recipient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("alert_recipients.id"), index=True, nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(30), default=AlertStatus.QUEUED.value, nullable=False, index=True,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_payload: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Sanitized alert message (no sensitive biometrics or raw CCTV frames)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True,
    )

    alert = relationship("AlertDB", back_populates="notifications")


class AlertAuditLogDB(Base):
    """
    Append-only immutable audit trail for all alert actions.
    """

    __tablename__ = "alert_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    alert_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("alerts.id"), index=True, nullable=False,
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True,
    )
    actor_username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    previous_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True,
    )
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    alert = relationship("AlertDB", back_populates="audit_logs")


class AlertTimelineDB(Base):
    """
    Chronological milestone events for an alert.
    """

    __tablename__ = "alert_timeline"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    alert_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("alerts.id"), index=True, nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True,
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    alert = relationship("AlertDB", back_populates="timeline")
