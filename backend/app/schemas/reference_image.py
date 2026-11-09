from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ImageStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ReferenceImageResponse(BaseModel):
    id: int
    case_id: int
    file_name: str
    original_file_name: str
    file_path: str
    storage_type: str = "LOCAL"
    mime_type: str
    file_size: int
    image_width: int
    image_height: int
    uploaded_by: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Future-ready fields
    image_quality_status: str | None = None
    processing_status: str | None = None
    feature_reference_id: str | None = None
    notes: str | None = None

    # Additional metadata
    description: str | None = None
    tags: list[str] | None = None
    is_primary: bool = False

    # Backward compatibility aliases
    stored_filename: str | None = None
    original_filename: str | None = None
    file_type: str | None = None
    width: int | None = None
    height: int | None = None
    uploaded_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def populate_synonyms(cls, data):
        if hasattr(data, "__dict__") or isinstance(data, dict):
            # Helper to extract value whether data is orm object or dict
            def get_val(key):
                return data.get(key) if isinstance(data, dict) else getattr(data, key, None)

            # If dict, populate both new and legacy names
            if isinstance(data, dict):
                file_name = get_val("file_name") or get_val("stored_filename")
                orig_name = get_val("original_file_name") or get_val("original_filename")
                mime = get_val("mime_type") or get_val("file_type")
                w = get_val("image_width") if get_val("image_width") is not None else get_val("width")
                h = get_val("image_height") if get_val("image_height") is not None else get_val("height")
                created = get_val("created_at") or get_val("uploaded_at")

                data["file_name"] = file_name
                data["stored_filename"] = file_name
                data["original_file_name"] = orig_name
                data["original_filename"] = orig_name
                data["mime_type"] = mime
                data["file_type"] = mime
                data["image_width"] = w
                data["width"] = w
                data["image_height"] = h
                data["height"] = h
                data["created_at"] = created
                data["uploaded_at"] = created
            else:
                # ORM model: populate legacy synonyms if None
                fn = getattr(data, "file_name", None) or getattr(data, "stored_filename", None)
                orig = getattr(data, "original_file_name", None) or getattr(data, "original_filename", None)
                mt = getattr(data, "mime_type", None) or getattr(data, "file_type", None)
                iw = getattr(data, "image_width", None) if getattr(data, "image_width", None) is not None else getattr(data, "width", None)
                ih = getattr(data, "image_height", None) if getattr(data, "image_height", None) is not None else getattr(data, "height", None)
                ca = getattr(data, "created_at", None) or getattr(data, "uploaded_at", None)

                return {
                    "id": getattr(data, "id", None),
                    "case_id": getattr(data, "case_id", None),
                    "file_name": fn,
                    "stored_filename": fn,
                    "original_file_name": orig,
                    "original_filename": orig,
                    "file_path": getattr(data, "file_path", None),
                    "storage_type": getattr(data, "storage_type", "LOCAL"),
                    "mime_type": mt,
                    "file_type": mt,
                    "file_size": getattr(data, "file_size", None),
                    "image_width": iw,
                    "width": iw,
                    "image_height": ih,
                    "height": ih,
                    "uploaded_by": getattr(data, "uploaded_by", None),
                    "is_active": getattr(data, "is_active", True),
                    "created_at": ca,
                    "uploaded_at": ca,
                    "updated_at": getattr(data, "updated_at", None),
                    "image_quality_status": getattr(data, "image_quality_status", None),
                    "processing_status": getattr(data, "processing_status", None),
                    "feature_reference_id": getattr(data, "feature_reference_id", None),
                    "notes": getattr(data, "notes", None),
                    "description": getattr(data, "description", None),
                    "tags": getattr(data, "tags", None),
                    "is_primary": getattr(data, "is_primary", False),
                }
        return data

    model_config = ConfigDict(from_attributes=True)


class ImageStatusUpdateRequest(BaseModel):
    status: ImageStatus | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_at_least_one(self):
        if self.status is None and self.is_active is None:
            raise ValueError("Either 'status' or 'is_active' must be provided")
        return self


class ReferenceImageMetadataUpdateRequest(BaseModel):
    original_file_name: str | None = Field(default=None, min_length=1, max_length=255)
    original_filename: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = Field(default=None, max_length=50)
    is_primary: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)
    image_quality_status: str | None = Field(default=None, max_length=50)

    @field_validator("original_file_name", "original_filename", "description", "notes", "image_quality_status")
    @classmethod
    def strip_text(cls, value):
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value):
        if value is None:
            return value
        normalized = [tag.strip() for tag in value]
        if any(not tag for tag in normalized):
            raise ValueError("Tags cannot be blank")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Tags must be unique")
        return normalized

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one metadata field is required")
        return self


class PaginatedReferenceImagesResponse(BaseModel):
    items: list[ReferenceImageResponse]
    total: int
    page: int = Field(ge=1)
    size: int = Field(ge=1)


class CaseWithImagesResponse(BaseModel):
    id: int
    case_number: str
    category: str
    title: str
    person_identifier: str
    description: str
    department_id: int
    created_by: int
    status: str
    priority: str
    last_known_location: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    reference_images: list[ReferenceImageResponse] = []

    model_config = ConfigDict(from_attributes=True)


class PaginatedCasesWithImagesResponse(BaseModel):
    items: list[CaseWithImagesResponse]
    total: int
    page: int = Field(ge=1)
    size: int = Field(ge=1)
