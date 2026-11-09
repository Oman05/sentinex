"""
Module 8 – Human Verification & Investigation Dashboard API Router
==================================================================
REST endpoints for authorized examiners to review AI-generated possible
match events, submit decisions, manage investigation tasks, and view
the full audit history.

AI Safety Invariant:
    The AI system NEVER autonomously confirms identity.
    All review decisions are made by authorized human examiners.
    Similarity scores are algorithmic signals only.

Endpoints:
    GET    /review/events                           – list pending/all review events
    POST   /review/events/ingest                   – ingest a new match event (internal hook)
    GET    /review/events/{id}                     – get event detail
    POST   /review/events/{id}/start               – claim and start reviewing
    POST   /review/events/{id}/decision            – submit examiner decision
    POST   /review/events/{id}/evidence-request    – request more evidence
    POST   /review/events/{id}/assign              – assign to another examiner
    GET    /review/events/{id}/history             – full audit history
    GET    /review/tasks                           – list investigation tasks
    POST   /review/tasks                           – create investigation task
    PATCH  /review/tasks/{task_id}                 – update task status/assignment
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_police
from app.database.session import get_db
from app.models.user import User
from app.schemas.review import (
    AssignRequest,
    EvidenceRequestRequest,
    InvestigationTaskCreate,
    InvestigationTaskResponse,
    Module9NotificationPayload,
    ReviewAuditEntry,
    ReviewDashboardStats,
    ReviewDecisionRequest,
    ReviewEventDetail,
    ReviewEventSummary,
    ReviewHistory,
    StartReviewRequest,
    TaskUpdateRequest,
    NotificationItem,
    TrackHistory,
)
from app.services.review_service import review_service, _now

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/review",
    tags=["Module 8 – Human Verification & Investigation Dashboard"],
)


# ---------------------------------------------------------------------------
# Helper to extract client IP
# ---------------------------------------------------------------------------


def _get_client_ip(request: Request) -> Optional[str]:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


# ---------------------------------------------------------------------------
# Dashboard Analytics & Stats
# ---------------------------------------------------------------------------


@router.get(
    "/dashboard/stats",
    response_model=ReviewDashboardStats,
    summary="Get Review & Investigation Dashboard Aggregate Statistics",
    description=(
        "Returns aggregate queue metrics, category breakdown, task counts, "
        "and mandatory AI safety disclaimer."
    ),
)
@router.get(
    "/stats",
    response_model=ReviewDashboardStats,
    include_in_schema=False,
)
async def get_dashboard_stats(
    current_user: User = Depends(require_police),
    db: Session = Depends(get_db),
) -> ReviewDashboardStats:
    return review_service.get_dashboard_stats(db=db)


# ---------------------------------------------------------------------------
# Review Events – List & Ingest
# ---------------------------------------------------------------------------


@router.get(
    "/events",
    response_model=list[ReviewEventSummary],
    summary="List Human Verification Queue Events",
    description=(
        "Returns possible match events awaiting or under authorized human review. "
        "Supports filtering by status, category, case, or assigned examiner. "
        "Similarity scores are algorithmic signals only — not identity assertions."
    ),
)
@router.get(
    "",
    response_model=list[ReviewEventSummary],
    include_in_schema=False,
)
async def list_review_events(
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="PENDING_REVIEW | UNDER_REVIEW | CONFIRMED_FOR_ACTION | REJECTED | NEED_MORE_EVIDENCE",
    ),
    category: Optional[str] = Query(
        default=None,
        pattern="^(MISSING|WANTED)$",
        description="Filter by case category.",
    ),
    case_id: Optional[int] = Query(default=None, description="Filter by case ID."),
    assigned_to: Optional[int] = Query(default=None, description="Filter by assigned examiner user ID."),
    search: Optional[str] = Query(default=None, description="Search case_number, match_event_id, track_id"),
    priority: Optional[str] = Query(default=None, description="Filter by priority"),
    camera_id: Optional[int] = Query(default=None, description="Filter by camera ID"),
    date_from: Optional[datetime] = Query(default=None, description="Filter from date"),
    date_to: Optional[datetime] = Query(default=None, description="Filter to date"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_police),
    db: Session = Depends(get_db),
) -> list[ReviewEventSummary]:
    rows = review_service.list_events(
        db=db,
        status=status_filter,
        category=category,
        case_id=case_id,
        assigned_to=assigned_to,
        search=search,
        priority=priority,
        camera_id=camera_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return [ReviewEventSummary.model_validate(r) for r in rows]


@router.post(
    "/events/ingest",
    response_model=ReviewEventDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a Module 7 Match Event into the Review Queue",
    description=(
        "Internal hook called by Module 7 (or administrators) to enqueue a "
        "PossibleMatchEvent for authorized human verification. Idempotent by match_event_id."
    ),
)
async def ingest_match_event(
    payload: ReviewEventIngestRequest,
    current_user: User = Depends(require_police),
    db: Session = Depends(get_db),
) -> ReviewEventDetail:
    """Create a ReviewEvent from a Module 7 match event payload."""
    row = review_service.create_review_event(
        match_event_id=payload.match_event_id,
        case_id=payload.case_id,
        case_number=payload.case_number,
        category=payload.category,
        similarity_score=payload.similarity_score,
        candidate_ranking_score=payload.candidate_ranking_score,
        query_quality_score=payload.query_quality_score,
        rank=payload.rank,
        decision_state=payload.decision_state,
        camera_id=payload.camera_id,
        camera_location=payload.camera_location,
        track_id=payload.track_id,
        model_name=payload.model_name,
        model_version=payload.model_version,
        priority=payload.priority,
        face_quality_label=payload.face_quality_label,
        observation_count=payload.observation_count,
        detection_quality_score=payload.detection_quality_score,
        db=db,
    )
    return ReviewEventDetail.model_validate(row)


# ---------------------------------------------------------------------------
# Review Events – Detail
# ---------------------------------------------------------------------------


@router.get(
    "/events/{event_id}",
    response_model=ReviewEventDetail,
    summary="Get Review Event Detail",
    description=(
        "Returns full detail for a review event. "
        "Similarity score is an algorithmic signal — not an identity assertion."
    ),
)
async def get_review_event(
    event_id: int,
    current_user: User = Depends(require_police),
    db: Session = Depends(get_db),
) -> ReviewEventDetail:
    row = review_service.get_event(review_event_id=event_id, db=db)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ReviewEvent id={event_id} not found.",
        )
    return ReviewEventDetail.model_validate(row)


# ---------------------------------------------------------------------------
# Review Events – Workflow Actions
# ---------------------------------------------------------------------------


@router.post(
    "/events/{event_id}/start",
    response_model=ReviewEventDetail,
    summary="Start Reviewing a Possible Match Event",
    description=(
        "Authorized examiner claims and begins reviewing the event. "
        "Transitions status PENDING_REVIEW → UNDER_REVIEW."
    ),
)
async def start_review(
    event_id: int,
    payload: StartReviewRequest,
    request: Request,
    current_user: User = Depends(require_police),
    db: Session = Depends(get_db),
) -> ReviewEventDetail:
    row = review_service.start_review(
        review_event_id=event_id,
        examiner=current_user,
        payload=payload,
        db=db,
        ip_address=_get_client_ip(request),
    )
    return ReviewEventDetail.model_validate(row)


@router.post(
    "/events/{event_id}/decision",
    response_model=ReviewEventDetail,
    summary="Submit Examiner Decision on a Possible Match Event",
    description=(
        "Authorized examiner submits their decision: CONFIRM_FOR_ACTION, REJECTED, or NEED_MORE_EVIDENCE. "
        "\n\n"
        "**AI Safety Notice**: CONFIRM_FOR_ACTION means the examiner authorises the next "
        "investigative step. It does NOT mean the AI system has confirmed the person's identity. "
        "Similarity scores are algorithmic signals only."
    ),
)
async def submit_decision(
    event_id: int,
    payload: ReviewDecisionRequest,
    request: Request,
    current_user: User = Depends(require_police),
    db: Session = Depends(get_db),
) -> ReviewEventDetail:
    row, _module9 = review_service.submit_decision(
        review_event_id=event_id,
        examiner=current_user,
        payload=payload,
        db=db,
        ip_address=_get_client_ip(request),
    )
    return ReviewEventDetail.model_validate(row)


@router.post(
    "/events/{event_id}/evidence-request",
    response_model=ReviewEventDetail,
    summary="Request Additional Evidence for a Review Event",
    description="Examiner records a request for additional evidence or further investigation context.",
)
async def request_evidence(
    event_id: int,
    payload: EvidenceRequestRequest,
    request: Request,
    current_user: User = Depends(require_police),
    db: Session = Depends(get_db),
) -> ReviewEventDetail:
    row = review_service.request_evidence(
        review_event_id=event_id,
        examiner=current_user,
        payload=payload,
        db=db,
        ip_address=_get_client_ip(request),
    )
    return ReviewEventDetail.model_validate(row)


@router.post(
    "/events/{event_id}/assign",
    response_model=ReviewEventDetail,
    summary="Assign or Re-assign a Review Event to an Examiner",
    description="Admin or senior officer assigns a review event to a specific authorized examiner.",
)
async def assign_event(
    event_id: int,
    payload: AssignRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ReviewEventDetail:
    row = review_service.assign_event(
        review_event_id=event_id,
        assigner=current_user,
        payload=payload,
        db=db,
        ip_address=_get_client_ip(request),
    )
    return ReviewEventDetail.model_validate(row)


@router.get(
    "/events/{event_id}/history",
    response_model=ReviewHistory,
    summary="Get Full Audit History for a Review Event",
    description=(
        "Returns the complete, append-only audit trail for all actions taken "
        "on a review event. Provides full accountability and chain-of-custody record."
    ),
)
async def get_review_history(
    event_id: int,
    current_user: User = Depends(require_police),
    db: Session = Depends(get_db),
) -> ReviewHistory:
    return review_service.get_history(review_event_id=event_id, db=db)


# ---------------------------------------------------------------------------
# Investigation Tasks
# ---------------------------------------------------------------------------


@router.get(
    "/tasks",
    response_model=list[InvestigationTaskResponse],
    summary="List Investigation Tasks",
    description="Returns investigation tasks with optional filtering by status, case, or assigned officer.",
)
async def list_tasks(
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="OPEN | ASSIGNED | IN_PROGRESS | COMPLETED | CANCELLED",
    ),
    case_id: Optional[int] = Query(default=None),
    assigned_to: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_police),
    db: Session = Depends(get_db),
) -> list[InvestigationTaskResponse]:
    rows = review_service.list_tasks(
        db=db,
        status=status_filter,
        case_id=case_id,
        assigned_to=assigned_to,
        limit=limit,
        offset=offset,
    )
    return [InvestigationTaskResponse.model_validate(r) for r in rows]


@router.post(
    "/tasks",
    response_model=InvestigationTaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Investigation Task",
    description=(
        "Creates an investigation task for a CONFIRM_FOR_ACTION review event. "
        "Tasks represent authorized follow-up actions and do NOT constitute AI identity confirmation."
    ),
)
async def create_task(
    payload: InvestigationTaskCreate,
    current_user: User = Depends(require_police),
    db: Session = Depends(get_db),
) -> InvestigationTaskResponse:
    task = review_service.create_task(payload=payload, creator=current_user, db=db)
    return InvestigationTaskResponse.model_validate(task)


@router.patch(
    "/tasks/{task_id}",
    response_model=InvestigationTaskResponse,
    summary="Update Investigation Task",
    description="Update task status, assignment, or resolution notes.",
)
async def update_task(
    task_id: int,
    payload: TaskUpdateRequest,
    current_user: User = Depends(require_police),
    db: Session = Depends(get_db),
) -> InvestigationTaskResponse:
    task = review_service.update_task(task_id=task_id, payload=payload, actor=current_user, db=db)
    return InvestigationTaskResponse.model_validate(task)
@router.get(
    "/notifications",
    response_model=list[NotificationItem],
    summary="Get Dashboard Notifications",
)
async def get_notifications_route(
    limit: int = 20,
    current_user: User = Depends(require_police),
    db: Session = Depends(get_db),
) -> list[NotificationItem]:
    return review_service.get_notifications(user_id=current_user.id, db=db, limit=limit)

@router.get(
    "/events/{event_id}/track-history",
    response_model=TrackHistory,
    summary="Get CCTV Track History",
)
async def get_event_track_history(
    event_id: int,
    current_user: User = Depends(require_police),
    db: Session = Depends(get_db),
) -> TrackHistory:
    row = review_service.get_event(review_event_id=event_id, db=db)
    if not row or not row.track_id:
        raise HTTPException(status_code=404, detail="Track history not found.")
    return review_service.get_track_history(track_id=row.track_id, db=db)

@router.patch(
    "/events/{event_id}",
    response_model=ReviewEventDetail,
    summary="Update Review Event Priority/Assignment",
)
async def update_event(
    event_id: int,
    payload: dict,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ReviewEventDetail:
    row = review_service.get_event(review_event_id=event_id, db=db)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    if "priority" in payload:
        row.priority = payload["priority"]
    if "assigned_to" in payload:
        row.assigned_to = payload["assigned_to"]
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return ReviewEventDetail.model_validate(row)
