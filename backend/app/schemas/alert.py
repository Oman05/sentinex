"""
Module 9 – Alert & Department Notification System Pydantic Schemas
==================================================================
Data validation and response serialization schemas for Module 9.

AI Safety Invariant:
    Alert creation strictly requires source_module = "MODULE_8" and
    review_status = "CONFIRMED_FOR_ACTION".  Direct algorithmic candidate
    or similarity signals will fail schema and business validation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.alert import (
    AlertPriority,
    AlertStatus,
    DeliveryChannel,
    DepartmentType,
    RecipientType,
)


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------


class AlertCreateRequest(BaseModel):
    """
    Payload for creating an operational alert.
    Must be emitted only by Module 8 after human verification.
    """

    source_module: str = Field(
        ...,
        description="Source module emitting the event. Strictly must be 'MODULE_8'",
        examples=["MODULE_8"],
    )
    review_status: str = Field(
        ...,
        description="Review approval status. Strictly must be 'CONFIRMED_FOR_ACTION'",
        examples=["CONFIRMED_FOR_ACTION"],
    )
    review_event_id: int = Field(..., description="ID of the confirmed ReviewEventDB")
    match_event_id: str = Field(..., description="Unique match event ID from Module 7")
    case_id: int = Field(..., description="Case primary key")
    camera_id: Optional[int] = Field(None, description="Detection camera ID")
    priority: Optional[AlertPriority] = Field(
        None, description="Optional override priority; defaults to case priority or NORMAL"
    )
    notes: Optional[str] = Field(None, description="Operational notes from examiner")

    model_config = ConfigDict(from_attributes=True)


class AlertAcknowledgeRequest(BaseModel):
    """Payload to acknowledge an alert."""

    notes: Optional[str] = Field(None, max_length=1000, description="Acknowledgment notes / initial actions")


class AlertStatusUpdateRequest(BaseModel):
    """Payload to update alert lifecycle status."""

    status: AlertStatus = Field(..., description="Target status (IN_PROGRESS, RESOLVED, CLOSED)")
    notes: Optional[str] = Field(None, max_length=2000, description="Status change rationale or resolution details")


class AlertRetryRequest(BaseModel):
    """Payload to retry failed notifications."""

    notification_id: Optional[int] = Field(
        None, description="Specific notification ID to retry; if omitted, retries all failed"
    )


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------


class AlertRecipientResponse(BaseModel):
    id: int
    alert_id: int
    department_id: int
    department_name: Optional[str] = None
    department_code: Optional[str] = None
    recipient_type: RecipientType
    delivery_channel: DeliveryChannel
    destination_reference: Optional[str] = None
    status: AlertStatus
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class AlertNotificationResponse(BaseModel):
    id: int
    alert_id: int
    recipient_id: int
    channel: DeliveryChannel
    status: AlertStatus
    attempt_count: int
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    message_payload: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertTimelineResponse(BaseModel):
    id: int
    alert_id: int
    timestamp: datetime
    event_type: str
    description: str
    metadata_json: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AlertAuditLogResponse(BaseModel):
    id: int
    alert_id: int
    user_id: Optional[int] = None
    actor_username: Optional[str] = None
    action: str
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    timestamp: datetime
    ip_address: Optional[str] = None
    metadata_json: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AlertResponse(BaseModel):
    id: int
    alert_number: str
    match_event_id: str
    review_event_id: int
    case_id: int
    case_number: str
    category: str
    originating_department_id: int
    originating_department_name: Optional[str] = None
    detected_camera_id: Optional[int] = None
    detected_camera_code: Optional[str] = None
    detected_location: Optional[str] = None
    nearest_department_id: Optional[int] = None
    nearest_department_name: Optional[str] = None
    routing_reason: Optional[str] = None
    distance_km: Optional[float] = None
    priority: AlertPriority
    status: AlertStatus
    observation_count: int
    last_observation_at: datetime
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AlertDetailResponse(AlertResponse):
    case_title: Optional[str] = None
    person_identifier: Optional[str] = None
    case_priority: Optional[str] = None
    examiner_username: Optional[str] = None
    decision_notes: Optional[str] = None
    similarity_score: Optional[float] = None
    similarity_disclaimer: str = (
        "AI similarity score is an algorithmic ranking metric, NOT an identity confirmation. "
        "This alert was generated exclusively following authorized human verification."
    )
    recipients: List[AlertRecipientResponse] = []
    notifications: List[AlertNotificationResponse] = []
    timeline: List[AlertTimelineResponse] = []
    audit_logs: List[AlertAuditLogResponse] = []

    model_config = ConfigDict(from_attributes=True)


class AlertListResponse(BaseModel):
    items: List[AlertResponse]
    total: int
    page: int
    page_size: int
    pages: int


class AlertDashboardStatsResponse(BaseModel):
    total_alerts: int = 0
    pending: int = 0
    acknowledged: int = 0
    in_progress: int = 0
    resolved: int = 0
    closed: int = 0
    failed: int = 0
    duplicate_alerts_prevented: int = 0
    average_latency_seconds: float = 0.0
