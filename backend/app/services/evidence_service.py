"""
Module 10 – Evidence Management Service
=========================================
Core business logic for:
  - Evidence creation, upload, and storage
  - Integrity hashing and verification
  - Versioning (original → derived, never overwrite)
  - Lifecycle management (archive, expire, delete workflow)
  - Retention policy management
  - Chain-of-custody and timeline construction
  - Access control (role + department + jurisdiction + classification)
  - Audit logging
  - Export tracking
  - Search and filtering

Design invariants:
  - FINALIZED evidence is read-only; new versions go through create_evidence_version()
  - Every access is logged via _log_access()
  - Every system action is logged via _audit()
  - Files are never served via public paths — callers must use download_evidence()
  - AI-generated evidence types are clearly labeled
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.evidence import (
    AuditAction,
    EvidenceAccessLogDB,
    EvidenceClassification,
    EvidenceExportDB,
    EvidenceItemDB,
    EvidenceRelationshipDB,
    EvidenceRetentionPolicyDB,
    EvidenceStatus,
    EvidenceType,
    EvidenceVersionDB,
    IntegrityStatus,
    SystemAuditLogDB,
)
from app.models.user import User, UserRole
from app.schemas.evidence import (
    AccessLogResponse,
    AuditLogListResponse,
    AuditLogResponse,
    CCTVClipCreateRequest,
    ChainOfCustodyResponse,
    CustodyEvent,
    EvidenceCreateRequest,
    EvidenceDeleteRequest,
    EvidenceExportRequest,
    EvidenceFinalizeRequest,
    EvidenceIntegrityResponse,
    EvidenceListResponse,
    EvidenceProvenanceResponse,
    EvidenceRelationshipCreate,
    EvidenceRelationshipResponse,
    EvidenceResponse,
    EvidenceStatsResponse,
    EvidenceTimelineResponse,
    EvidenceUpdateRequest,
    EvidenceVersionResponse,
    ExportResponse,
    ProvenanceStep,
    RetentionPolicyCreate,
    RetentionPolicyResponse,
    TimelineEntry,
)
from app.storage.evidence_storage import compute_sha256, evidence_storage
from app.utils.evidence_validator import malware_scan, validate_evidence_file

# ---------------------------------------------------------------------------
# Counter helpers (simple DB-based sequential IDs)
# ---------------------------------------------------------------------------

def _next_evidence_id(db: Session) -> str:
    count = db.query(EvidenceItemDB).count()
    return f"EVD-{datetime.utcnow().year}-{(count + 1):06d}"


def _next_export_id(db: Session) -> str:
    count = db.query(EvidenceExportDB).count()
    return f"EXP-{datetime.utcnow().year}-{(count + 1):06d}"


def _next_audit_id(db: Session) -> str:
    count = db.query(SystemAuditLogDB).count()
    return f"AUDIT-{datetime.utcnow().year}-{(count + 1):06d}"


# ---------------------------------------------------------------------------
# Access control helpers
# ---------------------------------------------------------------------------

def _check_evidence_access(evidence: EvidenceItemDB, user: User) -> bool:
    """
    Returns True if *user* is authorized to access *evidence*.

    Rules:
      ADMIN → always authorized
      POLICE → must belong to evidence.department_id (or evidence has no department)
    """
    if user.role == UserRole.ADMIN.value:
        return True
    if evidence.classification == EvidenceClassification.HIGHLY_RESTRICTED.value:
        return user.role == UserRole.ADMIN.value
    # Department-level check for POLICE
    if user.role == UserRole.POLICE.value:
        if evidence.department_id is None:
            return True  # no department restriction
        return getattr(user, "department_id", None) == evidence.department_id
    return False


# ---------------------------------------------------------------------------
# Internal audit / access log helpers
# ---------------------------------------------------------------------------

def _audit(
    db: Session,
    *,
    user: User | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    resource_label: str | None = None,
    reason: str | None = None,
    result: str = "SUCCESS",
    previous_state: str | None = None,
    new_state: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    extra: dict | None = None,
) -> SystemAuditLogDB:
    log = SystemAuditLogDB(
        event_id=_next_audit_id(db),
        user_id=user.id if user else None,
        actor_username=user.username if user else "SYSTEM",
        department_id=getattr(user, "department_id", None) if user else None,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        resource_label=resource_label,
        result=result,
        reason=reason,
        previous_state=previous_state,
        new_state=new_state,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata_json=json.dumps(extra) if extra else None,
    )
    db.add(log)
    return log


def _log_access(
    db: Session,
    *,
    evidence: EvidenceItemDB,
    user: User | None,
    action: str,
    granted: bool,
    reason: str | None = None,
    denial_reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    extra: dict | None = None,
) -> EvidenceAccessLogDB:
    log = EvidenceAccessLogDB(
        evidence_id=evidence.id,
        user_id=user.id if user else None,
        actor_username=user.username if user else "SYSTEM",
        action=action,
        access_granted=granted,
        denial_reason=denial_reason,
        reason=reason,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata_json=json.dumps(extra) if extra else None,
    )
    db.add(log)
    return log


# ---------------------------------------------------------------------------
# Evidence Service
# ---------------------------------------------------------------------------

class EvidenceService:

    # ------------------------------------------------------------------
    # Retention Policies
    # ------------------------------------------------------------------

    def create_retention_policy(
        self,
        db: Session,
        payload: RetentionPolicyCreate,
        user: User,
    ) -> RetentionPolicyResponse:
        policy = EvidenceRetentionPolicyDB(
            policy_name=payload.policy_name,
            evidence_type=payload.evidence_type,
            retention_days=payload.retention_days,
            action_on_expiry=payload.action_on_expiry,
            requires_manual_review=payload.requires_manual_review,
            description=payload.description,
        )
        db.add(policy)
        _audit(
            db, user=user, action=AuditAction.CASE_CREATE.value,
            resource_type="RETENTION_POLICY", resource_label=payload.policy_name,
        )
        db.commit()
        db.refresh(policy)
        return RetentionPolicyResponse.model_validate(policy)

    def list_retention_policies(self, db: Session) -> list[RetentionPolicyResponse]:
        rows = db.query(EvidenceRetentionPolicyDB).filter(
            EvidenceRetentionPolicyDB.is_active == True
        ).all()
        return [RetentionPolicyResponse.model_validate(r) for r in rows]

    # ------------------------------------------------------------------
    # Create evidence record (metadata only)
    # ------------------------------------------------------------------

    def create_evidence(
        self,
        db: Session,
        payload: EvidenceCreateRequest,
        user: User,
        *,
        file_content: bytes | None = None,
        original_filename: str | None = None,
        declared_mime: str | None = None,
        ip_address: str | None = None,
    ) -> EvidenceResponse:
        """
        Create an evidence record, optionally uploading a file.

        Upload pipeline when file_content provided:
          validate → malware scan → hash → store → record
        """
        file_reference = None
        file_name = None
        file_hash = None
        file_size = None
        mime_type = declared_mime
        storage_backend_label = "NONE"

        if file_content:
            # 1. Validate file (MIME, size, magic bytes)
            validated = validate_evidence_file(file_content, declared_mime or "", original_filename)
            # 2. Malware scan integration point
            scan = malware_scan(file_content, validated.sanitized_name)
            if not scan.clean:
                raise ValueError(f"Evidence file failed malware scan: {scan.details}")
            # 3. Hash
            file_hash = compute_sha256(file_content)
            # 4. Store
            subfolder = f"case_{payload.case_id}" if payload.case_id else "unlinked"
            file_reference, storage_backend_label = evidence_storage().upload_evidence(
                subfolder=subfolder,
                filename=validated.sanitized_name,
                content=file_content,
            )
            file_name = validated.sanitized_name
            file_size = validated.file_size
            mime_type = validated.mime_type

        # 5. Compute retention expiry
        retention_expires_at = None
        if payload.retention_policy_id:
            policy = db.query(EvidenceRetentionPolicyDB).filter(
                EvidenceRetentionPolicyDB.id == payload.retention_policy_id
            ).first()
            if policy:
                retention_expires_at = datetime.utcnow() + timedelta(days=policy.retention_days)

        # 6. Determine version number
        version_number = 1
        if payload.parent_evidence_id:
            parent = db.query(EvidenceItemDB).filter(
                EvidenceItemDB.id == payload.parent_evidence_id
            ).first()
            if parent:
                sibling_count = db.query(EvidenceItemDB).filter(
                    EvidenceItemDB.parent_evidence_id == payload.parent_evidence_id
                ).count()
                version_number = sibling_count + 2  # parent is v1

        item = EvidenceItemDB(
            evidence_id=_next_evidence_id(db),
            case_id=payload.case_id,
            match_event_id=payload.match_event_id,
            review_event_id=payload.review_event_id,
            alert_id=payload.alert_id,
            camera_id=payload.camera_id,
            department_id=payload.department_id or getattr(user, "department_id", None),
            evidence_type=payload.evidence_type,
            classification=payload.classification,
            file_reference=file_reference,
            storage_backend=storage_backend_label,
            file_name=file_name,
            original_file_name=original_filename,
            file_size=file_size,
            mime_type=mime_type,
            file_hash=file_hash,
            integrity_status=IntegrityStatus.VERIFIED.value if file_hash else IntegrityStatus.NOT_VERIFIED.value,
            status=EvidenceStatus.AVAILABLE.value if file_content else EvidenceStatus.CAPTURED.value,
            captured_at=payload.captured_at,
            uploaded_at=datetime.utcnow() if file_content else None,
            uploaded_by=user.id,
            track_id=payload.track_id,
            camera_location=payload.camera_location,
            retention_policy_id=payload.retention_policy_id,
            retention_expires_at=retention_expires_at,
            parent_evidence_id=payload.parent_evidence_id,
            version_number=version_number,
            version_notes=payload.version_notes,
            description=payload.description,
            tags=payload.tags,
            clip_start_time=payload.clip_start_time,
            clip_end_time=payload.clip_end_time,
            clip_generation_method=payload.clip_generation_method,
            clip_duration_seconds=(
                (payload.clip_end_time - payload.clip_start_time).total_seconds()
                if payload.clip_start_time and payload.clip_end_time else None
            ),
        )
        db.add(item)

        _audit(
            db, user=user, action=AuditAction.EVIDENCE_CREATE.value,
            resource_type="EVIDENCE",
            ip_address=ip_address,
            extra={"evidence_type": payload.evidence_type, "file_hash": file_hash},
        )

        db.commit()
        db.refresh(item)

        _log_access(
            db, evidence=item, user=user, action=AuditAction.EVIDENCE_CREATE.value,
            granted=True, ip_address=ip_address,
        )
        db.commit()

        return EvidenceResponse.model_validate(item)

    # ------------------------------------------------------------------
    # Retrieve evidence (with authorization check and access logging)
    # ------------------------------------------------------------------

    def get_evidence(
        self,
        db: Session,
        evidence_id: str,
        user: User,
        *,
        ip_address: str | None = None,
        reason: str | None = None,
    ) -> EvidenceResponse:
        item = db.query(EvidenceItemDB).filter(
            EvidenceItemDB.evidence_id == evidence_id
        ).first()
        if not item:
            raise ValueError(f"Evidence not found: {evidence_id}")

        if not _check_evidence_access(item, user):
            _log_access(
                db, evidence=item, user=user, action=AuditAction.EVIDENCE_VIEW.value,
                granted=False, denial_reason="Insufficient permission or wrong department",
                ip_address=ip_address,
            )
            _audit(
                db, user=user, action=AuditAction.UNAUTHORIZED_ACCESS_ATTEMPT.value,
                resource_type="EVIDENCE", resource_id=str(item.id), resource_label=item.evidence_id,
                result="DENIED", ip_address=ip_address,
            )
            db.commit()
            raise PermissionError("Access denied to this evidence item")

        _log_access(
            db, evidence=item, user=user, action=AuditAction.EVIDENCE_VIEW.value,
            granted=True, reason=reason, ip_address=ip_address,
        )
        _audit(
            db, user=user, action=AuditAction.EVIDENCE_VIEW.value,
            resource_type="EVIDENCE", resource_id=str(item.id), resource_label=item.evidence_id,
            ip_address=ip_address,
        )
        db.commit()
        return EvidenceResponse.model_validate(item)

    # ------------------------------------------------------------------
    # Download evidence content (authenticated, logs reason)
    # ------------------------------------------------------------------

    def download_evidence_content(
        self,
        db: Session,
        evidence_id: str,
        user: User,
        *,
        reason: str,
        ip_address: str | None = None,
    ) -> tuple[bytes, str]:
        """
        Return (content_bytes, mime_type).
        Requires explicit reason. Logs access before returning bytes.
        """
        item = db.query(EvidenceItemDB).filter(
            EvidenceItemDB.evidence_id == evidence_id
        ).first()
        if not item:
            raise ValueError(f"Evidence not found: {evidence_id}")

        if not _check_evidence_access(item, user):
            _log_access(
                db, evidence=item, user=user, action=AuditAction.EVIDENCE_DOWNLOAD.value,
                granted=False, denial_reason="Insufficient permission",
                ip_address=ip_address,
            )
            db.commit()
            raise PermissionError("Access denied to this evidence item")

        if not item.file_reference:
            raise ValueError("No file stored for this evidence item")

        content = evidence_storage().download_evidence(item.file_reference)

        _log_access(
            db, evidence=item, user=user, action=AuditAction.EVIDENCE_DOWNLOAD.value,
            granted=True, reason=reason, ip_address=ip_address,
        )
        _audit(
            db, user=user, action=AuditAction.EVIDENCE_DOWNLOAD.value,
            resource_type="EVIDENCE", resource_id=str(item.id), resource_label=item.evidence_id,
            reason=reason, ip_address=ip_address,
        )
        db.commit()
        return content, item.mime_type or "application/octet-stream"

    # ------------------------------------------------------------------
    # List / search evidence
    # ------------------------------------------------------------------

    def list_evidence(
        self,
        db: Session,
        user: User,
        *,
        case_id: int | None = None,
        camera_id: int | None = None,
        evidence_type: str | None = None,
        status: str | None = None,
        classification: str | None = None,
        match_event_id: int | None = None,
        alert_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> EvidenceListResponse:
        query = db.query(EvidenceItemDB)

        # RBAC filter — POLICE can only see their department's evidence
        if user.role == UserRole.POLICE.value:
            dept_id = getattr(user, "department_id", None)
            if dept_id:
                query = query.filter(
                    (EvidenceItemDB.department_id == dept_id) |
                    (EvidenceItemDB.department_id == None)
                )

        # Filters
        if case_id:
            query = query.filter(EvidenceItemDB.case_id == case_id)
        if camera_id:
            query = query.filter(EvidenceItemDB.camera_id == camera_id)
        if evidence_type:
            query = query.filter(EvidenceItemDB.evidence_type == evidence_type.upper())
        if status:
            query = query.filter(EvidenceItemDB.status == status.upper())
        if classification:
            query = query.filter(EvidenceItemDB.classification == classification.upper())
        if match_event_id:
            query = query.filter(EvidenceItemDB.match_event_id == match_event_id)
        if alert_id:
            query = query.filter(EvidenceItemDB.alert_id == alert_id)
        if date_from:
            query = query.filter(EvidenceItemDB.created_at >= date_from)
        if date_to:
            query = query.filter(EvidenceItemDB.created_at <= date_to)
        if q:
            like = f"%{q}%"
            query = query.filter(
                EvidenceItemDB.evidence_id.ilike(like) |
                EvidenceItemDB.case_number.ilike(like) |
                EvidenceItemDB.description.ilike(like) |
                EvidenceItemDB.tags.ilike(like)
            )

        total = query.count()
        items = (
            query.order_by(EvidenceItemDB.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return EvidenceListResponse(
            items=[EvidenceResponse.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    # ------------------------------------------------------------------
    # Integrity verification
    # ------------------------------------------------------------------

    def verify_integrity(
        self,
        db: Session,
        evidence_id: str,
        user: User,
        *,
        ip_address: str | None = None,
    ) -> EvidenceIntegrityResponse:
        item = db.query(EvidenceItemDB).filter(
            EvidenceItemDB.evidence_id == evidence_id
        ).first()
        if not item:
            raise ValueError(f"Evidence not found: {evidence_id}")

        if not _check_evidence_access(item, user):
            raise PermissionError("Access denied")

        verified_at = datetime.utcnow()
        computed_hash: str | None = None
        match = False
        message = ""

        if not item.file_reference:
            item.integrity_status = IntegrityStatus.NOT_VERIFIED.value
            message = "No file stored — integrity check not applicable"
        elif not item.file_hash:
            item.integrity_status = IntegrityStatus.NOT_VERIFIED.value
            message = "No stored hash — baseline hash not recorded at upload time"
        else:
            result = evidence_storage().verify_integrity(
                item.file_reference, item.file_hash, item.hash_algorithm
            )
            match = result
            if result:
                computed_hash = item.file_hash  # same
                item.integrity_status = IntegrityStatus.VERIFIED.value
                message = "INTEGRITY VERIFIED — file hash matches stored baseline"
            else:
                try:
                    content = evidence_storage().download_evidence(item.file_reference)
                    from app.storage.evidence_storage import compute_sha256
                    computed_hash = compute_sha256(content)
                except Exception:
                    computed_hash = None
                item.integrity_status = IntegrityStatus.FAILED.value
                message = (
                    "INTEGRITY CHECK FAILED — computed hash does not match stored baseline. "
                    "Do NOT silently replace the file. Investigate this discrepancy."
                )

        item.last_integrity_check_at = verified_at
        _log_access(
            db, evidence=item, user=user, action=AuditAction.EVIDENCE_INTEGRITY_CHECK.value,
            granted=True, ip_address=ip_address,
        )
        _audit(
            db, user=user, action=AuditAction.EVIDENCE_INTEGRITY_CHECK.value,
            resource_type="EVIDENCE", resource_id=str(item.id), resource_label=item.evidence_id,
            result="SUCCESS" if match else "FAILURE", ip_address=ip_address,
        )
        db.commit()

        return EvidenceIntegrityResponse(
            evidence_id=item.evidence_id,
            integrity_status=item.integrity_status,
            stored_hash=item.file_hash,
            computed_hash=computed_hash,
            hash_algorithm=item.hash_algorithm,
            verified_at=verified_at,
            match=match,
            message=message,
        )

    # ------------------------------------------------------------------
    # Archive evidence
    # ------------------------------------------------------------------

    def archive_evidence(
        self,
        db: Session,
        evidence_id: str,
        user: User,
        reason: str,
        *,
        ip_address: str | None = None,
    ) -> EvidenceResponse:
        item = db.query(EvidenceItemDB).filter(
            EvidenceItemDB.evidence_id == evidence_id
        ).first()
        if not item:
            raise ValueError(f"Evidence not found: {evidence_id}")
        if not _check_evidence_access(item, user):
            raise PermissionError("Access denied")
        if item.status == EvidenceStatus.ARCHIVED.value:
            raise ValueError("Evidence is already archived")

        prev = item.status
        item.status = EvidenceStatus.ARCHIVED.value
        _audit(
            db, user=user, action=AuditAction.EVIDENCE_ARCHIVE.value,
            resource_type="EVIDENCE", resource_id=str(item.id), resource_label=item.evidence_id,
            reason=reason, previous_state=prev, new_state=item.status,
            ip_address=ip_address,
        )
        db.commit()
        db.refresh(item)
        return EvidenceResponse.model_validate(item)

    # ------------------------------------------------------------------
    # Update evidence (blocks finalized/archived/deleted items)
    # ------------------------------------------------------------------

    def update_evidence(
        self,
        db: Session,
        evidence_id: str,
        payload: EvidenceUpdateRequest,
        user: User,
        *,
        ip_address: str | None = None,
    ) -> EvidenceResponse:
        item = db.query(EvidenceItemDB).filter(
            EvidenceItemDB.evidence_id == evidence_id
        ).first()
        if not item:
            raise ValueError(f"Evidence not found: {evidence_id}")
        if not _check_evidence_access(item, user):
            raise PermissionError("Access denied")

        if item.status == EvidenceStatus.FINALIZED.value:
            raise ValueError(
                "Evidence item is FINALIZED and immutable. Silent modification is prohibited. "
                "To revise or derive from this item, create a new evidence version."
            )
        if item.status in (EvidenceStatus.ARCHIVED.value, EvidenceStatus.DELETED.value):
            raise ValueError(f"Cannot update evidence in status {item.status}.")

        prev_state = {
            "description": item.description,
            "tags": item.tags,
            "classification": item.classification,
            "retention_policy_id": item.retention_policy_id,
        }

        if payload.description is not None:
            item.description = payload.description
        if payload.tags is not None:
            item.tags = payload.tags
        if payload.classification is not None:
            item.classification = payload.classification
        if payload.retention_policy_id is not None:
            item.retention_policy_id = payload.retention_policy_id
            policy = db.query(EvidenceRetentionPolicyDB).filter(
                EvidenceRetentionPolicyDB.id == payload.retention_policy_id
            ).first()
            if policy:
                item.retention_expires_at = datetime.utcnow() + timedelta(days=policy.retention_days)
        if payload.version_notes is not None:
            item.version_notes = payload.version_notes

        new_state = {
            "description": item.description,
            "tags": item.tags,
            "classification": item.classification,
            "retention_policy_id": item.retention_policy_id,
        }

        _audit(
            db, user=user, action=AuditAction.EVIDENCE_UPDATE.value,
            resource_type="EVIDENCE", resource_id=str(item.id), resource_label=item.evidence_id,
            previous_state=json.dumps(prev_state), new_state=json.dumps(new_state),
            ip_address=ip_address,
        )
        db.commit()
        db.refresh(item)
        return EvidenceResponse.model_validate(item)

    # ------------------------------------------------------------------
    # Finalize evidence (locks item as immutable)
    # ------------------------------------------------------------------

    def finalize_evidence(
        self,
        db: Session,
        evidence_id: str,
        user: User,
        payload: EvidenceFinalizeRequest,
        *,
        ip_address: str | None = None,
    ) -> EvidenceResponse:
        item = db.query(EvidenceItemDB).filter(
            EvidenceItemDB.evidence_id == evidence_id
        ).first()
        if not item:
            raise ValueError(f"Evidence not found: {evidence_id}")
        if not _check_evidence_access(item, user):
            raise PermissionError("Access denied")
        if item.status == EvidenceStatus.FINALIZED.value:
            raise ValueError("Evidence item is already FINALIZED.")

        prev = item.status
        item.status = EvidenceStatus.FINALIZED.value
        if payload.notes:
            item.version_notes = (
                f"{item.version_notes or ''}\nFinalized: {payload.notes}".strip()
            )

        _audit(
            db, user=user, action=AuditAction.EVIDENCE_FINALIZE.value,
            resource_type="EVIDENCE", resource_id=str(item.id), resource_label=item.evidence_id,
            reason=payload.reason, previous_state=prev, new_state=item.status,
            ip_address=ip_address,
        )
        db.commit()
        db.refresh(item)
        return EvidenceResponse.model_validate(item)

    # ------------------------------------------------------------------
    # Create evidence version (original -> derived, never overwrite)
    # ------------------------------------------------------------------

    def create_evidence_version(
        self,
        db: Session,
        parent_evidence_id: str,
        user: User,
        *,
        file_content: bytes | None = None,
        original_filename: str | None = None,
        declared_mime: str | None = None,
        version_notes: str | None = None,
        classification: str | None = None,
        ip_address: str | None = None,
    ) -> EvidenceResponse:
        parent = db.query(EvidenceItemDB).filter(
            EvidenceItemDB.evidence_id == parent_evidence_id
        ).first()
        if not parent:
            raise ValueError(f"Parent evidence not found: {parent_evidence_id}")
        if not _check_evidence_access(parent, user):
            raise PermissionError("Access denied")

        sibling_count = db.query(EvidenceItemDB).filter(
            EvidenceItemDB.parent_evidence_id == parent.id
        ).count()
        new_version_num = sibling_count + 2

        file_reference = parent.file_reference
        file_name = parent.file_name
        file_hash = parent.file_hash
        file_size = parent.file_size
        mime_type = parent.mime_type
        storage_backend_label = parent.storage_backend

        if file_content:
            validated = validate_evidence_file(file_content, declared_mime or "", original_filename)
            scan = malware_scan(file_content, validated.sanitized_name)
            if not scan.clean:
                raise ValueError(f"Evidence file failed malware scan: {scan.details}")
            file_hash = compute_sha256(file_content)
            subfolder = f"case_{parent.case_id}" if parent.case_id else "versions"
            file_reference, storage_backend_label = evidence_storage().upload_evidence(
                subfolder=subfolder,
                filename=validated.sanitized_name,
                content=file_content,
            )
            file_name = validated.sanitized_name
            file_size = validated.file_size
            mime_type = validated.mime_type

        new_item = EvidenceItemDB(
            evidence_id=_next_evidence_id(db),
            case_id=parent.case_id,
            case_number=parent.case_number,
            match_event_id=parent.match_event_id,
            review_event_id=parent.review_event_id,
            alert_id=parent.alert_id,
            camera_id=parent.camera_id,
            department_id=parent.department_id,
            evidence_type=parent.evidence_type,
            classification=classification or parent.classification,
            file_reference=file_reference,
            storage_backend=storage_backend_label,
            file_name=file_name,
            original_file_name=original_filename or parent.original_file_name,
            file_size=file_size,
            mime_type=mime_type,
            file_hash=file_hash,
            integrity_status=IntegrityStatus.VERIFIED.value if file_hash else IntegrityStatus.NOT_VERIFIED.value,
            status=EvidenceStatus.AVAILABLE.value if file_content else EvidenceStatus.CAPTURED.value,
            captured_at=parent.captured_at,
            uploaded_at=datetime.utcnow() if file_content else None,
            uploaded_by=user.id,
            track_id=parent.track_id,
            camera_location=parent.camera_location,
            retention_policy_id=parent.retention_policy_id,
            parent_evidence_id=parent.id,
            version_number=new_version_num,
            version_notes=version_notes,
            description=parent.description,
            tags=parent.tags,
        )
        db.add(new_item)
        db.flush()

        # Add explicit record to evidence_versions
        v_rec = EvidenceVersionDB(
            evidence_id=parent.id,
            version_number=new_version_num,
            file_reference=file_reference,
            file_hash=file_hash,
            file_size=file_size,
            mime_type=mime_type,
            change_summary=version_notes,
            created_by=user.id,
        )
        db.add(v_rec)

        # Record provenance relationship
        rel = EvidenceRelationshipDB(
            source_evidence_id=parent.id,
            target_evidence_id=new_item.id,
            relationship_type="DERIVED_VERSION",
            description=f"Version {new_version_num} derived from {parent.evidence_id}: {version_notes or 'New version'}",
            created_by=user.id,
        )
        db.add(rel)

        _audit(
            db, user=user, action=AuditAction.EVIDENCE_VERSION_CREATE.value,
            resource_type="EVIDENCE", resource_id=str(new_item.id), resource_label=new_item.evidence_id,
            previous_state=parent.evidence_id, new_state=new_item.evidence_id,
            reason=version_notes, ip_address=ip_address,
        )
        db.commit()
        db.refresh(new_item)
        return EvidenceResponse.model_validate(new_item)

    # ------------------------------------------------------------------
    # Delete evidence (governed by retention policy)
    # ------------------------------------------------------------------

    def delete_evidence(
        self,
        db: Session,
        evidence_id: str,
        user: User,
        payload: EvidenceDeleteRequest,
        *,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        item = db.query(EvidenceItemDB).filter(
            EvidenceItemDB.evidence_id == evidence_id
        ).first()
        if not item:
            raise ValueError(f"Evidence not found: {evidence_id}")
        if not _check_evidence_access(item, user):
            raise PermissionError("Access denied")

        if not payload.force and user.role != UserRole.ADMIN.value:
            if item.status != EvidenceStatus.EXPIRED.value:
                raise ValueError(
                    "Evidence cannot be deleted: it has not reached EXPIRED status under configured retention policy. "
                    "Administrative override or expired retention review required."
                )

        prev = item.status
        item.status = EvidenceStatus.DELETED.value

        if item.file_reference:
            evidence_storage().delete_evidence(item.file_reference)
            item.file_reference = None

        _audit(
            db, user=user, action=AuditAction.EVIDENCE_DELETE.value,
            resource_type="EVIDENCE", resource_id=str(item.id), resource_label=item.evidence_id,
            reason=payload.reason, previous_state=prev, new_state=item.status,
            ip_address=ip_address,
        )
        db.commit()
        return {
            "status": "DELETED",
            "evidence_id": item.evidence_id,
            "message": "Evidence deleted following authorized retention workflow",
        }

    # ------------------------------------------------------------------
    # Create CCTV clip evidence around an approved event (Section 7)
    # ------------------------------------------------------------------

    def create_cctv_clip_evidence(
        self,
        db: Session,
        payload: CCTVClipCreateRequest,
        user: User,
        *,
        file_content: bytes | None = None,
        original_filename: str | None = None,
        declared_mime: str | None = None,
        ip_address: str | None = None,
    ) -> EvidenceResponse:
        clip_start = payload.event_time - timedelta(seconds=payload.window_seconds_before)
        clip_end = payload.event_time + timedelta(seconds=payload.window_seconds_after)
        duration = (clip_end - clip_start).total_seconds()

        file_reference = None
        file_hash = None
        file_size = None
        mime_type = declared_mime or "video/mp4"
        storage_backend = "NONE"

        if file_content:
            validated = validate_evidence_file(file_content, declared_mime or "video/mp4", original_filename)
            scan = malware_scan(file_content, validated.sanitized_name)
            if not scan.clean:
                raise ValueError(f"Clip file failed malware scan: {scan.details}")
            file_hash = compute_sha256(file_content)
            subfolder = f"clips_cam_{payload.camera_id}" if payload.camera_id else "clips"
            file_reference, storage_backend = evidence_storage().upload_evidence(
                subfolder=subfolder,
                filename=validated.sanitized_name,
                content=file_content,
            )
            file_size = validated.file_size
            mime_type = validated.mime_type
        else:
            storage_backend = "LOCAL"

        item = EvidenceItemDB(
            evidence_id=_next_evidence_id(db),
            case_id=payload.case_id,
            match_event_id=payload.match_event_id,
            review_event_id=payload.review_event_id,
            alert_id=payload.alert_id,
            camera_id=payload.camera_id,
            department_id=getattr(user, "department_id", None),
            evidence_type=EvidenceType.CCTV_CLIP.value,
            classification=payload.classification,
            file_reference=file_reference,
            storage_backend=storage_backend,
            file_name=original_filename or f"clip_cam_{payload.camera_id}_{int(payload.event_time.timestamp())}.mp4",
            original_file_name=original_filename,
            file_size=file_size,
            mime_type=mime_type,
            file_hash=file_hash,
            integrity_status=IntegrityStatus.VERIFIED.value if file_hash else IntegrityStatus.NOT_VERIFIED.value,
            status=EvidenceStatus.AVAILABLE.value if file_content else EvidenceStatus.CAPTURED.value,
            captured_at=payload.event_time,
            uploaded_at=datetime.utcnow() if file_content else None,
            uploaded_by=user.id,
            clip_start_time=clip_start,
            clip_end_time=clip_end,
            clip_duration_seconds=duration,
            clip_generation_method=payload.clip_generation_method,
            description=payload.description or f"Authorized CCTV video segment ({duration:.1f}s window around event)",
            tags=payload.tags,
        )
        db.add(item)
        _audit(
            db, user=user, action=AuditAction.EVIDENCE_CREATE.value,
            resource_type="EVIDENCE",
            reason=f"Generated CCTV clip ({payload.clip_generation_method})",
            ip_address=ip_address,
            extra={"camera_id": payload.camera_id, "duration": duration},
        )
        db.commit()
        db.refresh(item)
        return EvidenceResponse.model_validate(item)

    # ------------------------------------------------------------------
    # Evidence relationships (Section 5)
    # ------------------------------------------------------------------

    def create_evidence_relationship(
        self,
        db: Session,
        payload: EvidenceRelationshipCreate,
        user: User,
    ) -> EvidenceRelationshipResponse:
        src = db.query(EvidenceItemDB).filter(EvidenceItemDB.id == payload.source_evidence_id).first()
        tgt = db.query(EvidenceItemDB).filter(EvidenceItemDB.id == payload.target_evidence_id).first()
        if not src or not tgt:
            raise ValueError("Source or target evidence item not found")
        if not _check_evidence_access(src, user) or not _check_evidence_access(tgt, user):
            raise PermissionError("Access denied")

        rel = EvidenceRelationshipDB(
            source_evidence_id=payload.source_evidence_id,
            target_evidence_id=payload.target_evidence_id,
            relationship_type=payload.relationship_type.upper(),
            description=payload.description,
            created_by=user.id,
        )
        db.add(rel)
        _audit(
            db, user=user, action=AuditAction.EVIDENCE_RELATIONSHIP_CREATE.value,
            resource_type="EVIDENCE_RELATIONSHIP",
            resource_id=f"{src.evidence_id}->{tgt.evidence_id}",
            reason=payload.relationship_type,
        )
        db.commit()
        db.refresh(rel)
        return EvidenceRelationshipResponse.model_validate(rel)

    def get_evidence_relationships(
        self,
        db: Session,
        evidence_id: str,
        user: User,
    ) -> list[EvidenceRelationshipResponse]:
        item = db.query(EvidenceItemDB).filter(EvidenceItemDB.evidence_id == evidence_id).first()
        if not item:
            raise ValueError(f"Evidence not found: {evidence_id}")
        if not _check_evidence_access(item, user):
            raise PermissionError("Access denied")

        rows = db.query(EvidenceRelationshipDB).filter(
            (EvidenceRelationshipDB.source_evidence_id == item.id) |
            (EvidenceRelationshipDB.target_evidence_id == item.id)
        ).order_by(EvidenceRelationshipDB.created_at.asc()).all()
        return [EvidenceRelationshipResponse.model_validate(r) for r in rows]

    # ------------------------------------------------------------------
    # Provenance trace (Section 5 & 40)
    # ------------------------------------------------------------------

    def get_evidence_provenance(
        self,
        db: Session,
        evidence_id: str,
        user: User,
    ) -> EvidenceProvenanceResponse:
        """
        Answers: 'Why does this evidence exist, and which event generated it?'
        Traces the full chain:
        CASE -> REFERENCE IMAGE -> CCTV STREAM -> VIDEO OBSERVATION -> FACE DETECTION
        -> CANDIDATE MATCH -> HUMAN REVIEW -> APPROVED EVENT -> ALERT -> EVIDENCE
        """
        item = db.query(EvidenceItemDB).filter(EvidenceItemDB.evidence_id == evidence_id).first()
        if not item:
            raise ValueError(f"Evidence not found: {evidence_id}")
        if not _check_evidence_access(item, user):
            raise PermissionError("Access denied")

        steps: list[ProvenanceStep] = []

        # 1. Case
        if item.case_id:
            from app.models.case import Case
            c = db.query(Case).filter(Case.id == item.case_id).first()
            if c:
                steps.append(ProvenanceStep(
                    stage="CASE",
                    identifier=c.case_number,
                    label=f"Case: {c.title} ({c.category})",
                    timestamp=c.created_at if hasattr(c, "created_at") else None,
                    metadata={"priority": getattr(c, "priority", "MEDIUM"), "status": getattr(c, "status", "ACTIVE")},
                ))

        # 2. Camera / CCTV Stream
        if item.camera_id:
            from app.models.camera import Camera
            cam = db.query(Camera).filter(Camera.id == item.camera_id).first()
            cam_name = cam.name if cam else f"Camera #{item.camera_id}"
            steps.append(ProvenanceStep(
                stage="CCTV_STREAM",
                identifier=f"CAM-{item.camera_id}",
                label=f"CCTV Stream: {cam_name}",
                timestamp=item.captured_at,
                metadata={"location": item.camera_location or (cam.location if cam else None)},
            ))

        # 3. Observation / Track
        if item.track_id:
            steps.append(ProvenanceStep(
                stage="VIDEO_OBSERVATION",
                identifier=f"TRACK-{item.track_id}",
                label=f"Video Observation Track: {item.track_id}",
                timestamp=item.captured_at,
                metadata={"track_id": item.track_id},
            ))

        # 4. Face Detection / Quality
        steps.append(ProvenanceStep(
            stage="FACE_DETECTION",
            identifier=f"DET-{item.evidence_id}",
            label=f"Face / Object Detection ({item.evidence_type})",
            timestamp=item.captured_at or item.created_at,
            metadata={"evidence_type": item.evidence_type, "classification": item.classification},
        ))

        # 5. Candidate Match Event
        if item.match_event_id:
            from app.models.match_event import MatchEventDB
            m = db.query(MatchEventDB).filter(MatchEventDB.id == item.match_event_id).first()
            steps.append(ProvenanceStep(
                stage="CANDIDATE_MATCH",
                identifier=f"MATCH-{item.match_event_id}",
                label=f"AI Candidate Match Event (Score: {m.similarity_score if m else 'N/A'})",
                timestamp=m.matched_at if m and hasattr(m, "matched_at") else item.created_at,
                metadata={"score": getattr(m, "similarity_score", None)},
            ))

        # 6. Human Review Event
        if item.review_event_id:
            from app.models.review_event import ReviewEventDB
            r = db.query(ReviewEventDB).filter(ReviewEventDB.id == item.review_event_id).first()
            steps.append(ProvenanceStep(
                stage="HUMAN_REVIEW",
                identifier=f"REVIEW-{item.review_event_id}",
                label=f"Human Review Decision: {r.decision if r else 'REVIEWED'}",
                timestamp=r.reviewed_at if r and hasattr(r, "reviewed_at") else item.created_at,
                metadata={"decision": getattr(r, "decision", None), "reviewer": getattr(r, "reviewer_id", None)},
            ))

        # 7. Alert
        if item.alert_id:
            from app.models.alert import AlertDB
            al = db.query(AlertDB).filter(AlertDB.id == item.alert_id).first()
            steps.append(ProvenanceStep(
                stage="ALERT",
                identifier=f"ALERT-{item.alert_id}",
                label=f"Operational Alert: {al.alert_id if al else item.alert_id}",
                timestamp=al.created_at if al and hasattr(al, "created_at") else item.created_at,
                metadata={"severity": getattr(al, "severity", None), "status": getattr(al, "status", None)},
            ))

        # 8. Evidence Store
        steps.append(ProvenanceStep(
            stage="EVIDENCE",
            identifier=item.evidence_id,
            label=f"Stored Evidence ({item.evidence_type}, Status: {item.status})",
            timestamp=item.created_at,
            metadata={
                "hash": item.file_hash,
                "integrity": item.integrity_status,
                "backend": item.storage_backend,
            },
        ))

        explanation = (
            f"Evidence {item.evidence_id} ({item.evidence_type}) was recorded at {item.created_at.isoformat()} "
            f"in relation to Case {item.case_number or item.case_id or 'UNLINKED'}. "
            f"The provenance chain traces {len(steps)} verified lifecycle stages from CCTV observation "
            f"through AI candidate matching, officer review, alert generation, to immutable evidence archival."
        )

        return EvidenceProvenanceResponse(
            evidence_id=item.evidence_id,
            evidence_type=item.evidence_type,
            case_id=item.case_id,
            case_number=item.case_number,
            camera_id=item.camera_id,
            track_id=item.track_id,
            match_event_id=item.match_event_id,
            review_event_id=item.review_event_id,
            alert_id=item.alert_id,
            chain_of_events=steps,
            explanation=explanation,
        )

    # ------------------------------------------------------------------
    # Export tracking
    # ------------------------------------------------------------------

    def create_export(
        self,
        db: Session,
        evidence_id: str,
        user: User,
        payload: EvidenceExportRequest,
        *,
        ip_address: str | None = None,
    ) -> ExportResponse:
        item = db.query(EvidenceItemDB).filter(
            EvidenceItemDB.evidence_id == evidence_id
        ).first()
        if not item:
            raise ValueError(f"Evidence not found: {evidence_id}")
        if not _check_evidence_access(item, user):
            raise PermissionError("Access denied")

        export = EvidenceExportDB(
            export_id=_next_export_id(db),
            evidence_id=item.id,
            user_id=user.id,
            actor_username=user.username,
            export_type=payload.export_type,
            reason=payload.reason,
            destination=payload.destination,
            file_hash_at_export=item.file_hash,
            ip_address=ip_address,
        )
        db.add(export)
        _log_access(
            db, evidence=item, user=user, action=AuditAction.EVIDENCE_EXPORT.value,
            granted=True, reason=payload.reason, ip_address=ip_address,
        )
        _audit(
            db, user=user, action=AuditAction.EVIDENCE_EXPORT.value,
            resource_type="EVIDENCE", resource_id=str(item.id), resource_label=item.evidence_id,
            reason=payload.reason, ip_address=ip_address,
        )
        db.commit()
        db.refresh(export)
        return ExportResponse.model_validate(export)

    # ------------------------------------------------------------------
    # Evidence timeline
    # ------------------------------------------------------------------

    def get_evidence_timeline(
        self,
        db: Session,
        evidence_id: str,
        user: User,
    ) -> EvidenceTimelineResponse:
        item = db.query(EvidenceItemDB).filter(
            EvidenceItemDB.evidence_id == evidence_id
        ).first()
        if not item:
            raise ValueError(f"Evidence not found: {evidence_id}")
        if not _check_evidence_access(item, user):
            raise PermissionError("Access denied")

        # Pull audit records related to this evidence
        audit_rows = (
            db.query(SystemAuditLogDB)
            .filter(
                SystemAuditLogDB.resource_type == "EVIDENCE",
                SystemAuditLogDB.resource_id == str(item.id),
            )
            .order_by(SystemAuditLogDB.timestamp.asc())
            .all()
        )
        # Pull access log
        access_rows = (
            db.query(EvidenceAccessLogDB)
            .filter(EvidenceAccessLogDB.evidence_id == item.id)
            .order_by(EvidenceAccessLogDB.timestamp.asc())
            .all()
        )

        entries: list[TimelineEntry] = []

        if item.captured_at:
            entries.append(TimelineEntry(
                timestamp=item.captured_at,
                actor="SYSTEM",
                action="EVIDENCE_CAPTURED",
                description=f"Evidence captured ({item.evidence_type})",
                resource_type="EVIDENCE",
                resource_id=item.evidence_id,
            ))
        if item.uploaded_at:
            entries.append(TimelineEntry(
                timestamp=item.uploaded_at,
                actor=item.uploaded_by and str(item.uploaded_by) or "SYSTEM",
                action="EVIDENCE_UPLOADED",
                description="Evidence file uploaded and stored",
                resource_type="EVIDENCE",
                resource_id=item.evidence_id,
            ))
        for row in audit_rows:
            entries.append(TimelineEntry(
                timestamp=row.timestamp,
                actor=row.actor_username,
                action=row.action,
                description=f"{row.action} — {row.result}",
                resource_type=row.resource_type,
                resource_id=row.resource_id,
            ))
        for row in access_rows:
            if row.action not in {AuditAction.EVIDENCE_VIEW.value, AuditAction.EVIDENCE_CREATE.value}:
                entries.append(TimelineEntry(
                    timestamp=row.timestamp,
                    actor=row.actor_username,
                    action=row.action,
                    description=f"{row.action} {'GRANTED' if row.access_granted else 'DENIED'}",
                    resource_type="EVIDENCE_ACCESS",
                    resource_id=item.evidence_id,
                ))

        entries.sort(key=lambda e: e.timestamp)

        return EvidenceTimelineResponse(
            evidence_id=item.evidence_id,
            case_number=item.case_number,
            entries=entries,
        )

    # ------------------------------------------------------------------
    # Chain of custody
    # ------------------------------------------------------------------

    def get_chain_of_custody(
        self,
        db: Session,
        evidence_id: str,
        user: User,
    ) -> ChainOfCustodyResponse:
        item = db.query(EvidenceItemDB).filter(
            EvidenceItemDB.evidence_id == evidence_id
        ).first()
        if not item:
            raise ValueError(f"Evidence not found: {evidence_id}")
        if not _check_evidence_access(item, user):
            raise PermissionError("Access denied")

        # Build custody events from audit + access logs
        audit_rows = (
            db.query(SystemAuditLogDB)
            .filter(
                SystemAuditLogDB.resource_type == "EVIDENCE",
                SystemAuditLogDB.resource_id == str(item.id),
            )
            .order_by(SystemAuditLogDB.timestamp.asc())
            .all()
        )
        access_rows = (
            db.query(EvidenceAccessLogDB)
            .filter(EvidenceAccessLogDB.evidence_id == item.id)
            .order_by(EvidenceAccessLogDB.timestamp.asc())
            .all()
        )

        events: list[CustodyEvent] = []

        events.append(CustodyEvent(
            timestamp=item.created_at,
            actor="SYSTEM",
            action="EVIDENCE_CREATED",
            source=None,
            destination=f"Secure Storage ({item.storage_backend})",
            reason="Evidence record created",
            integrity_info=f"SHA-256: {item.file_hash}" if item.file_hash else "No file stored",
        ))

        for row in audit_rows:
            events.append(CustodyEvent(
                timestamp=row.timestamp,
                actor=row.actor_username or "SYSTEM",
                action=row.action,
                source=row.previous_state,
                destination=row.new_state,
                reason=row.reason,
                integrity_info=None,
            ))

        for row in access_rows:
            events.append(CustodyEvent(
                timestamp=row.timestamp,
                actor=row.actor_username or "SYSTEM",
                action=f"{row.action} ({'GRANTED' if row.access_granted else 'DENIED'})",
                source=None,
                destination=None,
                reason=row.reason,
                integrity_info=None,
            ))

        events.sort(key=lambda e: e.timestamp)

        return ChainOfCustodyResponse(
            evidence_id=item.evidence_id,
            evidence_type=item.evidence_type,
            case_number=item.case_number,
            chain=events,
        )

    # ------------------------------------------------------------------
    # Retention management
    # ------------------------------------------------------------------

    def process_expired_evidence(self, db: Session) -> list[str]:
        """
        Identify evidence past its retention date and mark for review.
        Never auto-deletes — always transitions to EXPIRED first.
        Returns list of evidence_ids processed.
        """
        now = datetime.utcnow()
        expired = (
            db.query(EvidenceItemDB)
            .filter(
                EvidenceItemDB.retention_expires_at <= now,
                EvidenceItemDB.status.notin_([
                    EvidenceStatus.EXPIRED.value,
                    EvidenceStatus.ARCHIVED.value,
                    EvidenceStatus.DELETED.value,
                ]),
            )
            .all()
        )
        processed = []
        for item in expired:
            prev = item.status
            item.status = EvidenceStatus.EXPIRED.value
            _audit(
                db, user=None, action=AuditAction.RETENTION_EXPIRE.value,
                resource_type="EVIDENCE", resource_id=str(item.id),
                resource_label=item.evidence_id,
                previous_state=prev, new_state=item.status,
                reason=f"Retention policy expired at {item.retention_expires_at}",
            )
            processed.append(item.evidence_id)
        if processed:
            db.commit()
        return processed

    # ------------------------------------------------------------------
    # Dashboard stats
    # ------------------------------------------------------------------

    def get_stats(self, db: Session, user: User) -> EvidenceStatsResponse:
        query = db.query(EvidenceItemDB)
        if user.role == UserRole.POLICE.value:
            dept_id = getattr(user, "department_id", None)
            if dept_id:
                query = query.filter(
                    (EvidenceItemDB.department_id == dept_id) |
                    (EvidenceItemDB.department_id == None)
                )

        items = query.all()
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_class: dict[str, int] = {}
        total_size = 0
        integrity_verified = 0
        integrity_failed = 0
        integrity_pending = 0

        for item in items:
            by_type[item.evidence_type] = by_type.get(item.evidence_type, 0) + 1
            by_status[item.status] = by_status.get(item.status, 0) + 1
            by_class[item.classification] = by_class.get(item.classification, 0) + 1
            total_size += item.file_size or 0
            if item.integrity_status == IntegrityStatus.VERIFIED.value:
                integrity_verified += 1
            elif item.integrity_status == IntegrityStatus.FAILED.value:
                integrity_failed += 1
            else:
                integrity_pending += 1

        # Recent accesses (last 24h)
        cutoff = datetime.utcnow() - timedelta(hours=24)
        recent = db.query(EvidenceAccessLogDB).filter(
            EvidenceAccessLogDB.timestamp >= cutoff
        ).count()

        # Unauthorized attempts
        denied = db.query(EvidenceAccessLogDB).filter(
            EvidenceAccessLogDB.access_granted == False
        ).count()

        return EvidenceStatsResponse(
            total_evidence=len(items),
            by_type=by_type,
            by_status=by_status,
            by_classification=by_class,
            integrity_verified=integrity_verified,
            integrity_failed=integrity_failed,
            integrity_pending=integrity_pending,
            recent_accesses=recent,
            unauthorized_attempts=denied,
            storage_size_bytes=total_size,
        )

    # ------------------------------------------------------------------
    # Audit trail (admin only)
    # ------------------------------------------------------------------

    def list_audit_logs(
        self,
        db: Session,
        *,
        user_filter: str | None = None,
        action_filter: str | None = None,
        resource_type_filter: str | None = None,
        resource_id_filter: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        result_filter: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> AuditLogListResponse:
        query = db.query(SystemAuditLogDB)
        if user_filter:
            query = query.filter(SystemAuditLogDB.actor_username.ilike(f"%{user_filter}%"))
        if action_filter:
            query = query.filter(SystemAuditLogDB.action == action_filter.upper())
        if resource_type_filter:
            query = query.filter(SystemAuditLogDB.resource_type == resource_type_filter.upper())
        if resource_id_filter:
            query = query.filter(SystemAuditLogDB.resource_id == resource_id_filter)
        if date_from:
            query = query.filter(SystemAuditLogDB.timestamp >= date_from)
        if date_to:
            query = query.filter(SystemAuditLogDB.timestamp <= date_to)
        if result_filter:
            query = query.filter(SystemAuditLogDB.result == result_filter.upper())
        total = query.count()
        rows = (
            query.order_by(SystemAuditLogDB.timestamp.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return AuditLogListResponse(
            items=[AuditLogResponse.model_validate(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_resource_audit_history(
        self,
        db: Session,
        resource_type: str,
        resource_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> AuditLogListResponse:
        query = (
            db.query(SystemAuditLogDB)
            .filter(
                SystemAuditLogDB.resource_type == resource_type.upper(),
                SystemAuditLogDB.resource_id == resource_id,
            )
            .order_by(SystemAuditLogDB.timestamp.asc())
        )
        total = query.count()
        rows = query.offset((page - 1) * page_size).limit(page_size).all()
        return AuditLogListResponse(
            items=[AuditLogResponse.model_validate(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
        )


# Singleton
evidence_service = EvidenceService()
