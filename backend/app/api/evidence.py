"""
Module 10 – Evidence Management API Router
===========================================
All evidence-related endpoints. Files are NEVER served via public URLs —
only via authenticated /evidence/{id}/content with explicit access logging.

Endpoints:
  GET  /evidence                          — List/search authorized evidence
  GET  /evidence/stats                    — Evidence dashboard statistics
  POST /evidence                          — Create evidence (multipart upload)
  GET  /evidence/{evidence_id}            — Get evidence metadata
  GET  /evidence/{evidence_id}/access     — Get access log for evidence
  GET  /evidence/{evidence_id}/integrity  — Verify evidence integrity
  GET  /evidence/{evidence_id}/timeline   — Get evidence timeline
  GET  /evidence/{evidence_id}/custody    — Get chain of custody
  GET  /evidence/{evidence_id}/content    — Download evidence content
  POST /evidence/{evidence_id}/archive    — Archive evidence
  POST /evidence/{evidence_id}/export     — Create authorized export event

  GET  /evidence/retention/policies       — List retention policies
  POST /evidence/retention/policies       — Create retention policy (ADMIN)

  GET  /audit                             — System audit log (ADMIN)
  GET  /audit/{resource_type}/{resource_id} — Resource audit history (ADMIN)
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, UploadFile, File, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import get_current_user, require_admin, require_police
from app.models.user import User
from app.schemas.evidence import (
    AccessLogResponse,
    AuditLogListResponse,
    AuditLogResponse,
    CCTVClipCreateRequest,
    ChainOfCustodyResponse,
    EvidenceArchiveRequest,
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
    RetentionPolicyCreate,
    RetentionPolicyResponse,
)
from app.services.evidence_service import evidence_service

router = APIRouter(tags=["Module 10 – Evidence Management"])
audit_router = APIRouter(tags=["Module 10 – Audit Trail"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# ---------------------------------------------------------------------------
# Evidence CRUD
# ---------------------------------------------------------------------------

@router.get("/evidence/stats", response_model=EvidenceStatsResponse, summary="Evidence dashboard statistics")
def get_evidence_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    """Evidence dashboard KPI statistics (role-filtered)."""
    return evidence_service.get_stats(db, current_user)


@router.get("/evidence", response_model=EvidenceListResponse, summary="List and search authorized evidence")
def list_evidence(
    case_id: int | None = Query(None),
    camera_id: int | None = Query(None),
    evidence_type: str | None = Query(None),
    status: str | None = Query(None),
    classification: str | None = Query(None),
    match_event_id: int | None = Query(None),
    alert_id: int | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    q: str | None = Query(None, description="Search by evidence ID, case number, description, or tags"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    """List and filter evidence items authorized for the current user."""
    return evidence_service.list_evidence(
        db, current_user,
        case_id=case_id, camera_id=camera_id, evidence_type=evidence_type,
        status=status, classification=classification, match_event_id=match_event_id,
        alert_id=alert_id, date_from=date_from, date_to=date_to, q=q,
        page=page, page_size=page_size,
    )


@router.post("/evidence", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED,
             summary="Create evidence record with optional file upload")
async def create_evidence(
    request: Request,
    evidence_type: str = Form(...),
    case_id: int | None = Form(None),
    match_event_id: int | None = Form(None),
    review_event_id: int | None = Form(None),
    alert_id: int | None = Form(None),
    camera_id: int | None = Form(None),
    classification: str = Form("RESTRICTED"),
    description: str | None = Form(None),
    tags: str | None = Form(None),
    captured_at: datetime | None = Form(None),
    track_id: str | None = Form(None),
    camera_location: str | None = Form(None),
    retention_policy_id: int | None = Form(None),
    parent_evidence_id: int | None = Form(None),
    version_notes: str | None = Form(None),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    """
    Create an evidence record. Optionally attach a file.
    Files undergo size, MIME, magic-byte, and malware validation.
    """
    payload = EvidenceCreateRequest(
        evidence_type=evidence_type,
        case_id=case_id,
        match_event_id=match_event_id,
        review_event_id=review_event_id,
        alert_id=alert_id,
        camera_id=camera_id,
        classification=classification,
        description=description,
        tags=tags,
        captured_at=captured_at,
        track_id=track_id,
        camera_location=camera_location,
        retention_policy_id=retention_policy_id,
        parent_evidence_id=parent_evidence_id,
        version_notes=version_notes,
    )

    file_content = None
    original_filename = None
    declared_mime = None

    if file and file.filename:
        file_content = await file.read()
        original_filename = file.filename
        declared_mime = file.content_type or ""

    try:
        return evidence_service.create_evidence(
            db, payload, current_user,
            file_content=file_content,
            original_filename=original_filename,
            declared_mime=declared_mime,
            ip_address=_ip(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("/evidence/{evidence_id}", response_model=EvidenceResponse, summary="Get evidence metadata")
def get_evidence(
    evidence_id: str,
    request: Request,
    reason: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    """Retrieve evidence metadata. Access is logged."""
    try:
        return evidence_service.get_evidence(db, evidence_id, current_user, ip_address=_ip(request), reason=reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.put("/evidence/{evidence_id}", response_model=EvidenceResponse, summary="Update evidence metadata")
def update_evidence(
    evidence_id: str,
    request: Request,
    payload: EvidenceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    """
    Update mutable fields of evidence. Finalized items are immutable and will be rejected.
    """
    try:
        return evidence_service.update_evidence(db, evidence_id, payload, current_user, ip_address=_ip(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/evidence/{evidence_id}/finalize", response_model=EvidenceResponse,
             summary="Finalize evidence (lock as immutable)")
def finalize_evidence(
    evidence_id: str,
    request: Request,
    payload: EvidenceFinalizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    """
    Mark evidence as FINALIZED. Once finalized, content and metadata cannot be modified.
    Subsequent changes require creating a new derived evidence version.
    """
    try:
        return evidence_service.finalize_evidence(db, evidence_id, current_user, payload, ip_address=_ip(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/evidence/{evidence_id}/version", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED,
             summary="Create derived evidence version")
async def create_evidence_version(
    evidence_id: str,
    request: Request,
    version_notes: str | None = Form(None),
    classification: str | None = Form(None),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    """
    Create a new version derived from an existing evidence item.
    Never overwrites the original evidence record.
    """
    file_content = None
    original_filename = None
    declared_mime = None
    if file and file.filename:
        file_content = await file.read()
        original_filename = file.filename
        declared_mime = file.content_type or ""

    try:
        return evidence_service.create_evidence_version(
            db,
            evidence_id,
            current_user,
            file_content=file_content,
            original_filename=original_filename,
            declared_mime=declared_mime,
            version_notes=version_notes,
            classification=classification,
            ip_address=_ip(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.delete("/evidence/{evidence_id}", summary="Delete evidence following retention policy")
def delete_evidence(
    evidence_id: str,
    request: Request,
    payload: EvidenceDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    """
    Delete evidence following configured retention policy.
    Requires retention period expiry or administrative force override.
    """
    try:
        return evidence_service.delete_evidence(db, evidence_id, current_user, payload, ip_address=_ip(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/evidence/cctv-clip", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED,
             summary="Create CCTV video clip evidence around an approved event")
async def create_cctv_clip(
    request: Request,
    case_id: int | None = Form(None),
    camera_id: int | None = Form(None),
    stream_id: str | None = Form(None),
    event_time: datetime = Form(...),
    window_seconds_before: float = Form(10.0),
    window_seconds_after: float = Form(10.0),
    match_event_id: int | None = Form(None),
    review_event_id: int | None = Form(None),
    alert_id: int | None = Form(None),
    classification: str = Form("RESTRICTED"),
    description: str | None = Form(None),
    tags: str | None = Form(None),
    clip_generation_method: str = Form("AUTO_WINDOW_APPROVED_EVENT"),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    """
    Create a video segment around an approved detection event.
    Configurable time window (e.g. ±10s around event timestamp).
    """
    payload = CCTVClipCreateRequest(
        case_id=case_id,
        camera_id=camera_id,
        stream_id=stream_id,
        event_time=event_time,
        window_seconds_before=window_seconds_before,
        window_seconds_after=window_seconds_after,
        match_event_id=match_event_id,
        review_event_id=review_event_id,
        alert_id=alert_id,
        classification=classification,
        description=description,
        tags=tags,
        clip_generation_method=clip_generation_method,
    )
    file_content = None
    original_filename = None
    declared_mime = None
    if file and file.filename:
        file_content = await file.read()
        original_filename = file.filename
        declared_mime = file.content_type or "video/mp4"

    try:
        return evidence_service.create_cctv_clip_evidence(
            db, payload, current_user,
            file_content=file_content,
            original_filename=original_filename,
            declared_mime=declared_mime,
            ip_address=_ip(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/evidence/relationships", response_model=EvidenceRelationshipResponse, status_code=status.HTTP_201_CREATED,
             summary="Link evidence items in a relationship")
def create_relationship(
    payload: EvidenceRelationshipCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    """Record a provenance relationship between two evidence items."""
    try:
        return evidence_service.create_evidence_relationship(db, payload, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/evidence/{evidence_id}/relationships", response_model=list[EvidenceRelationshipResponse],
            summary="Get relationships for an evidence item")
def get_relationships(
    evidence_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    try:
        return evidence_service.get_evidence_relationships(db, evidence_id, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/evidence/{evidence_id}/provenance", response_model=EvidenceProvenanceResponse,
            summary="Get full evidence provenance trace")
def get_provenance(
    evidence_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    """
    Answers: 'Why does this evidence exist, and which event generated it?'
    Traces from CCTV Stream -> Observation -> Detection -> Match -> Review -> Alert -> Evidence.
    """
    try:
        return evidence_service.get_evidence_provenance(db, evidence_id, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/evidence/{evidence_id}/content", summary="Download evidence file content (authenticated)")
def download_evidence_content(
    evidence_id: str,
    request: Request,
    reason: str = Query(..., min_length=5, description="Mandatory reason for downloading evidence"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    """
    Download evidence file bytes. Files are NEVER served via public URLs.
    Requires explicit reason. Access is logged.
    """
    try:
        content, mime_type = evidence_service.download_evidence_content(
            db, evidence_id, current_user, reason=reason, ip_address=_ip(request)
        )
        return Response(
            content=content,
            media_type=mime_type,
            headers={"X-Evidence-ID": evidence_id, "X-Content-Disposition": "attachment"},
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/evidence/{evidence_id}/access", response_model=list[AccessLogResponse],
            summary="Get evidence access log")
def get_access_log(
    evidence_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    """Return access log for an evidence item (must have access to the item)."""
    from app.models.evidence import EvidenceItemDB, EvidenceAccessLogDB
    item = db.query(EvidenceItemDB).filter(EvidenceItemDB.evidence_id == evidence_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Evidence not found")
    from app.services.evidence_service import _check_evidence_access
    if not _check_evidence_access(item, current_user):
        raise HTTPException(status_code=403, detail="Access denied")
    rows = (
        db.query(EvidenceAccessLogDB)
        .filter(EvidenceAccessLogDB.evidence_id == item.id)
        .order_by(EvidenceAccessLogDB.timestamp.desc())
        .limit(200)
        .all()
    )
    return [AccessLogResponse.model_validate(r) for r in rows]


@router.get("/evidence/{evidence_id}/integrity", response_model=EvidenceIntegrityResponse,
            summary="Verify evidence file integrity")
def verify_integrity(
    evidence_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    """
    Re-compute and compare the file hash against the stored baseline.
    Returns INTEGRITY VERIFIED or INTEGRITY CHECK FAILED.
    """
    try:
        return evidence_service.verify_integrity(db, evidence_id, current_user, ip_address=_ip(request))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/evidence/{evidence_id}/timeline", response_model=EvidenceTimelineResponse,
            summary="Get evidence lifecycle timeline")
def get_evidence_timeline(
    evidence_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    """Chronological timeline of all events related to an evidence item."""
    try:
        return evidence_service.get_evidence_timeline(db, evidence_id, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/evidence/{evidence_id}/custody", response_model=ChainOfCustodyResponse,
            summary="Get chain-of-custody record")
def get_chain_of_custody(
    evidence_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    """
    Chain-of-custody style audit trail for an evidence item.
    Disclaimer: administrative record only — not an automatic legal admissibility guarantee.
    """
    try:
        return evidence_service.get_chain_of_custody(db, evidence_id, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/evidence/{evidence_id}/archive", response_model=EvidenceResponse, summary="Archive evidence")
def archive_evidence(
    evidence_id: str,
    request: Request,
    payload: EvidenceArchiveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    """Archive an evidence item. Original record is preserved."""
    try:
        return evidence_service.archive_evidence(
            db, evidence_id, current_user, payload.reason, ip_address=_ip(request)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/evidence/{evidence_id}/export", response_model=ExportResponse,
             summary="Create authorized evidence export event")
def create_export(
    evidence_id: str,
    request: Request,
    payload: EvidenceExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    """
    Record an authorized export event. Original evidence is unchanged.
    Reason is mandatory for all exports.
    """
    try:
        return evidence_service.create_export(
            db, evidence_id, current_user, payload, ip_address=_ip(request)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


# ---------------------------------------------------------------------------
# Retention Policies
# ---------------------------------------------------------------------------

@router.get("/evidence/retention/policies", response_model=list[RetentionPolicyResponse],
            summary="List retention policies")
def list_retention_policies(db: Session = Depends(get_db), _: User = Depends(require_police)):
    return evidence_service.list_retention_policies(db)


@router.post("/evidence/retention/policies", response_model=RetentionPolicyResponse,
             status_code=status.HTTP_201_CREATED, summary="Create retention policy (ADMIN)")
def create_retention_policy(
    payload: RetentionPolicyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a new evidence retention policy. Requires ADMIN role."""
    try:
        return evidence_service.create_retention_policy(db, payload, current_user)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/evidence/retention/process-expired", summary="Trigger retention expiration check (ADMIN)")
