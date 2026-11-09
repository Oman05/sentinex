from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import require_police
from app.models.user import User
from app.schemas.reference_image import (
    PaginatedCasesWithImagesResponse,
    PaginatedReferenceImagesResponse,
)
from app.services.image_service import ImageService

router = APIRouter(prefix="/datasets", tags=["datasets"])
dataset_router = router  # Alias for backward compatibility


def handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    msg = str(exc).lower()
    if "not found" in msg:
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/missing",
    response_model=PaginatedReferenceImagesResponse,
    summary="Get active missing-person dataset reference images",
)
def get_missing_dataset(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=200, description="Page size"),
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    """
    Retrieve active reference images from the Missing Person Dataset.
    Admin users access all records; authorized department users access department cases.
    """
    try:
        items, total = ImageService.dataset(db, user, "MISSING", page, size)
        return {"items": items, "total": total, "page": page, "size": size}
    except (ValueError, PermissionError) as exc:
        raise handle_error(exc) from exc


@router.get(
    "/wanted",
    response_model=PaginatedReferenceImagesResponse,
    summary="Get active wanted-person dataset reference images",
)
def get_wanted_dataset(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=200, description="Page size"),
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    """
    Retrieve active reference images from the Wanted Person Dataset.
    Admin users access all records; authorized department users access department cases.
    """
    try:
        items, total = ImageService.dataset(db, user, "WANTED", page, size)
        return {"items": items, "total": total, "page": page, "size": size}
    except (ValueError, PermissionError) as exc:
        raise handle_error(exc) from exc


@router.get(
    "/{category}/cases",
    response_model=PaginatedCasesWithImagesResponse,
    summary="Get active cases with associated reference images for a category",
)
def get_cases_with_images_by_category(
    category: str,
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=200, description="Page size"),
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    """
    Return active cases and associated active reference image information for the requested category
    (MISSING or WANTED).
    """
    try:
        items, total = ImageService.get_cases_with_images_by_category(db, user, category, page, size)
        return {"items": items, "total": total, "page": page, "size": size}
    except (ValueError, PermissionError) as exc:
        raise handle_error(exc) from exc


# Compatible aliases for legacy/extended path conventions
@router.get("/missing-persons", response_model=PaginatedReferenceImagesResponse, include_in_schema=False)
def get_missing_persons_alias(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    return get_missing_dataset(page, size, db, user)


@router.get("/wanted-persons", response_model=PaginatedReferenceImagesResponse, include_in_schema=False)
def get_wanted_persons_alias(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    return get_wanted_dataset(page, size, db, user)
