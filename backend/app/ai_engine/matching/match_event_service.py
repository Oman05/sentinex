"""
Module 7 – Possible Match Event Service
=======================================
Constructs, debounces, persists, and manages PossibleMatchEvents
dispatched to Module 8: Human Verification.

AI Safety Invariant (Sections 14 & 15):
---------------------------------------
Every event status starts strictly as PENDING_REVIEW.
This module NEVER bypasses human verification.
All alerts mandate authorized human review in Module 8.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
import time
from typing import Any, Sequence

from sqlalchemy.orm import Session

from app.ai_engine.config.matching_settings import matching_settings
from app.ai_engine.schemas.matching import (
    CandidateMatchResult,
    MatchDecisionState,
    MatchEventStatus,
    PossibleMatchEvent,
)
from app.database.session import SessionLocal
from app.models.match_event import MatchEventDB
from app.services.review_service import review_service

logger = logging.getLogger(__name__)


class MatchEventService:
    """
    Manages generation, debouncing, and database lifecycle for PossibleMatchEvents.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # (track_id, case_id) -> last_event_timestamp_s
        self._cooldown_cache: dict[tuple[str, int], float] = {}

    def should_emit_event(self, track_id: str, case_id: int) -> bool:
        """
        Prevents alert flooding by enforcing a temporal cooldown
        per (track_id, case_id) pair.
        """
        now = time.time()
        key = (track_id, case_id)
        with self._lock:
            last_time = self._cooldown_cache.get(key, 0.0)
            if (now - last_time) >= matching_settings.TRACK_COOLDOWN_SECONDS:
                self._cooldown_cache[key] = now
                return True
            return False

    def create_possible_match_event(
        self,
        candidate_id: str,
        track_id: str,
        camera_id: int,
        timestamp: datetime,
        matched_candidate: CandidateMatchResult,
        query_quality_score: float,
        camera_location: str | None = None,
        model_name: str | None = None,
        model_version: str | None = None,
        db: Session | None = None,
    ) -> PossibleMatchEvent | None:
        """
        Creates a structured PossibleMatchEvent if candidate qualifies
        and cooldown policy passes.
        """
        # Only emit events for POSSIBLE_MATCH or HIGH_PRIORITY_REVIEW
        if matched_candidate.decision_state not in {
            MatchDecisionState.POSSIBLE_MATCH,
            MatchDecisionState.HIGH_PRIORITY_REVIEW,
        }:
            return None

        # Check track cooldown
        if not self.should_emit_event(track_id, matched_candidate.case_id):
            logger.debug(
                "[MatchEventService] Suppressed repeated alert for track %s, case %s (cooldown)",
                track_id,
                matched_candidate.case_id,
            )
            return None

        event = PossibleMatchEvent(
            candidate_id=candidate_id,
            track_id=track_id,
            camera_id=camera_id,
            case_id=matched_candidate.case_id,
            case_number=matched_candidate.case_number,
            category=matched_candidate.category,
            timestamp=timestamp,
            location=camera_location,
            similarity_score=matched_candidate.similarity_score,
            candidate_ranking_score=matched_candidate.candidate_ranking_score,
            query_quality_score=query_quality_score,
            reference_quality_information={
                "best_reference_image_id": matched_candidate.best_reference_image_id,
                "matched_reference_count": matched_candidate.matched_reference_count,
            },
            rank=matched_candidate.rank,
            decision_state=matched_candidate.decision_state,
            status=MatchEventStatus.PENDING_REVIEW,
            model_name=model_name or matching_settings.EMBEDDING_MODEL,
            model_version=model_version or matching_settings.EMBEDDING_MODEL_VERSION,
        )

        # Persist to database if enabled
        if matching_settings.PERSIST_MATCH_EVENTS:
            self._persist_event(event, db)

        logger.info(
            "[MatchEventService] Emitted %s for case %s (similarity: %.2f, score: %.2f)",
            event.decision_state.value,
            event.case_number,
            event.similarity_score,
            event.candidate_ranking_score,
        )

        return event

    def _persist_event(
        self, event: PossibleMatchEvent, db: Session | None = None
    ) -> None:
        """Writes match event record to match_events database table."""
        should_close = False
        if db is None:
            db = SessionLocal()
            should_close = True

        try:
            from app.models.match_event import MatchEventDB

            db_row = MatchEventDB(
                event_id=event.event_id,
                candidate_id=event.candidate_id,
                track_id=event.track_id,
                camera_id=event.camera_id,
                case_id=event.case_id,
                case_number=event.case_number,
                category=event.category,
                similarity_score=event.similarity_score,
                query_quality_score=event.query_quality_score,
                candidate_ranking_score=event.candidate_ranking_score,
                rank=event.rank,
                decision_state=event.decision_state.value,
                status=event.status.value,
                model_name=event.model_name,
                model_version=event.model_version,
                camera_location=event.location,
                created_at=event.created_at,
                updated_at=datetime.now(timezone.utc),
            )
            db.add(db_row)
            db.commit()

            # Automatic ingestion into Module 8 Review Queue
            try:
                from app.services.review_service import review_service
                review_service.create_review_event(
                    match_event_id=event.event_id,
                    case_id=event.case_id,
                    case_number=event.case_number,
                    category=event.category,
                    similarity_score=event.similarity_score,
                    candidate_ranking_score=event.candidate_ranking_score,
                    query_quality_score=event.query_quality_score,
                    rank=event.rank,
                    decision_state=event.decision_state.value,
                    camera_id=event.camera_id,
                    camera_location=event.location,
                    track_id=event.track_id,
                    model_name=event.model_name,
                    model_version=event.model_version,
                    db=db,
                )
            except Exception as r_err:
                logger.debug("[MatchEventService] Review event enqueue hook notice: %s", r_err)
        except Exception as exc:
            db.rollback()
            logger.warning("[MatchEventService] DB write error for event: %s", exc)
        finally:
            if should_close:
                db.close()

    def get_event_by_id(
        self, event_id: str, db: Session
    ) -> PossibleMatchEvent | None:
        """Retrieve a stored event by its unique event_id string."""
        from app.models.match_event import MatchEventDB

        row = db.query(MatchEventDB).filter(MatchEventDB.event_id == event_id).first()
        if not row:
            return None
        return self._to_pydantic(row)

    def list_events(
        self,
        db: Session,
        status: str | None = None,
        category: str | None = None,
        case_id: int | None = None,
        camera_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PossibleMatchEvent]:
        """List match events with optional filtering for Module 8 verification queue."""
        from app.models.match_event import MatchEventDB

        q = db.query(MatchEventDB)
        if status:
            q = q.filter(MatchEventDB.status == status.upper())
        if category:
            q = q.filter(MatchEventDB.category == category.upper())
        if case_id:
            q = q.filter(MatchEventDB.case_id == case_id)
        if camera_id:
            q = q.filter(MatchEventDB.camera_id == camera_id)

        rows = q.order_by(MatchEventDB.id.desc()).offset(offset).limit(limit).all()
        return [self._to_pydantic(r) for r in rows]

    def update_event_status(
        self,
        event_id: str,
        new_status: MatchEventStatus | str,
        db: Session,
    ) -> PossibleMatchEvent | None:
        """Module 8 hook to update review status (e.g. IN_REVIEW, VERIFIED, REJECTED)."""
        from app.models.match_event import MatchEventDB

        status_val = (
            new_status.value
            if isinstance(new_status, MatchEventStatus)
            else new_status.upper()
        )
        row = db.query(MatchEventDB).filter(MatchEventDB.event_id == event_id).first()
        if not row:
            return None

        row.status = status_val
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return self._to_pydantic(row)

    @staticmethod
    def _to_pydantic(row) -> PossibleMatchEvent:
        return PossibleMatchEvent(
            event_id=row.event_id,
            candidate_id=row.candidate_id,
            track_id=row.track_id,
            camera_id=row.camera_id,
            case_id=row.case_id,
            case_number=row.case_number,
            category=row.category,
            timestamp=row.created_at,
            location=row.camera_location,
            similarity_score=row.similarity_score,
            candidate_ranking_score=row.candidate_ranking_score,
            query_quality_score=row.query_quality_score,
            rank=row.rank,
            decision_state=MatchDecisionState(row.decision_state),
            status=MatchEventStatus(row.status),
            model_name=row.model_name,
            model_version=row.model_version,
            created_at=row.created_at,
        )


# Module-level singleton
match_event_service = MatchEventService()
