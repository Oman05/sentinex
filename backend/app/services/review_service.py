"""
Module 8 – Review Service
==========================
Business logic for the Human Verification & Investigation Dashboard.

Implements:
- Review event creation from Module 7 match events
- Status transitions: PENDING_REVIEW → UNDER_REVIEW → terminal state
- Audit trail (append-only; no DELETE or UPDATE on audit rows)
- Investigation task management
- Module 9 notification hook

AI Safety Invariant:
    This service NEVER sets status to "IDENTITY_CONFIRMED".
    ReviewDecision.CONFIRM_FOR_ACTION is an operational decision made by
    a human examiner — it authorises the next investigative step only.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.review_event import (
    InvestigationTaskDB,
    ReviewAuditLogDB,
    ReviewDecision,
    ReviewEventDB,
    ReviewStatus,
    TaskPriority,
    TaskStatus,
)
from app.models.user import User
from app.schemas.review import (
    AssignRequest,
    EvidenceRequestRequest,
    InvestigationTaskCreate,
    InvestigationTaskResponse,
    Module9NotificationPayload,
    ReviewAuditEntry,
    ReviewDashboardStats,
    ReviewDecisionRequest,
    ReviewEventDetail,
    ReviewEventSummary,
    ReviewHistory,
    StartReviewRequest,
    TaskUpdateRequest,
    TrackHistory,
    NotificationItem,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Status transition guard
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[str, set[str]] = {
    ReviewStatus.PENDING_REVIEW.value: {ReviewStatus.UNDER_REVIEW.value},
    ReviewStatus.UNDER_REVIEW.value: {
        ReviewStatus.CONFIRMED_FOR_ACTION.value,
        ReviewStatus.REJECTED.value,
        ReviewStatus.NEED_MORE_EVIDENCE.value,
    },
    # Terminal states — no further transitions
    ReviewStatus.CONFIRMED_FOR_ACTION.value: set(),
    ReviewStatus.REJECTED.value: set(),
    ReviewStatus.NEED_MORE_EVIDENCE.value: {ReviewStatus.UNDER_REVIEW.value},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# ReviewService
# ---------------------------------------------------------------------------


class ReviewService:
    """Orchestrates all Module 8 review workflow operations."""

    # ------------------------------------------------------------------
    # Review Event — Creation
    # ------------------------------------------------------------------

    def create_review_event(
        self,
        match_event_id: str,
        case_id: int,
        case_number: str,
        category: str,
        similarity_score: float,
        candidate_ranking_score: float,
        query_quality_score: Optional[float],
        rank: Optional[int],
        decision_state: str,
        camera_id: Optional[int],
        camera_location: Optional[str],
        track_id: Optional[str],
        model_name: Optional[str],
        model_version: Optional[str],
        db: Session,
        priority: Optional[str] = None,
        face_quality_label: Optional[str] = None,
        observation_count: Optional[int] = None,
        detection_quality_score: Optional[float] = None,
    ) -> ReviewEventDB:
        """
        Create a new ReviewEvent record from a Module 7 PossibleMatchEvent.
        Idempotent: returns existing record if match_event_id already exists.
        """
        existing = (
            db.query(ReviewEventDB)
            .filter(ReviewEventDB.match_event_id == match_event_id)
            .first()
        )
        if existing:
            logger.info(
                "[ReviewService] ReviewEvent already exists for match_event_id=%s", match_event_id
            )
            return existing

        row = ReviewEventDB(
            match_event_id=match_event_id,
            case_id=case_id,
            case_number=case_number,
            category=category,
            similarity_score=similarity_score,
            candidate_ranking_score=candidate_ranking_score,
            query_quality_score=query_quality_score,
            rank=rank,
            decision_state=decision_state,
            camera_id=camera_id,
            camera_location=camera_location,
            track_id=track_id,
            model_name=model_name,
            model_version=model_version,
            priority=priority,
            face_quality_label=face_quality_label,
            observation_count=observation_count,
            detection_quality_score=detection_quality_score,
            status=ReviewStatus.PENDING_REVIEW.value,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        logger.info(
            "[ReviewService] Created ReviewEvent id=%d for match_event_id=%s",
            row.id, match_event_id,
        )
        return row

    # ------------------------------------------------------------------
    # Review Event — Queries
    # ------------------------------------------------------------------

    def get_event(self, review_event_id: int, db: Session) -> Optional[ReviewEventDB]:
        return db.query(ReviewEventDB).filter(ReviewEventDB.id == review_event_id).first()

    def get_event_by_match_id(
        self, match_event_id: str, db: Session
    ) -> Optional[ReviewEventDB]:
        return (
            db.query(ReviewEventDB)
            .filter(ReviewEventDB.match_event_id == match_event_id)
            .first()
        )

    def list_events(
        self,
        db: Session,
        status: Optional[str] = None,
        category: Optional[str] = None,
        case_id: Optional[int] = None,
        assigned_to: Optional[int] = None,
        search: Optional[str] = None,
        priority: Optional[str] = None,
        camera_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ReviewEventDB]:
        q = db.query(ReviewEventDB)
        if status:
            q = q.filter(ReviewEventDB.status == status.upper())
        if category:
            q = q.filter(ReviewEventDB.category == category.upper())
        if case_id:
            q = q.filter(ReviewEventDB.case_id == case_id)
        if assigned_to is not None:
            q = q.filter(ReviewEventDB.assigned_to == assigned_to)
        if search:
            search_pattern = f"%{search}%"
            from sqlalchemy import or_
            q = q.filter(
                or_(
                    ReviewEventDB.case_number.ilike(search_pattern),
                    ReviewEventDB.match_event_id.ilike(search_pattern),
                    ReviewEventDB.track_id.ilike(search_pattern)
                )
            )
        if priority:
            q = q.filter(ReviewEventDB.priority == priority.upper())
        if camera_id is not None:
            q = q.filter(ReviewEventDB.camera_id == camera_id)
        if date_from:
            q = q.filter(ReviewEventDB.created_at >= date_from)
        if date_to:
            q = q.filter(ReviewEventDB.created_at <= date_to)
        return q.order_by(ReviewEventDB.id.desc()).offset(offset).limit(limit).all()

    # ------------------------------------------------------------------
    # Review Event — Start Review
    # ------------------------------------------------------------------

    def start_review(
        self,
        review_event_id: int,
        examiner: User,
        payload: StartReviewRequest,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> ReviewEventDB:
        """Claim and start reviewing an event. Transitions PENDING_REVIEW → UNDER_REVIEW."""
        row = self._get_or_404(review_event_id, db)
        self._assert_valid_transition(row.status, ReviewStatus.UNDER_REVIEW.value)

        prev = row.status
        row.status = ReviewStatus.UNDER_REVIEW.value
        row.assigned_to = examiner.id
        row.review_started_at = _now()
        row.updated_at = _now()
        db.commit()
        db.refresh(row)

        self._append_audit(
            db=db,
            row=row,
            actor=examiner,
            action="START_REVIEW",
            previous_status=prev,
            new_status=row.status,
            notes=payload.notes,
            ip_address=ip_address,
        )
        logger.info(
            "[ReviewService] Examiner %s started review on event id=%d",
            examiner.username, row.id,
        )
        return row

    # ------------------------------------------------------------------
    # Review Event — Decision
    # ------------------------------------------------------------------

    def submit_decision(
        self,
        review_event_id: int,
        examiner: User,
        payload: ReviewDecisionRequest,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> tuple[ReviewEventDB, Optional[Module9NotificationPayload]]:
        """
        Submit an examiner decision.

        Returns (updated_row, module9_payload).
        module9_payload is non-None only when decision == CONFIRM_FOR_ACTION.

        AI Safety: the decision value NEVER equals "IDENTITY_CONFIRMED".
        """
        row = self._get_or_404(review_event_id, db)

        # Map ReviewDecision → ReviewStatus
        decision_to_status = {
            ReviewDecision.CONFIRM_FOR_ACTION: ReviewStatus.CONFIRMED_FOR_ACTION,
            ReviewDecision.REJECTED: ReviewStatus.REJECTED,
            ReviewDecision.NEED_MORE_EVIDENCE: ReviewStatus.NEED_MORE_EVIDENCE,
        }
        new_status = decision_to_status[payload.decision]
        self._assert_valid_transition(row.status, new_status.value)

        prev = row.status
        row.status = new_status.value
        row.decision = payload.decision.value
        row.decision_notes = payload.notes
        row.decision_at = _now()
        row.updated_at = _now()
        db.commit()
        db.refresh(row)

        self._append_audit(
            db=db,
            row=row,
            actor=examiner,
            action=payload.decision.value,
            previous_status=prev,
            new_status=row.status,
            notes=payload.notes,
            ip_address=ip_address,
        )

        module9_payload: Optional[Module9NotificationPayload] = None
        if payload.decision == ReviewDecision.CONFIRM_FOR_ACTION:
            module9_payload = Module9NotificationPayload(
                review_event_id=row.id,
                match_event_id=row.match_event_id,
                case_id=row.case_id,
                case_number=row.case_number,
                category=row.category,
                similarity_score=row.similarity_score,
                examiner_confirmed_for_action=True,
                examiner_user_id=examiner.id,
                examiner_notes=payload.notes,
                decision_at=row.decision_at,
            )
            self._dispatch_module9(row, module9_payload, db)

        logger.info(
            "[ReviewService] Examiner %s submitted decision=%s for event id=%d",
            examiner.username, payload.decision.value, row.id,
        )
        return row, module9_payload

    # ------------------------------------------------------------------
    # Review Event — Evidence Request
    # ------------------------------------------------------------------

    def request_evidence(
        self,
        review_event_id: int,
        examiner: User,
        payload: EvidenceRequestRequest,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> ReviewEventDB:
        """Record an evidence request from the examiner."""
        row = self._get_or_404(review_event_id, db)

        if row.status not in {
            ReviewStatus.UNDER_REVIEW.value,
            ReviewStatus.NEED_MORE_EVIDENCE.value,
        }:
            from fastapi import HTTPException, status as http_status
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="Evidence requests can only be made when event is UNDER_REVIEW or NEED_MORE_EVIDENCE.",
            )

        row.evidence_request_notes = payload.notes
        row.status = ReviewStatus.NEED_MORE_EVIDENCE.value
        row.updated_at = _now()
        db.commit()
        db.refresh(row)

        self._append_audit(
            db=db,
            row=row,
            actor=examiner,
            action="EVIDENCE_REQUEST",
            previous_status=ReviewStatus.UNDER_REVIEW.value,
            new_status=ReviewStatus.NEED_MORE_EVIDENCE.value,
            notes=payload.notes,
            ip_address=ip_address,
        )
        return row

    # ------------------------------------------------------------------
    # Review Event — Assign
    # ------------------------------------------------------------------

    def assign_event(
        self,
        review_event_id: int,
        assigner: User,
        payload: AssignRequest,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> ReviewEventDB:
        """Assign or re-assign a review event to an examiner."""
        row = self._get_or_404(review_event_id, db)

        # Verify target examiner exists
        from app.models.user import User as UserModel
        target_user = db.query(UserModel).filter(UserModel.id == payload.examiner_user_id).first()
        if not target_user or not target_user.is_active:
            from fastapi import HTTPException, status as http_status
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Examiner user_id={payload.examiner_user_id} not found or inactive.",
            )

        prev_assignee = row.assigned_to
        row.assigned_to = payload.examiner_user_id
        row.updated_at = _now()
        db.commit()
        db.refresh(row)

        self._append_audit(
            db=db,
            row=row,
            actor=assigner,
            action="ASSIGN",
            previous_status=row.status,
            new_status=row.status,
            notes=payload.notes if payload.notes else f"Assigned to user_id={payload.examiner_user_id} (was {prev_assignee}).",
            ip_address=ip_address,
        )
        return row

    # ------------------------------------------------------------------
    # Review Event — History
    # ------------------------------------------------------------------

    def get_history(self, review_event_id: int, db: Session) -> ReviewHistory:
        """Return full audit log for a review event."""
        row = self._get_or_404(review_event_id, db)
        audit_rows = (
            db.query(ReviewAuditLogDB)
            .filter(ReviewAuditLogDB.review_event_id == review_event_id)
            .order_by(ReviewAuditLogDB.timestamp.asc())
            .all()
        )
        entries = [ReviewAuditEntry.model_validate(a) for a in audit_rows]
        return ReviewHistory(
            review_event_id=row.id,
            match_event_id=row.match_event_id,
            case_number=row.case_number,
            entries=entries,
        )

    # ------------------------------------------------------------------
    # Dashboard Analytics & Statistics
    # ------------------------------------------------------------------

    def get_dashboard_stats(self, db: Session) -> ReviewDashboardStats:
        """Calculate operational metrics, category breakdowns, and task stats for the dashboard."""
        from sqlalchemy import func

        total_events = db.query(func.count(ReviewEventDB.id)).scalar() or 0
        pending_review = (
            db.query(func.count(ReviewEventDB.id))
            .filter(ReviewEventDB.status == ReviewStatus.PENDING_REVIEW.value)
            .scalar()
            or 0
        )
        under_review = (
            db.query(func.count(ReviewEventDB.id))
            .filter(ReviewEventDB.status == ReviewStatus.UNDER_REVIEW.value)
            .scalar()
            or 0
        )
        confirmed_for_action = (
            db.query(func.count(ReviewEventDB.id))
            .filter(ReviewEventDB.status == ReviewStatus.CONFIRMED_FOR_ACTION.value)
            .scalar()
            or 0
        )
        rejected = (
            db.query(func.count(ReviewEventDB.id))
            .filter(ReviewEventDB.status == ReviewStatus.REJECTED.value)
            .scalar()
            or 0
        )
        need_more_evidence = (
            db.query(func.count(ReviewEventDB.id))
            .filter(ReviewEventDB.status == ReviewStatus.NEED_MORE_EVIDENCE.value)
            .scalar()
            or 0
        )
        missing_count = (
            db.query(func.count(ReviewEventDB.id))
            .filter(ReviewEventDB.category == "MISSING")
            .scalar()
            or 0
        )
        wanted_count = (
            db.query(func.count(ReviewEventDB.id))
            .filter(ReviewEventDB.category == "WANTED")
            .scalar()
            or 0
        )

        total_tasks = db.query(func.count(InvestigationTaskDB.id)).scalar() or 0
        open_tasks = (
            db.query(func.count(InvestigationTaskDB.id))
            .filter(InvestigationTaskDB.status == TaskStatus.OPEN.value)
            .scalar()
            or 0
        )
        in_progress_tasks = (
            db.query(func.count(InvestigationTaskDB.id))
            .filter(InvestigationTaskDB.status.in_([TaskStatus.IN_PROGRESS.value, TaskStatus.ASSIGNED.value]))
            .scalar()
            or 0
        )
        completed_tasks = (
            db.query(func.count(InvestigationTaskDB.id))
            .filter(InvestigationTaskDB.status == TaskStatus.COMPLETED.value)
            .scalar()
            or 0
        )

        return ReviewDashboardStats(
            total_events=total_events,
            pending_review=pending_review,
            under_review=under_review,
            confirmed_for_action=confirmed_for_action,
            rejected=rejected,
            need_more_evidence=need_more_evidence,
            missing_category_count=missing_count,
            wanted_category_count=wanted_count,
            total_tasks=total_tasks,
            open_tasks=open_tasks,
            in_progress_tasks=in_progress_tasks,
            completed_tasks=completed_tasks,
        )

    # ------------------------------------------------------------------
    # Investigation Tasks
    # ------------------------------------------------------------------

    def create_task(
        self,
        payload: InvestigationTaskCreate,
        creator: User,
        db: Session,
    ) -> InvestigationTaskDB:
        """Create an investigation task after a CONFIRM_FOR_ACTION decision."""
        review_row = self._get_or_404(payload.review_event_id, db)

        # Only allow task creation after confirm-for-action
        if review_row.status != ReviewStatus.CONFIRMED_FOR_ACTION.value:
            from fastapi import HTTPException, status as http_status
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="Investigation tasks can only be created after CONFIRM_FOR_ACTION decision.",
            )

        task = InvestigationTaskDB(
            review_event_id=payload.review_event_id,
            case_id=review_row.case_id,
            case_number=review_row.case_number,
            title=payload.title,
            description=payload.description,
            priority=payload.priority.value if payload.priority else TaskPriority.MEDIUM.value,
            assigned_to=payload.assigned_to,
            created_by=creator.id,
            due_date=payload.due_date,
            status=TaskStatus.OPEN.value,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    def list_tasks(
        self,
        db: Session,
        status: Optional[str] = None,
        case_id: Optional[int] = None,
        assigned_to: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[InvestigationTaskDB]:
        q = db.query(InvestigationTaskDB)
        if status:
            q = q.filter(InvestigationTaskDB.status == status.upper())
        if case_id:
            q = q.filter(InvestigationTaskDB.case_id == case_id)
        if assigned_to is not None:
            q = q.filter(InvestigationTaskDB.assigned_to == assigned_to)
        return q.order_by(InvestigationTaskDB.id.desc()).offset(offset).limit(limit).all()

    def update_task(
        self,
        task_id: int,
        payload: TaskUpdateRequest,
        actor: User,
        db: Session,
    ) -> InvestigationTaskDB:
        task = db.query(InvestigationTaskDB).filter(InvestigationTaskDB.id == task_id).first()
        if not task:
            from fastapi import HTTPException, status as http_status
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Task not found.")
        if payload.status:
            task.status = payload.status.value
            if payload.status == TaskStatus.COMPLETED:
                task.completed_at = _now()
        if payload.assigned_to is not None:
            task.assigned_to = payload.assigned_to
        if payload.resolution_notes is not None:
            task.resolution_notes = payload.resolution_notes
        if payload.due_date is not None:
            task.due_date = payload.due_date
        task.updated_at = _now()
        db.commit()
        db.refresh(task)
        return task

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _get_or_404(self, review_event_id: int, db: Session) -> ReviewEventDB:
        row = db.query(ReviewEventDB).filter(ReviewEventDB.id == review_event_id).first()
        if not row:
            from fastapi import HTTPException, status as http_status
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"ReviewEvent id={review_event_id} not found.",
            )
        return row

    @staticmethod
    def _assert_valid_transition(current: str, target: str) -> None:
        allowed = _VALID_TRANSITIONS.get(current, set())
        if target not in allowed:
            from fastapi import HTTPException, status as http_status
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=(
                    f"Invalid status transition: {current} → {target}. "
                    f"Allowed transitions from {current}: {sorted(allowed) or 'none (terminal state)'}."
                ),
            )

    @staticmethod
    def _append_audit(
        db: Session,
        row: ReviewEventDB,
        actor: User,
        action: str,
        previous_status: Optional[str],
        new_status: Optional[str],
        notes: Optional[str],
        ip_address: Optional[str],
    ) -> None:
        """Append-only audit entry. Must never DELETE or UPDATE audit rows."""
        entry = ReviewAuditLogDB(
            review_event_id=row.id,
            actor_id=actor.id,
            actor_username=actor.username,
            action=action,
            previous_status=previous_status,
            new_status=new_status,
            notes=notes,
            ip_address=ip_address,
            timestamp=_now(),
        )
        db.add(entry)
        db.commit()

    def get_track_history(self, track_id: str, db: Session) -> TrackHistory:
        events = db.query(ReviewEventDB).filter(ReviewEventDB.track_id == track_id).all()
        if not events:
            from fastapi import HTTPException, status as http_status
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Track not found.")
        from app.schemas.review import TrackHistory, TrackObservation
        observations = []
        for i, ev in enumerate(events):
            obs = TrackObservation(
                observation_id=f"obs_{ev.id}_{i}",
                timestamp=ev.created_at,
                quality_label=ev.face_quality_label or "FAIR",
                quality_score=ev.detection_quality_score or 0.5,
                frame_number=i * 10
            )
            observations.append(obs)
        best_obs_id = None
        if observations:
            best_obs = max(observations, key=lambda x: x.quality_score)
            best_obs_id = best_obs.observation_id
        return TrackHistory(
            track_id=track_id,
            observations=observations,
            best_quality_observation_id=best_obs_id
        )

    def get_notifications(self, user_id: int, db: Session, limit: int = 20) -> list[NotificationItem]:
        from app.schemas.review import NotificationItem
        from sqlalchemy import or_
        audit_logs = (
            db.query(ReviewAuditLogDB)
            .join(ReviewEventDB, ReviewAuditLogDB.review_event_id == ReviewEventDB.id)
            .filter(or_(ReviewAuditLogDB.actor_id == user_id, ReviewEventDB.assigned_to == user_id))
            .order_by(ReviewAuditLogDB.timestamp.desc())
            .limit(limit)
            .all()
        )
        notifications = []
        for log in audit_logs:
            notifications.append(
                NotificationItem(
                    id=log.id,
                    event_type=log.action,
                    title=f"New {log.action} activity",
                    message=log.notes or f"Activity {log.action} recorded.",
                    review_event_id=log.review_event_id,
                    is_read=False,
                    created_at=log.timestamp
                )
            )
        return notifications

    def mark_notification_read(self, notification_id: int, db: Session) -> None:
        pass

    @staticmethod
    def _dispatch_module9(
        row: ReviewEventDB,
        payload: Module9NotificationPayload,
        db: Session,
    ) -> None:
        """
        Module 9 integration hook.

        Dispatches operational alert generation through Module 9 alert engine.
        """
        logger.info(
            "[ReviewService → Module9] CONFIRM_FOR_ACTION dispatched for "
            "review_event_id=%d, case=%s, similarity=%.4f (HUMAN DECISION — NOT identity confirmation)",
            row.id, row.case_number, row.similarity_score,
        )
        row.module9_notified = True
        db.commit()

        try:
            import asyncio
            from app.services.alert_service import alert_service
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(alert_service.create_alert_from_review_event(row, db))
            except RuntimeError:
                asyncio.run(alert_service.create_alert_from_review_event(row, db))
        except Exception as exc:
            logger.warning("[ReviewService → Module9] Alert dispatch background task error: %s", exc)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

review_service = ReviewService()
