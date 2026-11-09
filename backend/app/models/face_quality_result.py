"""
Module 6 – FaceQualityResult Database Model
=============================================
Records assessment metadata for each evaluated face observation.

Privacy & Safety Invariants:
- No biometric vectors, facial embeddings, or identity decisions are stored.
- No raw face images or pixel data are persisted in this table.
- Stores only telemetry, image quality measurements, and decision gating outcomes.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class FaceQualityResultDB(Base):
    """Database model mapping to table face_quality_results."""

    __tablename__ = "face_quality_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    """Auto-incrementing primary key."""

    candidate_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    """Originating Module 5 candidate ID."""

    track_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    """Associated short-term person track ID."""

    camera_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True
    )
    """Camera ID that provided the frame."""

    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )
    """UTC timestamp when the CCTV frame was captured."""

    # Individual component scores (0.0 to 1.0)
    sharpness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    brightness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    contrast_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    face_size_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    pose_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    occlusion_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    detection_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Composite evaluation & classification
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)
    quality_status: Mapped[str] = mapped_column(String(50), nullable=False, default="POOR", index=True)
    is_match_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    passed_quality_gate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    processing_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    rejection_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Provenance
    best_frame_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
