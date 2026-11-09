"""
Module 9 – Alert & Department Notification System FastAPI Router
================================================================
Exposes REST endpoints for operational alerts, acknowledgment, status transitions,
notification delivery tracking, retries, and Module 8 gated alert generation.

AI Safety Invariants:
    1. Direct algorithmic candidate or similarity results NEVER create alerts.
    2. POST /internal/alerts/create strictly validates source_module == 'MODULE_8'
       and review_status == 'CONFIRMED_FOR_ACTION'.
    3. Biometric feature vectors, high-res faces, and raw CCTV frames are NOT
       exposed in notification endpoints.
    4. Strict Department-level RBAC is enforced on all alert endpoints.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import get_current_user, require_police
from app.models.alert import (
    AlertDB,
    AlertNotificationDB,
    AlertRecipientDB,
    AlertStatus,
    AlertTimelineDB,
)
from app.models.case import Case
from app.models.review_event import ReviewDecision, ReviewEventDB, ReviewStatus
from app.models.user import User, UserRole
from app.schemas.alert import (
    AlertAcknowledgeRequest,
    AlertAuditLogResponse,
    AlertCreateRequest,
    AlertDashboardStatsResponse,
    AlertDetailResponse,
    AlertListResponse,
    AlertNotificationResponse,
    AlertRecipientResponse,
    AlertResponse,
    AlertRetryRequest,
    AlertStatusUpdateRequest,
    AlertTimelineResponse,
)
from app.services.alert_service import alert_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["Module 9 – Alerts & Department Notifications"])
internal_router = APIRouter(prefix="/internal/alerts", tags=["Module 9 – Internal Gated Alert Ingestion"])


# ---------------------------------------------------------------------------
# Helper: Serializing detailed response
# ---------------------------------------------------------------------------

def _build_detail_response(alert: AlertDB, db: Session) -> AlertDetailResponse:
    case = db.query(Case).filter(Case.id == alert.case_id).first()
    review = db.query(ReviewEventDB).filter(ReviewEventDB.id == alert.review_event_id).first()

    recip_responses: List[AlertRecipientResponse] = []
    for r in alert.recipients:
        dept_name = r.alert.originating_department_id if r.alert else None
        recip_responses.append(
            AlertRecipientResponse(
                id=r.id,
                alert_id=r.alert_id,
                department_id=r.department_id,
                department_name=getattr(r, "department_name", None),
                department_code=getattr(r, "department_code", None),
                recipient_type=r.recipient_type,
                delivery_channel=r.delivery_channel,
                destination_reference=r.destination_reference,
                status=r.status,
                sent_at=r.sent_at,
                delivered_at=r.delivered_at,
                acknowledged_at=r.acknowledged_at,
                acknowledged_by=r.acknowledged_by,
            )
        )

    notif_responses = [
        AlertNotificationResponse(
            id=n.id,
            alert_id=n.alert_id,
            recipient_id=n.recipient_id,
            channel=n.channel,
            status=n.status,
            attempt_count=n.attempt_count,
            sent_at=n.sent_at,
            delivered_at=n.delivered_at,
            failed_at=n.failed_at,
            error_code=n.error_code,
            error_message=n.error_message,
            message_payload=n.message_payload,
            created_at=n.created_at,
        )
        for n in alert.notifications
    ]

    timeline_responses = [
        AlertTimelineResponse(
            id=t.id,
            alert_id=t.alert_id,
            timestamp=t.timestamp,
            event_type=t.event_type,
            description=t.description,
            metadata_json=t.metadata_json,
        )
        for t in alert.timeline
    ]

    audit_responses = [
        AlertAuditLogResponse(
            id=a.id,
            alert_id=a.alert_id,
            user_id=a.user_id,
            actor_username=a.actor_username,
            action=a.action,
            previous_status=a.previous_status,
            new_status=a.new_status,
            timestamp=a.timestamp,
            ip_address=a.ip_address,
            metadata_json=a.metadata_json,
        )
        for a in alert.audit_logs
    ]

    return AlertDetailResponse(
        id=alert.id,
        alert_number=alert.alert_number,
        match_event_id=alert.match_event_id,
        review_event_id=alert.review_event_id,
        case_id=alert.case_id,
        case_number=alert.case_number,
        category=alert.category,
        originating_department_id=alert.originating_department_id,
        detected_camera_id=alert.detected_camera_id,
        detected_camera_code=alert.detected_camera_code,
        detected_location=alert.detected_location,
        nearest_department_id=alert.nearest_department_id,
        routing_reason=alert.routing_reason,
        distance_km=alert.distance_km,
        priority=alert.priority,
        status=alert.status,
        observation_count=alert.observation_count,
        last_observation_at=alert.last_observation_at,
        created_at=alert.created_at,
        acknowledged_at=alert.acknowledged_at,
        closed_at=alert.closed_at,
        case_title=case.title if case else None,
        person_identifier=case.person_identifier if case else None,
        case_priority=case.priority if case else None,
        examiner_username=None,
        decision_notes=review.decision_notes if review else None,
        similarity_score=review.similarity_score if review else None,
        recipients=recip_responses,
        notifications=notif_responses,
        timeline=timeline_responses,
        audit_logs=audit_responses,
    )


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------


@router.get(
    "/dashboard/stats",
    response_model=AlertDashboardStatsResponse,
    summary="Get operational alert dashboard statistics",
)
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stats = alert_service.get_dashboard_stats(db, current_user)
    return AlertDashboardStatsResponse(**stats)


@router.get(
    "",
    response_model=AlertListResponse,
    summary="List operational alerts with pagination and department authorization",
)
async def list_alerts(
    case_number: Optional[str] = Query(None, description="Filter by case number"),
    category: Optional[str] = Query(None, description="MISSING or WANTED"),
    status: Optional[str] = Query(None, description="Filter by alert status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    camera_id: Optional[int] = Query(None, description="Filter by camera ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = alert_service.list_alerts(
        db=db,
        user=current_user,
        case_number=case_number,
        category=category,
        status=status,
        priority=priority,
        department_id=department_id,
        camera_id=camera_id,
        page=page,
        page_size=page_size,
    )
    pages = (total + page_size - 1) // page_size if total > 0 else 1
    return AlertListResponse(
        items=[AlertResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/{alert_id}",
    response_model=AlertDetailResponse,
    summary="Get full alert details with recipients, timeline, and audit logs",
)
async def get_alert_detail(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        alert = alert_service.get_alert_by_id(alert_id, current_user, db)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id} not found.")

    return _build_detail_response(alert, db)


@router.post(
    "/{alert_id}/acknowledge",
    response_model=AlertDetailResponse,
    summary="Acknowledge an operational alert by authorized department officer",
)
async def acknowledge_alert(
    alert_id: int,
    payload: AlertAcknowledgeRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    client_ip = request.client.host if request.client else None
    try:
        alert = await alert_service.acknowledge_alert(
            alert_id=alert_id,
            user=current_user,
            notes=payload.notes,
            ip_address=client_ip,
            db=db,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return _build_detail_response(alert, db)


@router.post(
    "/{alert_id}/status",
    response_model=AlertDetailResponse,
    summary="Update operational status of an alert (IN_PROGRESS, RESOLVED, CLOSED)",
)
async def update_alert_status(
    alert_id: int,
    payload: AlertStatusUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    client_ip = request.client.host if request.client else None
    try:
        alert = await alert_service.update_alert_status(
            alert_id=alert_id,
            new_status=payload.status,
            user=current_user,
            notes=payload.notes,
            ip_address=client_ip,
            db=db,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return _build_detail_response(alert, db)


@router.get(
    "/{alert_id}/timeline",
    response_model=List[AlertTimelineResponse],
    summary="Retrieve chronological timeline milestones of an alert",
)
async def get_alert_timeline(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        alert = alert_service.get_alert_by_id(alert_id, current_user, db)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id} not found.")

    return [AlertTimelineResponse.model_validate(t) for t in alert.timeline]


@router.get(
    "/{alert_id}/notifications",
    response_model=List[AlertNotificationResponse],
    summary="Retrieve multi-channel notification transmission and delivery records",
)
async def get_alert_notifications(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        alert = alert_service.get_alert_by_id(alert_id, current_user, db)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id} not found.")

    return [AlertNotificationResponse.model_validate(n) for n in alert.notifications]


@router.post(
    "/{alert_id}/retry",
    response_model=List[AlertNotificationResponse],
    summary="Retry transmission of failed notifications",
)
async def retry_alert_notifications(
    alert_id: int,
    payload: AlertRetryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    try:
        retried = await alert_service.retry_failed_notifications(
            alert_id=alert_id,
            user=current_user,
            notification_id=payload.notification_id,
            db=db,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return [AlertNotificationResponse.model_validate(n) for n in retried]


# ---------------------------------------------------------------------------
# Section 23: Internal Gated Alert Ingestion API
# ---------------------------------------------------------------------------


@internal_router.post(
    "/create",
    response_model=AlertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create alert from Module 8 approved event (GATED ON HUMAN VERIFICATION)",
)
async def create_alert_from_module8(
    payload: AlertCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    """
    STRICT SAFETY VALIDATION:
    1. source_module MUST be MODULE_8
    2. review_status MUST be CONFIRMED_FOR_ACTION
    3. review_event record in DB must exist and be CONFIRMED_FOR_ACTION
    4. match_event_id and case_id must exist
    """
    if payload.source_module != "MODULE_8":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Source module '{payload.source_module}' rejected. "
                "Operational alerts can ONLY originate from 'MODULE_8'."
            ),
        )

    if payload.review_status != "CONFIRMED_FOR_ACTION":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Review status '{payload.review_status}' rejected. "
                "Operational alerts require authorized human approval 'CONFIRMED_FOR_ACTION'."
            ),
        )

    review_event = db.query(ReviewEventDB).filter(ReviewEventDB.id == payload.review_event_id).first()
    if not review_event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ReviewEvent with ID {payload.review_event_id} not found.",
        )

    if review_event.status != ReviewStatus.CONFIRMED_FOR_ACTION.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Review event {review_event.id} database status is '{review_event.status}', "
                "not 'CONFIRMED_FOR_ACTION'. Automated candidate signals cannot trigger alerts."
            ),
        )

    client_ip = request.client.host if request.client else None
    try:
        alert = await alert_service.create_alert_from_review_event(
            review_event=review_event,
            db=db,
            actor=current_user,
            custom_priority=payload.priority.value if payload.priority else None,
            notes=payload.notes,
            ip_address=client_ip,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return AlertResponse.model_validate(alert)
