from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.department import Department


class CameraStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"
    CONNECTING = "CONNECTING"


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    camera_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        default=lambda: f"CAM-{uuid4().hex[:12].upper()}",
    )
    camera_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    department_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=False, index=True
    )
    location_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(150), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    stream_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    stream_type: Mapped[str] = mapped_column(String(20), nullable=False, default="RTSP")
    username_reference: Mapped[str | None] = mapped_column(String(150), nullable=True)
    encrypted_password: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=CameraStatus.INACTIVE.value, nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    processing_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sample_fps: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    sampling_interval: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    queue_size: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    retry_limit: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    department: Mapped[Department] = relationship("Department", lazy="select")

    # Backward compatibility synonym
    name = synonym("camera_name")
