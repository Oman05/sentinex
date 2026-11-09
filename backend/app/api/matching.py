"""
Module 7 – Candidate Matching & Ranking API Router
===================================================
Exposes REST endpoints for match-ready candidate search, direct image querying,
PossibleMatchEvent queue management, dataset re-indexing, and telemetry.

Security & Safety:
- Protected via Module 1 authentication (JWT) and RBAC (Police/Admin).
- Similarity score is an algorithmic ranking signal, NEVER guaranteed identity.
- Output always carries: "POSSIBLE MATCH — REQUIRES AUTHORIZED HUMAN VERIFICATION".
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_police
from app.database.session import get_db
from app.ai_engine.schemas.matching import (
    CandidateSearchResponse,
    DirectQueryFaceRequest,
    MatchingTelemetryResponse,
    MatchEventStatus,
    MatchReadyCandidateInput,
    PossibleMatchEvent,
    ReindexResponse,
    SearchMode,
)
from app.services.matching_service import matching_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/matching", tags=["Module 7 – Candidate Matching & Ranking"])


@router.post(
    "/search",
    response_model=CandidateSearchResponse,
    summary="Search Match-Ready Candidate Against Reference Datasets",
    description=(
        "Receives a match-ready face observation from Module 6 (is_match_ready=True), "
        "extracts facial feature representations, queries authorized reference datasets "
        "(Missing Person and/or Wanted Person), aggregates multiple reference evidence, "
        "and computes non-biased candidate rankings. Outputs possible match alerts for Module 8."
    ),
)
async def search_candidate(
    payload: MatchReadyCandidateInput,
    current_user: Any = Depends(require_police),
    db: Session = Depends(get_db),
) -> CandidateSearchResponse:
    """Execute candidate matching pipeline for a match-ready observation."""
    if not payload.is_match_ready:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Observation is not match-ready. Module 6 quality gating rejected this face.",
        )
    return matching_service.process_match_ready_candidate(payload, db=db)


@router.post(
    "/query-face",
    response_model=CandidateSearchResponse,
    summary="Direct Face Image Search",
    description=(
        "Allows authorized investigators to execute an on-demand facial feature search "
        "against Missing Person, Wanted Person, or All Active Cases using a face image crop."
    ),
)
async def query_face(
    payload: DirectQueryFaceRequest,
    current_user: Any = Depends(require_police),
    db: Session = Depends(get_db),
) -> CandidateSearchResponse:
    """Execute direct face query search."""
    return matching_service.search_query_face(payload, db=db)


@router.get(
    "/events",
    response_model=list[PossibleMatchEvent],
    summary="List Possible Match Events (Human Verification Queue)",
    description=(
        "Retrieves possible match alert events awaiting or undergoing Module 8 human verification. "
        "Supports filtering by status (PENDING_REVIEW, IN_REVIEW, VERIFIED, REJECTED), category, case, or camera."
    ),
)
async def list_match_events(
    status_filter: MatchEventStatus | None = Query(default=None, alias="status"),
    category: str | None = Query(default=None, pattern="^(MISSING|WANTED)$"),
    case_id: int | None = Query(default=None),
    camera_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: Any = Depends(require_police),
    db: Session = Depends(get_db),
) -> list[PossibleMatchEvent]:
    """List match events with filters."""
    status_str = status_filter.value if status_filter else None
    return matching_service.event_mgr.list_events(
        db=db,
        status=status_str,
        category=category,
        case_id=case_id,
        camera_id=camera_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/events/{event_id}",
    response_model=PossibleMatchEvent,
    summary="Get Match Event Details",
    description="Fetches comprehensive detail for a specific PossibleMatchEvent by its event ID.",
)
async def get_match_event(
    event_id: str,
    current_user: Any = Depends(require_police),
    db: Session = Depends(get_db),
) -> PossibleMatchEvent:
    """Fetch individual match event."""
    event = matching_service.event_mgr.get_event_by_id(event_id=event_id, db=db)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match event '{event_id}' not found",
        )
    return event


@router.patch(
    "/events/{event_id}/status",
    response_model=PossibleMatchEvent,
    summary="Update Match Event Status (Module 8 Hook)",
    description="Updates verification status (e.g. IN_REVIEW, VERIFIED, REJECTED) by an authorized examiner.",
)
async def update_match_event_status(
    event_id: str,
    new_status: MatchEventStatus,
    current_user: Any = Depends(require_police),
    db: Session = Depends(get_db),
) -> PossibleMatchEvent:
    """Update event review status."""
    event = matching_service.event_mgr.update_event_status(
        event_id=event_id, new_status=new_status, db=db
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match event '{event_id}' not found",
        )
    return event


@router.post(
    "/reindex",
    response_model=ReindexResponse,
    summary="Re-index Reference Datasets",
    description=(
        "Extracts feature embeddings for all active reference images using the current active model "
        "and updates the in-memory vector search index. Restricted to Administrator role."
    ),
)
async def reindex_reference_images(
    current_user: Any = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ReindexResponse:
    """Execute full reference image re-indexing."""
    return matching_service.reindex_reference_images(db=db)


@router.get(
    "/telemetry",
    response_model=MatchingTelemetryResponse,
    summary="Module 7 Operational Telemetry",
    description="Returns live operational metrics: queries processed, candidates retrieved, alerts created, latencies.",
)
async def get_matching_telemetry(
    current_user: Any = Depends(require_police),
) -> MatchingTelemetryResponse:
    """Get matching telemetry statistics."""
    return matching_service.get_telemetry_snapshot()
