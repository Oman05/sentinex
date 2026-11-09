from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class SystemConfigItem(BaseModel):
    id: int
    category: str
    key: str
    value: Any
    value_type: str
    description: str | None = None
    is_secret: bool = False
    requires_restart: bool = False
    updated_at: str

    model_config = {"from_attributes": True}


class SystemConfigUpdateItem(BaseModel):
    key: str
    value: Any
    reason: str = Field(..., min_length=3, max_length=255)


class SystemConfigUpdateRequest(BaseModel):
    updates: list[SystemConfigUpdateItem]
    confirmation: bool = Field(default=True, description="Explicit confirmation for configuration change")


class SystemConfigAuditItem(BaseModel):
    id: int
    category: str
    key: str
    old_value: str | None
    new_value: str
    changed_by_user_id: int | None
    changed_at: str
    reason: str | None

    model_config = {"from_attributes": True}


class BackupItem(BaseModel):
    id: int
    backup_id: str
    filename: str
    filepath: str
    backup_type: str
    size_bytes: int
    duration_seconds: float
    status: str
    checksum_sha256: str
    verification_status: str
    created_at: str
    created_by_user_id: int | None = None
    notes: str | None = None

    model_config = {"from_attributes": True}


class BackupCreateRequest(BaseModel):
    backup_type: str = Field(default="FULL", pattern="^(FULL|CONFIG|DATABASE)$")
    notes: str | None = None


class BackupVerifyResponse(BaseModel):
    backup_id: str
    is_valid: bool
    status: str
    checksum_sha256: str
    details: str


class BackupRestoreRequest(BaseModel):
    confirmation_code: str = Field(..., description="Must enter 'CONFIRM_RESTORE' to proceed")


class WorkerStatusItem(BaseModel):
    worker_name: str
    display_name: str
    status: str
    current_job: str | None = None
    queue_size: int = 0
    jobs_processed: int = 0
    jobs_failed: int = 0
    avg_processing_time_ms: float = 0.0
    last_heartbeat: str


class AdminDashboardMetrics(BaseModel):
    total_users: int
    active_departments: int
    registered_cameras: int
    online_cameras: int
    offline_cameras: int
    active_cases: int
    pending_human_reviews: int
    confirmed_for_action_events: int
    active_alerts: int
    system_health: str
    ai_model_status: str
    database_status: str
    storage_status: str
    worker_status: str
    recent_security_events: list[dict[str, Any]]


class CameraAdminCreateRequest(BaseModel):
    camera_name: str = Field(..., min_length=2, max_length=150)
    department_id: int
    location_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    jurisdiction: str | None = None
    # Accepts RTSP/HTTP URLs, local device indices (e.g. "0"), and file paths
    stream_url: str = Field(..., min_length=1, max_length=2048)
    # WEBCAM added so laptop/built-in cameras can be registered
    stream_type: str = Field(default="RTSP", pattern="^(RTSP|HTTP|FILE|WEBCAM|HTTPS)$")
    processing_enabled: bool = True
    sample_fps: float = Field(default=1.0, ge=0.1, le=30.0)
    sampling_interval: float = Field(default=1.0, ge=0.1, le=60.0)
    queue_size: int = Field(default=8, ge=1, le=64)
    retry_limit: int = Field(default=3, ge=0, le=10)
    username: str | None = None
    password: str | None = None


class CameraAdminUpdateRequest(BaseModel):
    camera_name: str | None = None
    department_id: int | None = None
    location_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    jurisdiction: str | None = None
    stream_url: str | None = None
    stream_type: str | None = None
    processing_enabled: bool | None = None
    sample_fps: float | None = None
    sampling_interval: float | None = None
    is_active: bool | None = None
    status: str | None = None


class CameraAdminResponse(BaseModel):
    id: int
    camera_code: str
    camera_name: str
    department_id: int
    location_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    jurisdiction: str | None = None
    stream_type: str
    status: str
    is_active: bool
    processing_enabled: bool
    sample_fps: float
    sampling_interval: float
    created_at: str
    updated_at: str
    last_seen_at: str | None = None
    last_error: str | None = None

    model_config = {"from_attributes": True}


class DepartmentStatsResponse(BaseModel):
    department_id: int
    department_name: str
    total_users: int
    total_cameras: int
    online_cameras: int
    total_cases: int
    total_alerts_dispatched: int
    total_alerts_received: int
