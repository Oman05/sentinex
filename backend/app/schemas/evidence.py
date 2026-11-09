"""
Module 10 – Evidence Management Pydantic Schemas
================================================
Request/response schemas for evidence management endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Retention Policy
# ---------------------------------------------------------------------------

class RetentionPolicyCreate(BaseModel):
    policy_name: str = Field(..., max_length=100)
    evidence_type: str | None = None
    retention_days: int = Field(365, ge=1)
    action_on_expiry: str = Field("REVIEW")
    requires_manual_review: bool = True
    description: str | None = None

    @field_validator("action_on_expiry")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = {"REVIEW", "ARCHIVE", "DELETE"}
        if v.upper() not in allowed:
            raise ValueError(f"action_on_expiry must be one of {allowed}")
        return v.upper()


class RetentionPolicyResponse(BaseModel):
    id: int
    policy_name: str
    evidence_type: str | None
    retention_days: int
    action_on_expiry: str
    requires_manual_review: bool
    description: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Evidence Item
# ---------------------------------------------------------------------------

class EvidenceCreateRequest(BaseModel):
    """Create a new evidence metadata record (file upload handled separately)."""

    evidence_type: str = Field(..., description="EvidenceType enum value")
    case_id: int | None = None
    match_event_id: int | None = None
    review_event_id: int | None = None
    alert_id: int | None = None
    camera_id: int | None = None
    department_id: int | None = None
    classification: str = Field("RESTRICTED")
    description: str | None = None
    tags: str | None = None
    captured_at: datetime | None = None
    track_id: str | None = None
    camera_location: str | None = None
    retention_policy_id: int | None = None
    parent_evidence_id: int | None = None
    version_notes: str | None = None
    clip_start_time: datetime | None = None
    clip_end_time: datetime | None = None
    clip_generation_method: str | None = None


class EvidenceUpdateRequest(BaseModel):
    """Update mutable fields of an evidence item (finalized items are blocked)."""

    description: str | None = None
    tags: str | None = None
    classification: str | None = None
    retention_policy_id: int | None = None
    version_notes: str | None = None


class EvidenceFinalizeRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)
    notes: str | None = None


class EvidenceDeleteRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)
    force: bool = False


class CCTVClipCreateRequest(BaseModel):
    case_id: int | None = None
    camera_id: int | None = None
    stream_id: str | None = None
    event_time: datetime
    window_seconds_before: float = Field(10.0, ge=1.0, le=300.0)
    window_seconds_after: float = Field(10.0, ge=1.0, le=300.0)
    match_event_id: int | None = None
    review_event_id: int | None = None
    alert_id: int | None = None
    classification: str = "RESTRICTED"
    description: str | None = None
    tags: str | None = None
    clip_generation_method: str = "AUTO_WINDOW_APPROVED_EVENT"


class EvidenceResponse(BaseModel):
    id: int
    evidence_id: str
    evidence_type: str
    classification: str
    status: str
    integrity_status: str
    case_id: int | None
    case_number: str | None
    match_event_id: int | None
    review_event_id: int | None
    alert_id: int | None
    camera_id: int | None
    department_id: int | None
    file_name: str | None
    file_size: int | None
    mime_type: str | None
    hash_algorithm: str
    file_hash: str | None
    storage_backend: str
    captured_at: datetime | None
    uploaded_at: datetime | None
    created_at: datetime
    track_id: str | None
    camera_location: str | None
    clip_start_time: datetime | None
    clip_end_time: datetime | None
    clip_duration_seconds: float | None
    clip_generation_method: str | None
    version_number: int
    parent_evidence_id: int | None
    version_notes: str | None
    description: str | None
    tags: str | None
    retention_policy_id: int | None
    retention_expires_at: datetime | None
    last_integrity_check_at: datetime | None

    # NOTE: file_reference is intentionally omitted from public response
    # to prevent direct storage path exposure

    model_config = {"from_attributes": True}


class EvidenceListResponse(BaseModel):
    items: list[EvidenceResponse]
    total: int
    page: int
    page_size: int


class EvidenceIntegrityResponse(BaseModel):
    evidence_id: str
    integrity_status: str
    stored_hash: str | None
    computed_hash: str | None
    hash_algorithm: str
    verified_at: datetime
    match: bool
    message: str


class EvidenceArchiveRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


class EvidenceExportRequest(BaseModel):
    export_type: str = Field("DOWNLOAD", description="DOWNLOAD | PRINT | SHARE | REPORT")
    reason: str = Field(..., min_length=5, max_length=500)
    destination: str | None = None

    @field_validator("export_type")
    @classmethod
    def validate_export_type(cls, v: str) -> str:
        allowed = {"DOWNLOAD", "PRINT", "SHARE", "REPORT"}
        if v.upper() not in allowed:
            raise ValueError(f"export_type must be one of {allowed}")
        return v.upper()


class ExportResponse(BaseModel):
    id: int
    export_id: str
    evidence_id: int
    actor_username: str | None
    export_type: str
    reason: str
    destination: str | None
    file_hash_at_export: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Evidence Relationship
# ---------------------------------------------------------------------------

class EvidenceRelationshipCreate(BaseModel):
    source_evidence_id: int
    target_evidence_id: int
    relationship_type: str = Field(..., max_length=60)
    description: str | None = None


class EvidenceRelationshipResponse(BaseModel):
    id: int
    source_evidence_id: int
    target_evidence_id: int
    relationship_type: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class EvidenceVersionResponse(BaseModel):
    id: int
    evidence_id: int
    version_number: int
    file_reference: str | None = None
    file_hash: str | None = None
    file_size: int | None = None
    mime_type: str | None = None
    change_summary: str | None = None
    created_by: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProvenanceStep(BaseModel):
    stage: str
    identifier: str
    label: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = {}


class EvidenceProvenanceResponse(BaseModel):
    evidence_id: str
    evidence_type: str
    case_id: int | None
    case_number: str | None
    camera_id: int | None
    track_id: str | None
    match_event_id: int | None
    review_event_id: int | None
    alert_id: int | None
    chain_of_events: list[ProvenanceStep]
    explanation: str


# ---------------------------------------------------------------------------
# Evidence Access Log
# ---------------------------------------------------------------------------

class AccessLogResponse(BaseModel):
    id: int
    evidence_id: int
    actor_username: str | None
    action: str
    access_granted: bool
    denial_reason: str | None
    reason: str | None
    ip_address: str | None
    timestamp: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Evidence Timeline Entry
# ---------------------------------------------------------------------------

class TimelineEntry(BaseModel):
    timestamp: datetime
    actor: str | None
    action: str
    description: str
    resource_type: str
    resource_id: str | None


class EvidenceTimelineResponse(BaseModel):
    evidence_id: str
    case_number: str | None
    entries: list[TimelineEntry]


# ---------------------------------------------------------------------------
# System Audit Log
# ---------------------------------------------------------------------------

class AuditLogResponse(BaseModel):
    id: int
    event_id: str
    actor_username: str | None
    department_id: int | None
    action: str
    resource_type: str
    resource_id: str | None
    resource_label: str | None
    timestamp: datetime
    ip_address: str | None
    reason: str | None
    result: str
    metadata_json: str | None

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Evidence Dashboard Stats
# ---------------------------------------------------------------------------

class EvidenceStatsResponse(BaseModel):
    total_evidence: int
    by_type: dict[str, int]
    by_status: dict[str, int]
    by_classification: dict[str, int]
    integrity_verified: int
    integrity_failed: int
    integrity_pending: int
    recent_accesses: int
    unauthorized_attempts: int
    storage_size_bytes: int


# ---------------------------------------------------------------------------
# Chain of Custody
# ---------------------------------------------------------------------------

class CustodyEvent(BaseModel):
    timestamp: datetime
    actor: str | None
    action: str
    source: str | None
    destination: str | None
    reason: str | None
    integrity_info: str | None


class ChainOfCustodyResponse(BaseModel):
    evidence_id: str
    evidence_type: str
    case_number: str | None
    chain: list[CustodyEvent]
    disclaimer: str = (
        "This chain-of-custody record is an administrative audit trail. "
        "Legal admissibility is determined by applicable laws and judicial review, "
        "not by this system's designation."
    )
