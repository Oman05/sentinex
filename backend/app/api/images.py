from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.datasets import dataset_router  # Re-exported for backward compatibility
from app.database.session import get_db
from app.dependencies.auth import require_police
from app.models.reference_image import ReferenceImage
from app.models.user import User
from app.schemas.reference_image import (
    ImageStatus,
    ImageStatusUpdateRequest,
    ReferenceImageMetadataUpdateRequest,
    ReferenceImageResponse,
)
from app.services.image_service import ImageService

router = APIRouter(prefix="/cases", tags=["reference-images"])
image_router = APIRouter(prefix="/images", tags=["reference-images"])


def handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    msg = str(exc).lower()
    if "not found" in msg:
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


def get_authorized_visible_image(db: Session, user: User, image_id: int) -> ReferenceImage:
    """Helper to fetch image, verify case permission, and check active visibility."""
    image = ImageService.get_image_by_id(db, user, image_id)
    if not image.is_active and user.role != "ADMIN":
        raise ValueError("Reference image not found")
    return image


# ---------------------------------------------------------------------------
# Case Image Endpoints: /cases/{case_id}/images
# ---------------------------------------------------------------------------

@router.post(
    "/{case_id}/images",
    response_model=list[ReferenceImageResponse],
    status_code=201,
    summary="Upload one or multiple reference images for a case",
)
def upload_reference_images(
    case_id: int,
    files: list[UploadFile] = File(..., description="Image files to upload"),
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    """
    Upload one or multiple reference images for a specified case.
    Files are validated (MIME type, binary structure, dimensions, size),
    safely renamed, and routed to the corresponding dataset directory based on case category.
    """
    try:
        case = ImageService.get_case(db, user, case_id)
        return ImageService.upload(db, user, case, files)
    except (ValueError, PermissionError) as exc:
        raise handle_error(exc) from exc


@router.get(
    "/{case_id}/images",
    response_model=list[ReferenceImageResponse],
    summary="List all authorized reference images for a case",
)
def list_case_reference_images(
    case_id: int,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    """
    Return all authorized reference images associated with a case.
    Inactive images are excluded by default (only visible to admins if requested).
    """
    try:
        ImageService.get_case(db, user, case_id)
        can_view_inactive = include_inactive and user.role == "ADMIN"
        return ImageService.list_case(db, case_id, include_inactive=can_view_inactive)
    except (ValueError, PermissionError) as exc:
        raise handle_error(exc) from exc


@router.patch(
    "/{case_id}/images/{image_id}/primary",
    response_model=ReferenceImageResponse,
    summary="Set primary reference image for a case",
)
def set_primary_image(
    case_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    """Set an active reference image as the primary image for a case."""
    try:
        image = ImageService.get_image(db, user, case_id, image_id)
        return ImageService.primary(db, user, image)
    except (ValueError, PermissionError) as exc:
        raise handle_error(exc) from exc


@router.patch(
    "/{case_id}/images/{image_id}/status",
    response_model=ReferenceImageResponse,
    summary="Activate or deactivate case image (case-scoped)",
)
def update_case_image_status(
    case_id: int,
    image_id: int,
    payload: ImageStatusUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    """Update active status of an image scoped by case_id."""
    try:
        image = ImageService.get_image(db, user, case_id, image_id)
        active = payload.is_active if payload.is_active is not None else (payload.status == ImageStatus.ACTIVE)
        return ImageService.status(db, user, image, active)
    except (ValueError, PermissionError) as exc:
        raise handle_error(exc) from exc


@router.delete(
    "/{case_id}/images/{image_id}",
    response_model=ReferenceImageResponse,
    summary="Soft delete a case image (case-scoped)",
)
def soft_delete_case_image(
    case_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    """Soft delete / logically deactivate an image scoped by case_id."""
    try:
        image = ImageService.get_image(db, user, case_id, image_id)
        return ImageService.status(db, user, image, False)
    except (ValueError, PermissionError) as exc:
        raise handle_error(exc) from exc


# ---------------------------------------------------------------------------
# Individual Image Endpoints: /images/{image_id}
# ---------------------------------------------------------------------------

@image_router.get(
    "/{image_id}",
    response_model=ReferenceImageResponse,
    summary="Get metadata for a specific reference image",
)
def get_image_metadata(
    image_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    """Return metadata for a specific authorized reference image and log access."""
    try:
        image = get_authorized_visible_image(db, user, image_id)
        ImageService.log(
            db,
            user_id=user.id,
            image_id=image.id,
            case_id=image.case_id,
            action="REFERENCE_IMAGE_ACCESSED",
            details=f"filename={image.original_file_name}",
        )
        return image
    except (ValueError, PermissionError) as exc:
        raise handle_error(exc) from exc


@image_router.put(
    "/{image_id}",
    response_model=ReferenceImageResponse,
    summary="Update permitted image metadata",
)
def update_image_metadata(
    image_id: int,
    payload: ReferenceImageMetadataUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    """Update permitted metadata (filename, description, tags, notes, quality status, primary flag)."""
    try:
        image = get_authorized_visible_image(db, user, image_id)
        return ImageService.update_metadata(db, user, image, payload)
    except (ValueError, PermissionError) as exc:
        raise handle_error(exc) from exc


@image_router.patch(
    "/{image_id}/status",
    response_model=ReferenceImageResponse,
    summary="Activate or deactivate an image",
)
def update_image_status(
    image_id: int,
    payload: ImageStatusUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    """Activate or deactivate an image record without permanently deleting it."""
    try:
        image = ImageService.get_image_by_id(db, user, image_id)
        active = payload.is_active if payload.is_active is not None else (payload.status == ImageStatus.ACTIVE)
        return ImageService.status(db, user, image, active)
    except (ValueError, PermissionError) as exc:
        raise handle_error(exc) from exc


@image_router.delete(
    "/{image_id}",
    response_model=ReferenceImageResponse,
    summary="Soft delete/deactivate an image",
)
def delete_image(
    image_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    """
    Logically deactivate (soft delete) an image.
    The database record and image file are preserved for audit and historical integrity.
    """
    try:
        image = ImageService.get_image_by_id(db, user, image_id)
        return ImageService.status(db, user, image, False)
    except (ValueError, PermissionError) as exc:
        raise handle_error(exc) from exc


@image_router.api_route(
    "/{image_id}/replace",
    methods=["POST", "PUT"],
    response_model=ReferenceImageResponse,
    summary="Replace an authorized reference image",
)
def replace_reference_image(
    image_id: int,
    file: UploadFile = File(..., description="New replacement image file"),
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    """Replace an existing image file with a newly uploaded, validated image."""
    try:
        image = get_authorized_visible_image(db, user, image_id)
        return ImageService.replace(db, user, image, file)
    except (ValueError, PermissionError) as exc:
        raise handle_error(exc) from exc
