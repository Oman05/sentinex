from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import require_police
from app.models.case import Case
from app.models.user import User
from app.schemas.case import (
    CaseCreateRequest,
    CaseDeleteResponse,
    CaseDetailResponse,
    CaseStatusUpdateRequest,
    CaseSummaryResponse,
    CaseUpdateRequest,
    PaginatedCasesResponse,
)
from app.services.case_service import CaseService

router = APIRouter(prefix="/cases", tags=["cases"])


def _to_case_summary(case: Case) -> CaseSummaryResponse:
    return CaseSummaryResponse(
        id=case.id,
        case_number=case.case_number,
        category=case.category,
        title=case.title,
        person_identifier=case.person_identifier,
        department_id=case.department_id,
        created_by=case.created_by,
        status=case.status,
        priority=case.priority,
        last_known_location=case.last_known_location,
        is_active=case.is_active,
        created_at=case.created_at.isoformat(),
        updated_at=case.updated_at.isoformat(),
        closed_at=case.closed_at.isoformat() if case.closed_at else None,
    )


def _to_case_detail(case: Case) -> CaseDetailResponse:
    item = _to_case_summary(case)
    return CaseDetailResponse(
        **item.model_dump(),
        description=case.description,
    )


@router.post("", response_model=CaseDetailResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    try:
        case = CaseService.create_case(db, current_user, payload)
    except (PermissionError, ValueError) as exc:
        detail = str(exc)
        status_code = status.HTTP_403_FORBIDDEN if isinstance(exc, PermissionError) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return _to_case_detail(case)


@router.get("", response_model=PaginatedCasesResponse)
def list_cases(
    category: str | None = None,
    status: str | None = None,
    department_id: int | None = None,
    priority: str | None = None,
    search: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    include_inactive: bool = False,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    query = CaseService.build_access_query(db, current_user, include_inactive=include_inactive)
    query = CaseService.apply_filters(
        query,
        category=category,
        status=status,
        department_id=department_id,
        priority=priority,
        search=search,
        start_date=start_date,
        end_date=end_date,
    )
    total = query.count()
    cases = query.order_by(Case.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return {
        "items": [_to_case_summary(case) for case in cases],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/my-department", response_model=PaginatedCasesResponse)
def list_my_department_cases(
    category: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    search: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    if current_user.department_id is None and current_user.role != "ADMIN":
        query = db.query(Case).filter(Case.created_by == current_user.id)
    else:
        query = db.query(Case).filter(Case.department_id == current_user.department_id)
    if current_user.role != "ADMIN":
        query = query.filter(Case.is_active.is_(True))
    query = CaseService.apply_filters(
        query,
        category=category,
        status=status,
        priority=priority,
        search=search,
        start_date=start_date,
        end_date=end_date,
    )
    total = query.count()
    cases = query.order_by(Case.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": [_to_case_summary(case) for case in cases], "total": total, "page": page, "size": size}


@router.get("/{case_id}", response_model=CaseDetailResponse)
def get_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    try:
        case = CaseService.get_case_or_404(db, case_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if not CaseService.user_can_access_case(current_user, case):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this case")
    CaseService.log_case_action(db, current_user.id, case.id, "CASE_ACCESSED", "Case details viewed by authorized user")
    return _to_case_detail(case)


@router.put("/{case_id}", response_model=CaseDetailResponse)
def update_case(
    case_id: int,
    payload: CaseUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    try:
        case = CaseService.get_case_or_404(db, case_id)
        updated_case = CaseService.update_case(db, current_user, case, payload)
    except (PermissionError, ValueError) as exc:
        detail = str(exc)
        code = status.HTTP_403_FORBIDDEN if isinstance(exc, PermissionError) else status.HTTP_400_BAD_REQUEST
        if isinstance(exc, ValueError) and "not found" in detail.lower():
            code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=detail) from exc
    return _to_case_detail(updated_case)


@router.patch("/{case_id}/status", response_model=CaseDetailResponse)
def update_case_status(
    case_id: int,
    payload: CaseStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    try:
        case = CaseService.get_case_or_404(db, case_id)
        updated_case = CaseService.update_case_status(db, current_user, case, payload.status)
    except (PermissionError, ValueError) as exc:
        detail = str(exc)
        code = status.HTTP_403_FORBIDDEN if isinstance(exc, PermissionError) else status.HTTP_400_BAD_REQUEST
        if isinstance(exc, ValueError) and "not found" in detail.lower():
            code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=detail) from exc
    return _to_case_detail(updated_case)


@router.delete("/{case_id}", response_model=CaseDeleteResponse)
def deactivate_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
):
    try:
        case = CaseService.get_case_or_404(db, case_id)
        updated_case = CaseService.deactivate_case(db, current_user, case)
    except (PermissionError, ValueError) as exc:
        detail = str(exc)
        code = status.HTTP_403_FORBIDDEN if isinstance(exc, PermissionError) else status.HTTP_400_BAD_REQUEST
        if isinstance(exc, ValueError) and "not found" in detail.lower():
            code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=detail) from exc
    return {"message": "Case deactivated successfully", "case_id": updated_case.id}
