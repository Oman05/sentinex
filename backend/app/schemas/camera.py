from __future__ import annotations

from datetime import datetime
from enum import Enum
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.camera import CameraStatus


class StreamType(str, Enum):
    RTSP = "RTSP"
    HTTP = "HTTP"
    HTTPS = "HTTPS"
    WEBCAM = "WEBCAM"
    FILE = "FILE"
    TEST = "TEST"
    PRERECORDED = "PRERECORDED"


def validate_stream_url(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if value.isdigit() or value.startswith("file://") or value.startswith("test:") or value.startswith("prerecorded:"):
        return value
    if ("://" not in value) and value.lower().endswith((".mp4", ".avi", ".mkv", ".mov", ".m4v")):
        return value
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"rtsp", "http", "https"} or not parsed.netloc:
        raise ValueError("Stream URL must use RTSP, HTTP, or HTTPS, or a webcam device index (e.g. 0)")
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        raise ValueError("Stream URL must not contain embedded credentials. Provide username_reference and password separately.")
    return value


class CameraCreateRequest(BaseModel):
    camera_code: str | None = Field(default=None, min_length=1, max_length=50)
    camera_name: str | None = Field(default=None, min_length=1, max_length=150)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    department_id: int
    location_name: str | None = Field(default=None, max_length=255)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    jurisdiction: str | None = Field(default=None, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    stream_url: str = Field(..., max_length=2048)
    stream_type: StreamType | None = None
    username_reference: str | None = Field(default=None, max_length=150)
    password: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool = True
    sample_fps: float = Field(default=1.0, gt=0, le=30)
    queue_size: int = Field(default=8, ge=1, le=1000)
    retry_limit: int = Field(default=3, ge=0, le=20)

    _url = field_validator("stream_url")(validate_stream_url)

    @model_validator(mode="after")
    def normalize_names(self):
        if self.camera_name is None and self.name is None:
            raise ValueError("camera_name is required")
        if self.camera_name is None:
            self.camera_name = self.name
        if self.name is None:
            self.name = self.camera_name
        return self


class CameraUpdateRequest(BaseModel):
    camera_code: str | None = Field(default=None, min_length=1, max_length=50)
    camera_name: str | None = Field(default=None, min_length=1, max_length=150)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    department_id: int | None = None
    location_name: str | None = Field(default=None, max_length=255)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    jurisdiction: str | None = Field(default=None, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    stream_url: str | None = Field(default=None, max_length=2048)
    stream_type: StreamType | None = None
    username_reference: str | None = Field(default=None, max_length=150)
    password: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None
    sample_fps: float | None = Field(default=None, gt=0, le=30)
    queue_size: int | None = Field(default=None, ge=1, le=1000)
    retry_limit: int | None = Field(default=None, ge=0, le=20)

    _url = field_validator("stream_url")(validate_stream_url)


class CameraStatusUpdateRequest(BaseModel):
    status: CameraStatus | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def check_at_least_one(self):
        if self.status is None and self.is_active is None:
            raise ValueError("Either status or is_active must be provided")
        return self


class CameraResponse(BaseModel):
    id: int
    camera_code: str
    camera_name: str | None = None
    name: str | None = None
    department_id: int
    location_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    jurisdiction: str | None = None
    description: str | None = None
    stream_url: str
    stream_type: str
    username_reference: str | None = None
    status: str
    is_active: bool
    sample_fps: float
    queue_size: int
    retry_limit: int
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None = None
    last_error: str | None = None

    @model_validator(mode="before")
    @classmethod
    def populate_name_synonyms(cls, data):
        if hasattr(data, "__dict__") or isinstance(data, dict):
            def get_val(key):
                return data.get(key) if isinstance(data, dict) else getattr(data, key, None)
            cname = get_val("camera_name") or get_val("name")
            if isinstance(data, dict):
                data["camera_name"] = cname
                data["name"] = cname
            else:
                return {
                    "id": getattr(data, "id", None),
                    "camera_code": getattr(data, "camera_code", None),
                    "camera_name": cname,
                    "name": cname,
                    "department_id": getattr(data, "department_id", None),
                    "location_name": getattr(data, "location_name", None),
                    "latitude": getattr(data, "latitude", None),
                    "longitude": getattr(data, "longitude", None),
                    "jurisdiction": getattr(data, "jurisdiction", None),
                    "description": getattr(data, "description", None),
                    "stream_url": getattr(data, "stream_url", None),
                    "stream_type": getattr(data, "stream_type", "RTSP"),
                    "username_reference": getattr(data, "username_reference", None),
                    "status": getattr(data, "status", "INACTIVE"),
                    "is_active": getattr(data, "is_active", True),
                    "sample_fps": getattr(data, "sample_fps", 1.0),
                    "queue_size": getattr(data, "queue_size", 8),
                    "retry_limit": getattr(data, "retry_limit", 3),
                    "created_at": getattr(data, "created_at", None),
                    "updated_at": getattr(data, "updated_at", None),
                    "last_seen_at": getattr(data, "last_seen_at", None),
                    "last_error": getattr(data, "last_error", None),
                }
        return data

    model_config = ConfigDict(from_attributes=True)


class CameraHealthResponse(BaseModel):
    camera_id: int
    camera_code: str | None = None
    status: str
    connection_status: str
    current_state: str
    last_seen_at: datetime | None = None
    failures: int = 0
    error_state: str | None = None
    last_error: str | None = None


class CameraHealthSummaryResponse(BaseModel):
    total: int
    online: int
    offline: int
    connecting: int
    error: int
    by_status: dict[str, int]


class PaginatedCamerasResponse(BaseModel):
    items: list[CameraResponse]
    total: int
    page: int = Field(ge=1)
    size: int = Field(ge=1)
