"""
Module 5 – ProcessingEvent Database Model
==========================================
Records a lightweight audit row for each processed (or failed) frame.

This table supports:
- Research evaluation: track detection rates, latency over time, FPS.
- Operational monitoring: identify problematic cameras or processing bottlenecks.
- Audit compliance: demonstrate what the system processed and when.

Privacy design
--------------
- No raw frame data, pixel data, or biometric features are stored here.
- No identity references (no case_id, no person_id).
- Only aggregate counts and processing metadata are persisted.

Retention
---------
The PROCESSING_EVENTS_ENABLED setting controls whether rows are written.
A separate data-retention policy (not implemented in this module) can purge
old rows based on created_at.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ProcessingEvent(Base):
    """
    One row per processed (or failed) CCTV frame.

    Inserted asynchronously by the AI pipeline; never blocks frame processing.
    """

    __tablename__ = "processing_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    """Auto-incrementing primary key."""

    camera_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    """ID of the camera that produced the frame."""

    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )
    """UTC capture timestamp of the originating frame."""

    frame_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """Opaque frame reference string for traceability."""

    processing_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="PROCESSED", index=True
    )
    """
    Final processing outcome for this frame.
    Values: PROCESSED | VALIDATION_FAILED | PROCESSING_ERROR
    """

    people_detected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    """Number of people detected in this frame."""

    people_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    """Synonym alias for people_detected."""

    faces_detected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    """Number of faces detected in this frame."""

    tracks_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    """Number of active tracks after this frame was processed."""

    processing_latency_ms: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    """Wall-clock time spent on detection + tracking for this frame (milliseconds)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    """Wall-clock timestamp when this event row was written."""
