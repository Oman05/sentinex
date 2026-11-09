from __future__ import annotations

from datetime import datetime
from typing import Sequence

from fastapi import UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.case import Case
from app.models.reference_image import ReferenceImage
from app.models.user import User
from app.schemas.reference_image import ReferenceImageMetadataUpdateRequest
from app.services.case_service import CaseService
from app.storage.file_manager import default_file_manager
from app.utils.image_validator import validate_image_content


class ImageService:
    @staticmethod
    def log(
        db: Session,
        user_id: int | None,
        image_id: int | None,
        case_id: int | None,
        action: str,
        details: str | None = None,
    ) -> None:
        """Create an audit log record for image management operations."""
        try:
            detail_str = f"case_id={case_id}" if case_id else ""
            if details:
                detail_str = f"{detail_str}; {details}".strip("; ")
            db.add(
                AuditLog(
                    user_id=user_id,
                    action=action,
                    resource_type="REFERENCE_IMAGE",
                    resource_id=image_id or case_id,
                    details=detail_str or None,
                )
            )
            db.commit()
        except Exception:
            db.rollback()

    @staticmethod
    def get_case(db: Session, user: User, case_id: int) -> Case:
        """Retrieve case and enforce role-based access control."""
        case = CaseService.get_case_or_404(db, case_id)
        if not CaseService.user_can_access_case(user, case):
            ImageService.log(
                db,
                user_id=user.id,
                image_id=None,
                case_id=case.id,
                action="UNAUTHORIZED_ACCESS_ATTEMPT",
                details=f"Unauthorized access to case {case_id} by user {user.username}",
            )
            raise PermissionError("You do not have access to this case")
        return case

    @staticmethod
    def get_image(db: Session, user: User, case_id: int, image_id: int) -> ReferenceImage:
        """Retrieve reference image for a specific case and verify permissions."""
        case = ImageService.get_case(db, user, case_id)
        image = (
            db.query(ReferenceImage)
            .filter(ReferenceImage.id == image_id, ReferenceImage.case_id == case.id)
            .first()
        )
        if image is None:
            raise ValueError("Reference image not found")
        return image

    @staticmethod
    def get_image_by_id(db: Session, user: User, image_id: int) -> ReferenceImage:
        """Retrieve reference image by ID and enforce case permission."""
        image = db.query(ReferenceImage).filter(ReferenceImage.id == image_id).first()
        if image is None:
            raise ValueError("Reference image not found")
        ImageService.get_case(db, user, image.case_id)
        return image

    @staticmethod
    def upload(db: Session, user: User, case: Case, files: list[UploadFile]) -> list[ReferenceImage]:
        """
        Securely validate, store, and enroll one or multiple reference images for a case.
        Automatically routes files into missing_persons or wanted_persons dataset folder.
        """
        if not files:
            raise ValueError("At least one image is required")
        if len(files) > 50:
            raise ValueError("A maximum of 50 images can be uploaded at once")

        saved_files: list[str] = []
        records: list[ReferenceImage] = []

        try:
            # 1. Validate all files before writing to disk
            validated = []
            for upload in files:
                content = upload.file.read()
                checked = validate_image_content(
                    content=content,
                    content_type=upload.content_type,
                    original_filename=upload.filename,
                    max_size=settings.MAX_IMAGE_SIZE_BYTES,
                    max_dimension=settings.MAX_IMAGE_DIMENSION,
                )
                validated.append((upload, content, checked))

            # 2. Persist files into category-specific dataset directory
            for upload, content, checked in validated:
                stored_name, file_path, storage_type = default_file_manager.save_image(
                    category=case.category,
                    case_number=case.case_number,
                    extension=checked.extension,
                    content=content,
                )
                saved_files.append(file_path)

                record = ReferenceImage(
                    case_id=case.id,
                    file_name=stored_name,
                    original_file_name=checked.sanitized_original_name,
                    file_path=file_path,
                    storage_type=storage_type,
                    mime_type=checked.file_type,
                    file_size=len(content),
                    image_width=checked.width,
                    image_height=checked.height,
                    uploaded_by=user.id,
                    is_active=True,
                    is_primary=False,
                    image_quality_status="PENDING",
                    processing_status="PENDING",
                )
                records.append(record)

            db.add_all(records)
            db.flush()

            # Set first active image as primary if case currently has no primary image
            has_primary = (
                db.query(ReferenceImage)
                .filter(
                    ReferenceImage.case_id == case.id,
                    ReferenceImage.is_active.is_(True),
                    ReferenceImage.is_primary.is_(True),
                )
                .first()
            )
            if not has_primary and records:
                records[0].is_primary = True

            db.commit()

            # Auto-enroll reference images into vector search index
            try:
                from app.ai_engine.matching.embedding_service import embedding_service
                for img in records:
                    embedding_service.enroll_reference_image(img, case, db=db)
            except Exception as emb_exc:
                import logging
                logging.getLogger(__name__).warning(
                    "[ImageService] Auto-enrollment warning for case %s: %s", case.case_number, emb_exc
                )

            # Log audit for all uploaded images
            for img in records:
                db.refresh(img)
                ImageService.log(
                    db,
                    user_id=user.id,
                    image_id=img.id,
                    case_id=case.id,
                    action="REFERENCE_IMAGE_UPLOADED",
                    details=f"filename={img.original_file_name}; size={img.file_size}; category={case.category}",
                )

            return records

        except Exception:
            db.rollback()
            for path in saved_files:
                default_file_manager.remove_file(path)
            raise

    @staticmethod
    def update_metadata(
        db: Session,
        user: User,
        image: ReferenceImage,
        payload: ReferenceImageMetadataUpdateRequest,
    ) -> ReferenceImage:
        """Update permitted metadata for an authorized reference image."""
        changes = payload.model_dump(exclude_unset=True)
        if changes.get("is_primary") is True:
            return ImageService.primary(db, user, image)

        field_mapping = {
            "original_filename": "original_file_name",
            "original_file_name": "original_file_name",
            "description": "description",
            "tags": "tags",
            "notes": "notes",
            "image_quality_status": "image_quality_status",
            "is_primary": "is_primary",
        }

        updated_fields = []
        for key, value in changes.items():
            attr = field_mapping.get(key)
            if attr and hasattr(image, attr):
                setattr(image, attr, value)
                updated_fields.append(attr)

        image.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(image)

        ImageService.log(
            db,
            user_id=user.id,
            image_id=image.id,
            case_id=image.case_id,
            action="REFERENCE_IMAGE_UPDATED",
            details=f"fields={','.join(set(updated_fields))}",
        )
        return image

    @staticmethod
    def replace(db: Session, user: User, image: ReferenceImage, upload: UploadFile) -> ReferenceImage:
        """Replace an authorized reference image with a new validated image file."""
        content = upload.file.read()
        checked = validate_image_content(
            content=content,
            content_type=upload.content_type,
            original_filename=upload.filename,
            max_size=settings.MAX_IMAGE_SIZE_BYTES,
            max_dimension=settings.MAX_IMAGE_DIMENSION,
        )

        case = CaseService.get_case_or_404(db, image.case_id)
        old_path = image.file_path

        new_name, new_path, storage_type = default_file_manager.save_image(
            category=case.category,
            case_number=case.case_number,
            extension=checked.extension,
            content=content,
        )

        try:
            image.file_name = new_name
            image.original_file_name = checked.sanitized_original_name
            image.file_path = new_path
            image.storage_type = storage_type
            image.mime_type = checked.file_type
            image.file_size = len(content)
            image.image_width = checked.width
            image.image_height = checked.height
            image.updated_at = datetime.utcnow()

            db.commit()
            db.refresh(image)

            # Clean up old stored file
            default_file_manager.remove_file(old_path)

            ImageService.log(
                db,
                user_id=user.id,
                image_id=image.id,
                case_id=image.case_id,
                action="REFERENCE_IMAGE_REPLACED",
                details=f"filename={image.original_file_name}; size={image.file_size}",
            )
            return image
        except Exception:
            db.rollback()
            default_file_manager.remove_file(new_path)
            raise

    @staticmethod
    def status(db: Session, user: User, image: ReferenceImage, active: bool) -> ReferenceImage:
        """Activate or deactivate a reference image (logical soft deactivation)."""
        image.is_active = active
        if not active:
            image.is_primary = False
        image.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(image)

        action = "REFERENCE_IMAGE_ACTIVATED" if active else "REFERENCE_IMAGE_DEACTIVATED"
        ImageService.log(
            db,
            user_id=user.id,
            image_id=image.id,
            case_id=image.case_id,
            action=action,
            details=f"is_active={active}",
        )
        return image

    @staticmethod
    def primary(db: Session, user: User, image: ReferenceImage) -> ReferenceImage:
        """Set an image as the primary reference image for a case."""
        if not image.is_active:
            raise ValueError("Only an active image can be set as primary")

        db.query(ReferenceImage).filter(
            ReferenceImage.case_id == image.case_id,
            ReferenceImage.id != image.id,
        ).update({ReferenceImage.is_primary: False}, synchronize_session=False)

        image.is_primary = True
        image.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(image)

        ImageService.log(
            db,
            user_id=user.id,
            image_id=image.id,
            case_id=image.case_id,
            action="REFERENCE_IMAGE_PRIMARY_CHANGED",
        )
        return image

    @staticmethod
    def list_case(db: Session, case_id: int, include_inactive: bool = False) -> list[ReferenceImage]:
        """List reference images for a case, optionally including inactive ones."""
        query = db.query(ReferenceImage).filter(ReferenceImage.case_id == case_id)
        if not include_inactive:
            query = query.filter(ReferenceImage.is_active.is_(True))
        return query.order_by(ReferenceImage.is_primary.desc(), ReferenceImage.created_at.asc()).all()

    @staticmethod
    def dataset(
        db: Session,
        user: User,
        category: str,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[ReferenceImage], int]:
        """
        Retrieve active reference images for a specific dataset category (MISSING or WANTED).
        Admin users can view all; department users view only authorized cases.
        """
        cat_upper = category.upper()
        if cat_upper not in {"MISSING", "WANTED"}:
            raise ValueError("Unsupported dataset category. Expected 'MISSING' or 'WANTED'")

        query = (
            db.query(ReferenceImage)
            .join(Case, Case.id == ReferenceImage.case_id)
            .filter(Case.category == cat_upper, ReferenceImage.is_active.is_(True))
        )

        if user.role != "ADMIN":
            if user.department_id is not None:
                query = query.filter(
                    or_(Case.department_id == user.department_id, Case.created_by == user.id)
                )
            else:
                query = query.filter(Case.created_by == user.id)

        total = query.count()
        items = (
            query.order_by(ReferenceImage.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )
        return items, total

    @staticmethod
    def get_cases_with_images_by_category(
        db: Session,
        user: User,
        category: str,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict], int]:
        """
        Return active cases and associated active reference images for the requested category.
        """
        cat_upper = category.upper()
        if cat_upper not in {"MISSING", "WANTED"}:
            raise ValueError("Unsupported dataset category. Expected 'MISSING' or 'WANTED'")

        query = db.query(Case).filter(Case.category == cat_upper, Case.is_active.is_(True))
        if user.role != "ADMIN":
            if user.department_id is not None:
                query = query.filter(
                    or_(Case.department_id == user.department_id, Case.created_by == user.id)
                )
            else:
                query = query.filter(Case.created_by == user.id)

        total = query.count()
        cases: Sequence[Case] = (
            query.order_by(Case.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )

        results = []
        for c in cases:
            # Active images for this case
            active_imgs = (
                db.query(ReferenceImage)
                .filter(ReferenceImage.case_id == c.id, ReferenceImage.is_active.is_(True))
                .order_by(ReferenceImage.is_primary.desc(), ReferenceImage.created_at.asc())
                .all()
            )
            results.append({
                "id": c.id,
                "case_number": c.case_number,
                "category": c.category,
                "title": c.title,
                "person_identifier": c.person_identifier,
                "description": c.description,
                "department_id": c.department_id,
                "created_by": c.created_by,
                "status": c.status,
                "priority": c.priority,
                "last_known_location": c.last_known_location,
                "is_active": c.is_active,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
                "closed_at": c.closed_at,
                "reference_images": active_imgs,
            })

        return results, total

    # --- Clean interfaces for future AI processing modules (Module 4, 5, 6, 7) ---

    @staticmethod
    def get_active_images_for_ai(
        db: Session,
        category: str | None = None,
        case_id: int | None = None,
    ) -> list[ReferenceImage]:
        """
        Internal interface for future AI modules (face detection, quality assessment, feature extraction).
        Retrieves all active, authorized reference images.
        """
        query = (
            db.query(ReferenceImage)
            .join(Case, Case.id == ReferenceImage.case_id)
            .filter(ReferenceImage.is_active.is_(True), Case.is_active.is_(True))
        )
        if category:
            query = query.filter(Case.category == category.upper())
        if case_id:
            query = query.filter(Case.id == case_id)
        return query.order_by(Case.id.asc(), ReferenceImage.is_primary.desc()).all()

    @staticmethod
    def get_case_images_for_ai(db: Session, case_number: str) -> list[ReferenceImage]:
        """Retrieve all active reference images for a specific case number for candidate matching."""
        return (
            db.query(ReferenceImage)
            .join(Case, Case.id == ReferenceImage.case_id)
            .filter(
                Case.case_number == case_number,
                Case.is_active.is_(True),
                ReferenceImage.is_active.is_(True),
            )
            .order_by(ReferenceImage.is_primary.desc())
            .all()
        )
