from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from typing import TYPE_CHECKING

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.reference_image import ReferenceImage


class CaseCategory(str, Enum):
    MISSING = "MISSING"
    WANTED = "WANTED"


class CasePriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CaseStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    UNDER_REVIEW = "UNDER_REVIEW"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    VERIFIED = "VERIFIED"
    CLOSED = "CLOSED"
    INACTIVE = "INACTIVE"


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    case_number: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    person_identifier: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    department_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=CaseStatus.DRAFT.value, index=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default=CasePriority.MEDIUM.value, index=True)
    last_known_location: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reference_images: Mapped[list[ReferenceImage]] = relationship(
        "ReferenceImage", back_populates="case", cascade="all, delete-orphan", lazy="select"
    )
