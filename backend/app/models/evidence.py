"""
Module 10 – Evidence Management & Complete Audit Trail ORM Models
=================================================================
Database models for secure evidence storage metadata, versioning,
chain-of-custody relationships, access logging, integrity records,
retention lifecycle, and complete system audit trail.

Design Invariants:
    1. Original evidence is NEVER overwritten — versioning creates a new
       record referencing the original.
    2. Every sensitive access is logged via EvidenceAccessLogDB.
    3. Evidence files are stored in secure local/object storage; this table
       holds metadata and file references only.
    4. Evidence marked FINALIZED must not be silently modified.
    5. AI-generated artefacts (detection crops, embeddings) are clearly
       labelled and distinguished from human decisions.
    6. Retention and deletion follow the configured policy — never hard-coded.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class EvidenceType(str, Enum):
    # Image types
    CCTV_FRAME = "CCTV_FRAME"
    FACE_CROP = "FACE_CROP"
    REFERENCE_IMAGE = "REFERENCE_IMAGE"
    REVIEWER_SNAPSHOT = "REVIEWER_SNAPSHOT"
    EVIDENCE_SNAPSHOT = "EVIDENCE_SNAPSHOT"
    # Video types
    CCTV_CLIP = "CCTV_CLIP"
    INVESTIGATION_CLIP = "INVESTIGATION_CLIP"
    # AI analysis
    AI_DETECTION_METADATA = "AI_DETECTION_METADATA"
    AI_TRACKING_METADATA = "AI_TRACKING_METADATA"
    AI_FEATURE_ANALYSIS = "AI_FEATURE_ANALYSIS"
    AI_CANDIDATE_RANKING = "AI_CANDIDATE_RANKING"
    AI_MODEL_VERSION = "AI_MODEL_VERSION"
    # Review / decision records
    REVIEW_RECORD = "REVIEW_RECORD"
    REVIEW_NOTE = "REVIEW_NOTE"
    EVIDENCE_REQUEST = "EVIDENCE_REQUEST"
    # Alert records
    ALERT_RECORD = "ALERT_RECORD"
    NOTIFICATION_RECORD = "NOTIFICATION_RECORD"
    ACKNOWLEDGMENT_RECORD = "ACKNOWLEDGMENT_RECORD"
    # Documents
    CASE_DOCUMENT = "CASE_DOCUMENT"
    INVESTIGATION_NOTE = "INVESTIGATION_NOTE"
    AUTHORIZED_REPORT = "AUTHORIZED_REPORT"


class EvidenceStatus(str, Enum):
    CAPTURED = "CAPTURED"
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    AVAILABLE = "AVAILABLE"
    RESTRICTED = "RESTRICTED"
    FINALIZED = "FINALIZED"
    ARCHIVED = "ARCHIVED"
    EXPIRED = "EXPIRED"
    DELETED = "DELETED"
    INTEGRITY_FAILED = "INTEGRITY_FAILED"


class EvidenceClassification(str, Enum):
    INTERNAL = "INTERNAL"
    RESTRICTED = "RESTRICTED"
    SENSITIVE = "SENSITIVE"
    HIGHLY_RESTRICTED = "HIGHLY_RESTRICTED"


class IntegrityStatus(str, Enum):
    NOT_VERIFIED = "NOT_VERIFIED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    PENDING = "PENDING"


class AuditAction(str, Enum):
    # Auth
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    LOGIN_FAILED = "LOGIN_FAILED"
    # Case
    CASE_VIEW = "CASE_VIEW"
    CASE_CREATE = "CASE_CREATE"
    CASE_UPDATE = "CASE_UPDATE"
    CASE_ARCHIVE = "CASE_ARCHIVE"
    # Evidence
    EVIDENCE_CREATE = "EVIDENCE_CREATE"
    EVIDENCE_VIEW = "EVIDENCE_VIEW"
    EVIDENCE_DOWNLOAD = "EVIDENCE_DOWNLOAD"
    EVIDENCE_UPDATE = "EVIDENCE_UPDATE"
    EVIDENCE_ARCHIVE = "EVIDENCE_ARCHIVE"
    EVIDENCE_DELETE = "EVIDENCE_DELETE"
    EVIDENCE_FINALIZE = "EVIDENCE_FINALIZE"
    EVIDENCE_EXPORT = "EVIDENCE_EXPORT"
    EVIDENCE_INTEGRITY_CHECK = "EVIDENCE_INTEGRITY_CHECK"
    EVIDENCE_VERSION_CREATE = "EVIDENCE_VERSION_CREATE"
    EVIDENCE_RELATIONSHIP_CREATE = "EVIDENCE_RELATIONSHIP_CREATE"
    # Match / review
    MATCH_VIEW = "MATCH_VIEW"
    REVIEW_START = "REVIEW_START"
    REVIEW_DECISION = "REVIEW_DECISION"
    # Alert
    ALERT_CREATE = "ALERT_CREATE"
    ALERT_VIEW = "ALERT_VIEW"
    ALERT_ACKNOWLEDGE = "ALERT_ACKNOWLEDGE"
    ALERT_STATUS_CHANGE = "ALERT_STATUS_CHANGE"
    # User management
    USER_CREATE = "USER_CREATE"
    USER_UPDATE = "USER_UPDATE"
    PERMISSION_CHANGE = "PERMISSION_CHANGE"
    # Access control
    UNAUTHORIZED_ACCESS_ATTEMPT = "UNAUTHORIZED_ACCESS_ATTEMPT"
    # Retention
    RETENTION_REVIEW = "RETENTION_REVIEW"
    RETENTION_EXPIRE = "RETENTION_EXPIRE"
    RETENTION_ARCHIVE = "RETENTION_ARCHIVE"


class RetentionAction(str, Enum):
    ARCHIVE = "ARCHIVE"
    DELETE = "DELETE"
    REVIEW = "REVIEW"
    EXTEND = "EXTEND"


class ExportType(str, Enum):
    DOWNLOAD = "DOWNLOAD"
    PRINT = "PRINT"
    SHARE = "SHARE"
    REPORT = "REPORT"


# ---------------------------------------------------------------------------
# Evidence Retention Policy
# ---------------------------------------------------------------------------

class EvidenceRetentionPolicyDB(Base):
    """
    Configurable retention policy applied to evidence items.
    Retention periods and actions are set by administrators — never hardcoded.
    """

    __tablename__ = "evidence_retention_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    policy_name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False,
        comment="Human-readable policy label e.g. 'WANTED_CASE_STANDARD'",
    )
    evidence_type: Mapped[str | None] = mapped_column(
        String(60), nullable=True, index=True,
        comment="Optional: applies only to this evidence type. NULL = all types.",
    )
    retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=365,
        comment="Number of days evidence is retained before review",
    )
    action_on_expiry: Mapped[str] = mapped_column(
        String(30), default=RetentionAction.REVIEW.value, nullable=False,
        comment="REVIEW | ARCHIVE | DELETE — never auto-delete without explicit config",
    )
    requires_manual_review: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
        comment="If True, expiration triggers a review task rather than automatic action",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False,
    )

    # Back-references
    evidence_items: Mapped[list[EvidenceItemDB]] = relationship(
        "EvidenceItemDB", back_populates="retention_policy",
    )


# ---------------------------------------------------------------------------
# Evidence Item (primary metadata record)
# ---------------------------------------------------------------------------

class EvidenceItemDB(Base):
    """
    Core evidence metadata record.

    The actual file content lives in secure storage (local or object store).
    This table holds the reference, hash, classification, and lifecycle state.
    Files are never served via public URLs — only authenticated /evidence/{id}/content.
    """

    __tablename__ = "evidence_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    evidence_id: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False,
        comment="Human-readable ID e.g. EVD-2026-000001",
    )

    # Foreign keys to related system entities
    case_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("cases.id"), index=True, nullable=True,
    )
    case_number: Mapped[str | None] = mapped_column(String(30), index=True, nullable=True)
    match_event_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("match_events.id"), index=True, nullable=True,
    )
    review_event_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("review_events.id"), index=True, nullable=True,
    )
    alert_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("alerts.id"), index=True, nullable=True,
    )
    camera_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("cameras.id"), index=True, nullable=True,
    )
    department_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("departments.id"), index=True, nullable=True,
        comment="Owning department (controls access)",
    )

    # Evidence classification
    evidence_type: Mapped[str] = mapped_column(
        String(60), nullable=False, index=True,
    )
    classification: Mapped[str] = mapped_column(
        String(40), default=EvidenceClassification.RESTRICTED.value, nullable=False, index=True,
    )

    # Storage reference (never a public URL)
    file_reference: Mapped[str | None] = mapped_column(
        String(512), nullable=True,
        comment="Secure internal storage path or object-storage key",
    )
    storage_backend: Mapped[str] = mapped_column(
        String(30), default="LOCAL", nullable=False,
        comment="LOCAL | S3 | AZURE_BLOB | GCS etc.",
    )
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Size in bytes",
    )
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Integrity
    hash_algorithm: Mapped[str] = mapped_column(
        String(20), default="SHA-256", nullable=False,
    )
    file_hash: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="Hex-encoded hash of the stored file content",
    )
    integrity_status: Mapped[str] = mapped_column(
        String(30), default=IntegrityStatus.NOT_VERIFIED.value, nullable=False, index=True,
    )
    last_integrity_check_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Lifecycle
    status: Mapped[str] = mapped_column(
        String(30), default=EvidenceStatus.CAPTURED.value, nullable=False, index=True,
    )

    # Timestamps and provenance
    captured_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
        comment="When the evidence was originally captured (e.g. CCTV timestamp)",
    )
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False,
    )

    uploaded_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True,
    )

    # For video clips
    clip_start_time: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
        comment="Start timestamp of the video clip (if evidence type is a video clip)",
    )
    clip_end_time: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
        comment="End timestamp of the video clip",
    )
    clip_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    clip_generation_method: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="How the clip was generated e.g. 'AUTO_WINDOW_±10s' or 'MANUAL_SELECTION'",
    )

    # Track / observation context (for CCTV evidence)
    track_id: Mapped[str | None] = mapped_column(
        String(100), index=True, nullable=True,
        comment="Track ID from Module 5 tracking",
    )
    camera_location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Retention
    retention_policy_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("evidence_retention_policies.id"), nullable=True, index=True,
    )
    retention_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
        comment="Computed expiry date based on policy retention_days",
    )

    # Versioning — points to the original if this is a derived version
    parent_evidence_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("evidence_items.id"), nullable=True, index=True,
        comment="Original evidence this item was derived from (for versioning chain)",
    )
    version_number: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False,
        comment="Version 1 = original; 2+ = derived",
    )
    version_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Description / notes
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="Comma-separated searchable tags",
    )

    # Relationships
    retention_policy: Mapped[EvidenceRetentionPolicyDB | None] = relationship(
        "EvidenceRetentionPolicyDB", back_populates="evidence_items",
    )
    versions: Mapped[list[EvidenceItemDB]] = relationship(
        "EvidenceItemDB",
        primaryjoin="EvidenceItemDB.parent_evidence_id == EvidenceItemDB.id",
        foreign_keys="EvidenceItemDB.parent_evidence_id",
        back_populates="parent",
    )
    parent: Mapped[EvidenceItemDB | None] = relationship(
        "EvidenceItemDB",
        primaryjoin="EvidenceItemDB.id == EvidenceItemDB.parent_evidence_id",
        foreign_keys="EvidenceItemDB.parent_evidence_id",
        back_populates="versions",
        remote_side="EvidenceItemDB.id",
    )
    relationships_as_source: Mapped[list[EvidenceRelationshipDB]] = relationship(
        "EvidenceRelationshipDB",
        foreign_keys="EvidenceRelationshipDB.source_evidence_id",
        back_populates="source_evidence",
        cascade="all, delete-orphan",
    )
    relationships_as_target: Mapped[list[EvidenceRelationshipDB]] = relationship(
        "EvidenceRelationshipDB",
        foreign_keys="EvidenceRelationshipDB.target_evidence_id",
        back_populates="target_evidence",
    )
    access_logs: Mapped[list[EvidenceAccessLogDB]] = relationship(
        "EvidenceAccessLogDB", back_populates="evidence", cascade="all, delete-orphan",
    )
    exports: Mapped[list[EvidenceExportDB]] = relationship(
        "EvidenceExportDB", back_populates="evidence", cascade="all, delete-orphan",
    )
    version_records: Mapped[list[EvidenceVersionDB]] = relationship(
        "EvidenceVersionDB", back_populates="evidence", cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# Evidence Versions (historical version records)
# ---------------------------------------------------------------------------

class EvidenceVersionDB(Base):
    """
    Historical snapshot of an evidence item version.
    Ensures that when an evidence item is revised or a derived version is registered,
    the complete historical version record is preserved.
    """

    __tablename__ = "evidence_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    evidence_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evidence_items.id"), index=True, nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    file_reference: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    evidence: Mapped[EvidenceItemDB] = relationship(
        "EvidenceItemDB", back_populates="version_records",
    )


# ---------------------------------------------------------------------------
# Evidence Relationships (provenance graph)
# ---------------------------------------------------------------------------

class EvidenceRelationshipDB(Base):
    """
    Records the provenance relationship between two evidence items.

    Allows the system to answer: 'Why does this evidence exist and which
    event generated it?' e.g. CCTV_FRAME → FACE_CROP → AI_CANDIDATE_RANKING
    """

    __tablename__ = "evidence_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_evidence_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evidence_items.id"), index=True, nullable=False,
        comment="The evidence item that was the source/cause",
    )
    target_evidence_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evidence_items.id"), index=True, nullable=False,
        comment="The evidence item that was derived/created",
    )
    relationship_type: Mapped[str] = mapped_column(
        String(60), nullable=False,
        comment="e.g. DERIVED_FROM | LINKED_TO | GENERATED_BY | ATTACHED_TO",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True,
    )

    source_evidence: Mapped[EvidenceItemDB] = relationship(
        "EvidenceItemDB",
        foreign_keys=[source_evidence_id],
        back_populates="relationships_as_source",
    )
    target_evidence: Mapped[EvidenceItemDB] = relationship(
        "EvidenceItemDB",
        foreign_keys=[target_evidence_id],
        back_populates="relationships_as_target",
    )


# ---------------------------------------------------------------------------
# Evidence Access Log (every view / download / export)
# ---------------------------------------------------------------------------

class EvidenceAccessLogDB(Base):
    """
    Immutable record of every access to an evidence item.
    No silent downloads — every access is recorded with reason.
    """

    __tablename__ = "evidence_access_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    evidence_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evidence_items.id"), index=True, nullable=False,
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True,
    )
    actor_username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action: Mapped[str] = mapped_column(
        String(60), nullable=False, index=True,
        comment="EVIDENCE_VIEW | EVIDENCE_DOWNLOAD | EVIDENCE_EXPORT | EVIDENCE_INTEGRITY_CHECK",
    )
    access_granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    denial_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reason: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Officer-provided reason for sensitive access (required for downloads)",
    )
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True,
    )
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    evidence: Mapped[EvidenceItemDB] = relationship(
        "EvidenceItemDB", back_populates="access_logs",
    )


# ---------------------------------------------------------------------------
# Evidence Export
# ---------------------------------------------------------------------------

class EvidenceExportDB(Base):
    """
    Records every authorized evidence export event.
    Original evidence is never modified during export.
    """

    __tablename__ = "evidence_exports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    export_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True,
        comment="Human-readable export ID e.g. EXP-2026-000001",
    )
    evidence_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evidence_items.id"), index=True, nullable=False,
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True,
    )
    actor_username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    export_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="DOWNLOAD | PRINT | SHARE | REPORT",
    )
    reason: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Mandatory reason for export",
    )
    destination: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Destination reference (department, system, etc.) — no personal data",
    )
    file_hash_at_export: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="Hash of the exported file at the time of export (integrity snapshot)",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    evidence: Mapped[EvidenceItemDB] = relationship(
        "EvidenceItemDB", back_populates="exports",
    )


# ---------------------------------------------------------------------------
# System-wide Audit Log (expanded from Module 1 AuditLog)
# ---------------------------------------------------------------------------

class SystemAuditLogDB(Base):
    """
    Complete system audit trail recording who did what, when, where, and why.
    This supersedes the minimal AuditLog from Module 1 for full Module 10 compliance.
    Both tables coexist — this provides richer context.
    """

    __tablename__ = "system_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True,
        comment="Human-readable event ID e.g. AUDIT-2026-000145",
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True,
    )
    actor_username: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    department_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=True, index=True,
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    resource_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True,
        comment="String ID to accommodate both integer PKs and string IDs",
    )
    resource_label: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="Human-readable identifier e.g. EVD-2026-000031",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True,
    )
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_state: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="JSON snapshot of resource state before change",
    )
    new_state: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="JSON snapshot of resource state after change",
    )
    result: Mapped[str] = mapped_column(
        String(20), default="SUCCESS", nullable=False, index=True,
        comment="SUCCESS | FAILURE | DENIED",
    )
    metadata_json: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Additional context — must not contain unnecessary personal data",
    )