def process_expired_retention(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Process evidence items that have exceeded their configured retention period.
    Items transition to EXPIRED for authorized retention workflow — never deleted silently.
    """
    processed = evidence_service.process_expired_evidence(db)
    return {
        "processed_count": len(processed),
        "expired_evidence_ids": processed,
        "message": f"Processed {len(processed)} expired evidence items according to retention policy.",
    }


# ---------------------------------------------------------------------------
# Audit Trail
# ---------------------------------------------------------------------------

@audit_router.get("/audit", response_model=AuditLogListResponse, summary="System audit log (ADMIN)")
def list_audit_logs(
    user_filter: str | None = Query(None, alias="user"),
    action_filter: str | None = Query(None, alias="action"),
    resource_type_filter: str | None = Query(None, alias="resource_type"),
    resource_id_filter: str | None = Query(None, alias="resource_id"),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    result_filter: str | None = Query(None, alias="result"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Full system audit log. Restricted to ADMIN role.
    Provides filters by user, action, resource type, date, and result.
    """
    return evidence_service.list_audit_logs(
        db,
        user_filter=user_filter, action_filter=action_filter,
        resource_type_filter=resource_type_filter, resource_id_filter=resource_id_filter,
        date_from=date_from, date_to=date_to, result_filter=result_filter,
        page=page, page_size=page_size,
    )


@audit_router.get("/audit/{resource_type}/{resource_id}", response_model=AuditLogListResponse,
                  summary="Get audit history of a specific resource (ADMIN)")
def get_resource_audit_history(
    resource_type: str,
    resource_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Retrieve the complete audit history for a specific resource (ADMIN only)."""
    return evidence_service.get_resource_audit_history(
        db, resource_type, resource_id, page=page, page_size=page_size
    )
