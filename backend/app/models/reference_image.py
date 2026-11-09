from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.case import Case


class ReferenceImage(Base):
    __tablename__ = "reference_images"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    storage_type: Mapped[str] = mapped_column(String(50), default="LOCAL", nullable=False)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    image_width: Mapped[int] = mapped_column(Integer, nullable=False)
    image_height: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Future-ready fields
    image_quality_status: Mapped[str | None] = mapped_column(String(50), default="PENDING", nullable=True)
    processing_status: Mapped[str | None] = mapped_column(String(50), default="PENDING", nullable=True)
    feature_reference_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Additional metadata
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Relationships
    case: Mapped[Case] = relationship("Case", back_populates="reference_images", lazy="select")

    # Backward compatibility synonyms
    stored_filename = synonym("file_name")
    original_filename = synonym("original_file_name")
    file_type = synonym("mime_type")
    width = synonym("image_width")
    height = synonym("image_height")
    uploaded_at = synonym("created_at")
