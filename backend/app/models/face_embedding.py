"""
Module 7 – FaceEmbedding Database Model
========================================
Persists extracted biometric feature vectors and model version provenance.
Ensures feature vectors are isolated, encrypted/serialized as raw bytes,
and never exposed through public user-facing API endpoints.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class FaceEmbeddingDB(Base):
    """Database table face_embeddings."""

    __tablename__ = "face_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reference_image_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    case_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # MISSING or WANTED
    embedding_reference: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    # Model Versioning Provenance
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False, default=512)

    # Serialized L2-normalized float32 vector
    vector_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
