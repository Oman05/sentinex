"""
Module 7 – MatchEvent Database Model
=====================================
Database representation of match events for candidate retrieval and verification.

AI Safety Invariant:
--------------------
Every record defaults to status 'PENDING_REVIEW'.
This table stores candidate similarity rankings for Module 8 verification.
It NEVER records an automatic confirmed identity.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class MatchEventDB(Base):
    """Database table match_events."""

    __tablename__ = "match_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    track_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    camera_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    case_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    case_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # MISSING or WANTED

    # Match Scores
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    query_quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    candidate_ranking_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    search_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)

    # Decision & Verification Status
    decision_state: Mapped[str] = mapped_column(String(50), nullable=False, default="POSSIBLE_MATCH")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_REVIEW", index=True)

    # Model Versioning & Context
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, default="ANALYTICAL_V1")
    model_version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    camera_location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
