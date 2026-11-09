"""
Module 11 – Analytics Service
==============================
Core analytics engine that queries Modules 1–10 tables to produce
aggregated, privacy-preserving performance metrics.

Design rules:
  1. All returned metrics are aggregated counts/statistics — no raw personal data.
  2. Evaluation results NEVER constitute operational identity decisions.
  3. Drift detection is advisory only; human review is always required before
     any model or threshold change.
  4. This service is READ-ONLY with respect to all prior module tables.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.alert import AlertDB, AlertNotificationDB
from app.models.analytics import (
    AnalyticsAlertDB,
    DatasetRegistryDB,
    DriftEventDB,
    EvaluationResultDB,
    EvaluationRunDB,
    ModelRegistryDB,
    SystemMetricsSnapshotDB,
)
from app.models.camera import Camera, CameraStatus
from app.models.evidence import EvidenceAccessLogDB, EvidenceExportDB, EvidenceItemDB
from app.models.face_quality_result import FaceQualityResultDB
from app.models.match_event import MatchEventDB
from app.models.processing_event import ProcessingEvent
from app.models.review_event import ReviewDecision, ReviewEventDB, ReviewStatus
from app.models.user import User
from app.schemas.analytics import (
    AlertMetricsResponse,
    AnalyticsAlertResponse,
    CameraAnalyticsItem,
    DatasetRegistryCreate,
    DatasetRegistryResponse,
    DriftEventResponse,
    EvaluationResultResponse,
    EvaluationRunCreate,
    EvaluationRunResponse,
    EvidenceMetricsResponse,
    FaceQualityBreakdown,
    MatchingMetricsResponse,
    ModelRegistryCreate,
    ModelRegistryResponse,
    OverviewResponse,
    PipelineStageMetrics,
    ReviewMetricsResponse,
    ScoreDistributionResponse,
    SystemHealthResponse,
    ThresholdEvaluationRequest,
    ThresholdEvaluationResult,
)

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Aggregates data from all prior modules to produce system-level analytics.
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _date_bounds(
        self,
        time_range: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[datetime | None, datetime | None]:
        """Return (from_dt, to_dt) for the requested time range."""
        now = datetime.utcnow()
        if time_range == "today":
            return now.replace(hour=0, minute=0, second=0, microsecond=0), now
        if time_range == "7d":
            return now - timedelta(days=7), now
        if time_range == "30d":
            return now - timedelta(days=30), now
        if time_range == "custom":
            return start_date, end_date
        return now - timedelta(days=7), now

    def _apply_date_filter(self, query, col, from_dt, to_dt):
        """Apply date range filter to a SQLAlchemy query."""
        if from_dt is not None:
            query = query.filter(col >= from_dt)
        if to_dt is not None:
            query = query.filter(col <= to_dt)
        return query

    def _safe_div(self, numerator: float, denominator: float) -> float | None:
        """Safe division returning None instead of ZeroDivisionError."""
        if denominator == 0:
            return None
        return numerator / denominator

    # ------------------------------------------------------------------
    # System Health
    # ------------------------------------------------------------------

    def get_system_health(self, db: Session) -> SystemHealthResponse:
        """
        Return current system health snapshot.

        Queries the cameras and recent processing_events tables.
        """
        try:
            cameras_online = (
                db.query(func.count(Camera.id))
                .filter(Camera.status == CameraStatus.ONLINE.value, Camera.is_active.is_(True))
                .scalar() or 0
            )
            cameras_offline = (
                db.query(func.count(Camera.id))
                .filter(Camera.status == CameraStatus.OFFLINE.value)
                .scalar() or 0
            )
            cameras_error = (
                db.query(func.count(Camera.id))
                .filter(Camera.status == CameraStatus.ERROR.value)
                .scalar() or 0
            )

            # Last 24 h of processing events for live metrics
            cutoff = datetime.utcnow() - timedelta(hours=24)
            pe_q = db.query(ProcessingEvent).filter(ProcessingEvent.timestamp >= cutoff)

            frames_received = pe_q.count()
            frames_processed = (
                pe_q.filter(ProcessingEvent.processing_status == "PROCESSED").count()
            )
            frames_dropped = (
                pe_q.filter(ProcessingEvent.processing_status == "FAILED").count()
            )

            avg_latency = (
                db.query(func.avg(ProcessingEvent.processing_latency_ms))
                .filter(ProcessingEvent.timestamp >= cutoff)
                .scalar()
            )

            db_healthy = True
            try:
                db.execute(__import__("sqlalchemy").text("SELECT 1"))
            except Exception:
                db_healthy = False

            return SystemHealthResponse(
                cameras_online=cameras_online,
                cameras_offline=cameras_offline,
                cameras_error=cameras_error,
                frames_received=frames_received,
                frames_processed=frames_processed,
                frames_dropped=frames_dropped,
                avg_latency_ms=round(avg_latency, 2) if avg_latency else None,
                db_healthy=db_healthy,
            )
        except Exception as exc:
            logger.error("get_system_health error: %s", exc)
            return SystemHealthResponse(db_healthy=False)

    # ------------------------------------------------------------------
    # Camera Analytics
    # ------------------------------------------------------------------

    def get_camera_analytics(
        self,
        db: Session,
        time_range: str = "7d",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[CameraAnalyticsItem]:
        """
        Return per-camera processing metrics.

        Aggregates processing_events and face_quality_results per camera.
        """
        from_dt, to_dt = self._date_bounds(time_range, start_date, end_date)
        results: list[CameraAnalyticsItem] = []

        try:
            cameras = db.query(Camera).filter(Camera.is_active.is_(True)).all()
            for cam in cameras:
                pe_q = db.query(ProcessingEvent).filter(
                    ProcessingEvent.camera_id == cam.id
                )
                pe_q = self._apply_date_filter(pe_q, ProcessingEvent.timestamp, from_dt, to_dt)

                total = pe_q.count()
                processed = pe_q.filter(ProcessingEvent.processing_status == "PROCESSED").count()
                failed = pe_q.filter(ProcessingEvent.processing_status == "FAILED").count()

                avg_latency = (
                    db.query(func.avg(ProcessingEvent.processing_latency_ms))
                    .filter(ProcessingEvent.camera_id == cam.id)
                    .scalar()
                )
                # People detected
                detections_sum = (
                    db.query(func.sum(ProcessingEvent.people_count))
                    .filter(ProcessingEvent.camera_id == cam.id)
                    .scalar() or 0
                )
                # Face candidates passed quality gate
                fq_q = db.query(FaceQualityResultDB).filter(
                    FaceQualityResultDB.camera_id == cam.id
                )
                fq_q = self._apply_date_filter(fq_q, FaceQualityResultDB.timestamp, from_dt, to_dt)
                face_candidates = fq_q.filter(FaceQualityResultDB.passed_quality_gate.is_(True)).count()

                results.append(
                    CameraAnalyticsItem(
                        camera_id=cam.id,
                        camera_name=cam.camera_name,
                        frames_received=total,
                        frames_processed=processed,
                        frames_dropped=failed,
                        avg_latency_ms=round(avg_latency, 2) if avg_latency else None,
                        detections=int(detections_sum),
                        face_candidates=face_candidates,
                        error_count=failed,
                    )
                )
        except Exception as exc:
            logger.error("get_camera_analytics error: %s", exc)

        return results

    # ------------------------------------------------------------------
    # Pipeline Stage Metrics
    # ------------------------------------------------------------------

    def get_pipeline_metrics(
        self,
        db: Session,
        time_range: str = "7d",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[PipelineStageMetrics]:
        """
        Return per-stage metrics across the full AI pipeline.

        Stages map to: CCTV Ingestion → Person Detection → Face Detection
        → Quality Assessment → Candidate Matching → Human Review → Alert Dispatch.
        """
        from_dt, to_dt = self._date_bounds(time_range, start_date, end_date)
        stages: list[PipelineStageMetrics] = []

        try:
            # Stage 1 – CCTV Ingestion (all processing events)
            pe_q = self._apply_date_filter(
                db.query(ProcessingEvent), ProcessingEvent.timestamp, from_dt, to_dt
            )
            total_frames = pe_q.count()
            failed_frames = pe_q.filter(ProcessingEvent.processing_status == "FAILED").count()
            avg_pe_lat = (
                db.query(func.avg(ProcessingEvent.processing_latency_ms))
                .filter(ProcessingEvent.timestamp >= from_dt if from_dt else True)
                .scalar()
            )
            stages.append(PipelineStageMetrics(
                stage_name="CCTV_INGESTION",
                input_count=total_frames,
                successful_count=total_frames - failed_frames,
                failed_count=failed_frames,
                avg_latency_ms=round(avg_pe_lat, 2) if avg_pe_lat else None,
                error_count=failed_frames,
            ))

            # Stage 2 – Person Detection (sum of people_count)
            detections = int(
                db.query(func.sum(ProcessingEvent.people_count))
                .filter(ProcessingEvent.timestamp >= from_dt if from_dt else True)
                .scalar() or 0
            )
            stages.append(PipelineStageMetrics(
                stage_name="PERSON_DETECTION",
                input_count=total_frames,
                successful_count=detections,
                failed_count=max(0, total_frames - detections),
                error_count=failed_frames,
            ))

            # Stage 3 – Face Detection (faces received by quality module)
            fq_q = self._apply_date_filter(
                db.query(FaceQualityResultDB), FaceQualityResultDB.timestamp, from_dt, to_dt
            )
            faces_total = fq_q.count()
            avg_fq_lat = (
                db.query(func.avg(FaceQualityResultDB.processing_time_ms))
                .filter(FaceQualityResultDB.timestamp >= from_dt if from_dt else True)
                .scalar()
            )
            stages.append(PipelineStageMetrics(
                stage_name="FACE_DETECTION",
                input_count=detections,
                successful_count=faces_total,
                failed_count=max(0, detections - faces_total),
                avg_latency_ms=round(avg_fq_lat, 2) if avg_fq_lat else None,
                error_count=0,
            ))

            # Stage 4 – Quality Assessment
            faces_passed = fq_q.filter(FaceQualityResultDB.passed_quality_gate.is_(True)).count()
            faces_rejected = faces_total - faces_passed
            stages.append(PipelineStageMetrics(
                stage_name="QUALITY_ASSESSMENT",
                input_count=faces_total,
                successful_count=faces_passed,
                failed_count=faces_rejected,
                avg_latency_ms=round(avg_fq_lat, 2) if avg_fq_lat else None,
                error_count=0,
            ))

            # Stage 5 – Candidate Matching
            me_q = self._apply_date_filter(
                db.query(MatchEventDB), MatchEventDB.created_at, from_dt, to_dt
            )
            matches_total = me_q.count()
            avg_me_lat = (
                db.query(func.avg(MatchEventDB.search_latency_ms))
                .filter(MatchEventDB.created_at >= from_dt if from_dt else True)
                .scalar()
            )
            stages.append(PipelineStageMetrics(
                stage_name="CANDIDATE_MATCHING",
                input_count=faces_passed,
                successful_count=matches_total,
                failed_count=max(0, faces_passed - matches_total),
                avg_latency_ms=round(avg_me_lat, 2) if avg_me_lat else None,
                error_count=0,
            ))

            # Stage 6 – Human Review
            re_q = self._apply_date_filter(
                db.query(ReviewEventDB), ReviewEventDB.created_at, from_dt, to_dt
            )
            reviews_total = re_q.count()
            reviews_done = re_q.filter(
                ReviewEventDB.status.in_(["COMPLETED", "CONFIRM_FOR_ACTION", "REJECTED", "NEED_MORE_EVIDENCE"])
            ).count()
            stages.append(PipelineStageMetrics(
                stage_name="HUMAN_REVIEW",
                input_count=matches_total,
                successful_count=reviews_done,
                failed_count=max(0, reviews_total - reviews_done),
                error_count=0,
            ))

            # Stage 7 – Alert Dispatch
            al_q = self._apply_date_filter(
                db.query(AlertDB), AlertDB.created_at, from_dt, to_dt
            )
            alerts_total = al_q.count()
            alerts_failed = al_q.filter(AlertDB.status == "FAILED").count()
            stages.append(PipelineStageMetrics(
                stage_name="ALERT_DISPATCH",
                input_count=reviews_done,
                successful_count=alerts_total - alerts_failed,
                failed_count=alerts_failed,
                error_count=alerts_failed,
            ))

        except Exception as exc:
            logger.error("get_pipeline_metrics error: %s", exc)

        return stages

    # ------------------------------------------------------------------
    # Face Quality
    # ------------------------------------------------------------------

    def get_face_quality_breakdown(
        self,
        db: Session,
        time_range: str = "7d",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> FaceQualityBreakdown:
        """
        Return face quality assessment breakdown from Module 6 data.
        """
        from_dt, to_dt = self._date_bounds(time_range, start_date, end_date)

        try:
            q = self._apply_date_filter(
                db.query(FaceQualityResultDB), FaceQualityResultDB.timestamp, from_dt, to_dt
            )
            total = q.count()
            passed = q.filter(FaceQualityResultDB.passed_quality_gate.is_(True)).count()
            rejected = total - passed

            avg_qs = db.query(func.avg(FaceQualityResultDB.quality_score)).scalar()
            avg_pt = db.query(func.avg(FaceQualityResultDB.processing_time_ms)).scalar()

            # Count rejection reasons
            rejection_reasons: dict[str, int] = {}
            rejected_rows = (
                q.filter(
                    FaceQualityResultDB.passed_quality_gate.is_(False),
                    FaceQualityResultDB.rejection_reason.isnot(None),
                )
                .with_entities(
                    FaceQualityResultDB.rejection_reason,
                    func.count(FaceQualityResultDB.id).label("cnt"),
                )
                .group_by(FaceQualityResultDB.rejection_reason)
                .all()
            )
            for row in rejected_rows:
                if row.rejection_reason:
                    rejection_reasons[row.rejection_reason] = row.cnt

            return FaceQualityBreakdown(
                faces_received=total,
                faces_passed=passed,
                faces_rejected=rejected,
                avg_quality_score=round(avg_qs, 4) if avg_qs else None,
                avg_processing_time_ms=round(avg_pt, 2) if avg_pt else None,
                rejection_reasons=rejection_reasons,
            )
        except Exception as exc:
            logger.error("get_face_quality_breakdown error: %s", exc)
            return FaceQualityBreakdown()

    # ------------------------------------------------------------------
    # Matching Analytics
    # ------------------------------------------------------------------

    def get_matching_metrics(
        self,
        db: Session,
        time_range: str = "7d",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> MatchingMetricsResponse:
        """
        Return candidate matching performance metrics from Module 7.

        FMR/FNMR are estimated from human review outcomes (Module 8).
        """
        from_dt, to_dt = self._date_bounds(time_range, start_date, end_date)

        try:
            me_q = self._apply_date_filter(
                db.query(MatchEventDB), MatchEventDB.created_at, from_dt, to_dt
            )
            queries = me_q.count()
            possible_matches = me_q.filter(
                MatchEventDB.decision_state == "POSSIBLE_MATCH"
            ).count()
            no_candidates = me_q.filter(
                MatchEventDB.decision_state == "NO_CANDIDATE"
            ).count()

            avg_lat = db.query(func.avg(MatchEventDB.search_latency_ms)).scalar()

            # Top-1: rank==1 events that were later confirmed / all confirmed
            confirmed_ids = (
                db.query(ReviewEventDB.match_event_id)
                .filter(ReviewEventDB.decision == ReviewDecision.CONFIRM_FOR_ACTION.value)
                .subquery()
                .select()
            )
            rejected_ids = (
                db.query(ReviewEventDB.match_event_id)
                .filter(ReviewEventDB.decision == ReviewDecision.REJECTED.value)
                .subquery()
                .select()
            )

            top1_hits = (
                me_q.filter(MatchEventDB.rank == 1)
                .filter(MatchEventDB.event_id.in_(confirmed_ids))
                .count()
            )
            top5_hits = (
                me_q.filter(MatchEventDB.rank <= 5)
                .filter(MatchEventDB.event_id.in_(confirmed_ids))
                .count()
            )
            total_confirmed = (
                me_q.filter(MatchEventDB.event_id.in_(confirmed_ids)).count()
            )
            total_rejected = (
                me_q.filter(MatchEventDB.event_id.in_(rejected_ids)).count()
            )

            # FMR = FP / (FP + TN)  → rejected_above / (rejected + true_negatives)
            # FNMR = FN / (FN + TP) → confirmed_below / (confirmed + missed)
            # Simplified: FMR ≈ rejected / (rejected + confirmed) if threshold applied
            fmr = self._safe_div(total_rejected, total_rejected + total_confirmed)
            fnmr = self._safe_div(
                total_confirmed - top1_hits, total_confirmed
            ) if total_confirmed else None

            top1 = self._safe_div(top1_hits, total_confirmed)
            top5 = self._safe_div(top5_hits, total_confirmed)

            return MatchingMetricsResponse(
                queries_processed=queries,
                candidates_retrieved=possible_matches,
                possible_matches=possible_matches,
                no_candidate_results=no_candidates,
                avg_search_latency_ms=round(avg_lat, 2) if avg_lat else None,
                top1_accuracy=round(top1, 4) if top1 is not None else None,
                top5_retrieval_rate=round(top5, 4) if top5 is not None else None,
                fmr=round(fmr, 4) if fmr is not None else None,
                fnmr=round(fnmr, 4) if fnmr is not None else None,
            )
        except Exception as exc:
            logger.error("get_matching_metrics error: %s", exc)
            return MatchingMetricsResponse()

    # ------------------------------------------------------------------
    # Human Review Metrics
    # ------------------------------------------------------------------

    def get_review_metrics(
        self,
        db: Session,
        time_range: str = "7d",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> ReviewMetricsResponse:
        """
        Return human review workflow metrics from Module 8.

        IMPORTANT: These metrics describe system workflow performance.
        They must NOT be used to rank, evaluate, or score individual reviewers.
        """
        from_dt, to_dt = self._date_bounds(time_range, start_date, end_date)

        try:
            re_q = self._apply_date_filter(
                db.query(ReviewEventDB), ReviewEventDB.created_at, from_dt, to_dt
            )
            created = re_q.count()
            pending = re_q.filter(ReviewEventDB.status == ReviewStatus.PENDING_REVIEW.value).count()
            confirmed = re_q.filter(
                ReviewEventDB.decision == ReviewDecision.CONFIRM_FOR_ACTION.value
            ).count()
            rejected = re_q.filter(
                ReviewEventDB.decision == ReviewDecision.REJECTED.value
            ).count()
            need_more = re_q.filter(
                ReviewEventDB.decision == ReviewDecision.NEED_MORE_EVIDENCE.value
            ).count()
            completed = confirmed + rejected + need_more

            # Average review time for completed reviews
            completed_rows = (
                re_q.filter(
                    ReviewEventDB.review_started_at.isnot(None),
                    ReviewEventDB.review_completed_at.isnot(None),
                ).all()
            )
            if completed_rows:
                durations = [
                    (r.review_completed_at - r.review_started_at).total_seconds()
                    for r in completed_rows
                    if r.review_completed_at and r.review_started_at
                    and r.review_completed_at > r.review_started_at
                ]
                avg_review = sum(durations) / len(durations) if durations else None
            else:
                avg_review = None

            return ReviewMetricsResponse(
                reviews_created=created,
                reviews_completed=completed,
                pending_reviews=pending,
                confirmed_for_action=confirmed,
                rejected=rejected,
                need_more_evidence=need_more,
                avg_review_time_seconds=round(avg_review, 1) if avg_review else None,
            )
        except Exception as exc:
            logger.error("get_review_metrics error: %s", exc)
            return ReviewMetricsResponse()

    # ------------------------------------------------------------------
    # Alert Metrics
    # ------------------------------------------------------------------

    def get_alert_metrics(
        self,
        db: Session,
        time_range: str = "7d",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> AlertMetricsResponse:
        """Return operational alert metrics from Module 9."""
        from_dt, to_dt = self._date_bounds(time_range, start_date, end_date)

        try:
            al_q = self._apply_date_filter(
                db.query(AlertDB), AlertDB.created_at, from_dt, to_dt
            )
            created = al_q.count()
            acknowledged = al_q.filter(
                AlertDB.status.in_(["ACKNOWLEDGED", "IN_PROGRESS", "RESOLVED", "CLOSED"])
            ).count()
            in_progress = al_q.filter(AlertDB.status == "IN_PROGRESS").count()
            resolved = al_q.filter(AlertDB.status.in_(["RESOLVED", "CLOSED"])).count()
            failed = al_q.filter(AlertDB.status == "FAILED").count()

            # Avg acknowledgment time
            acked_rows = al_q.filter(
                AlertDB.acknowledged_at.isnot(None)
            ).all()
            if acked_rows:
                ack_times = [
                    (r.acknowledged_at - r.created_at).total_seconds()
                    for r in acked_rows
                    if r.acknowledged_at and r.created_at
                ]
                avg_ack = sum(ack_times) / len(ack_times) if ack_times else None
            else:
                avg_ack = None

            # Notification failures
            notif_q = self._apply_date_filter(
                db.query(AlertNotificationDB),
                AlertNotificationDB.created_at,
                from_dt,
                to_dt,
            )
            notif_failures = notif_q.filter(AlertNotificationDB.status == "FAILED").count()

            # Avg notification latency (sent_at - created_at)
            sent_rows = notif_q.filter(AlertNotificationDB.sent_at.isnot(None)).all()
            if sent_rows:
                lat_vals = [
                    (r.sent_at - r.created_at).total_seconds() * 1000
                    for r in sent_rows
                    if r.sent_at and r.created_at
                ]
                avg_notif_lat = sum(lat_vals) / len(lat_vals) if lat_vals else None
            else:
                avg_notif_lat = None

            return AlertMetricsResponse(
                alerts_created=created,
                alerts_acknowledged=acknowledged,
                alerts_in_progress=in_progress,
                alerts_resolved=resolved,
                alerts_failed=failed,
                avg_acknowledgment_time_seconds=round(avg_ack, 1) if avg_ack else None,
                avg_notification_latency_ms=round(avg_notif_lat, 2) if avg_notif_lat else None,
                notification_failures=notif_failures,
            )
        except Exception as exc:
            logger.error("get_alert_metrics error: %s", exc)
            return AlertMetricsResponse()

    # ------------------------------------------------------------------
    # Evidence Metrics
    # ------------------------------------------------------------------

    def get_evidence_metrics(
        self,
        db: Session,
        time_range: str = "7d",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> EvidenceMetricsResponse:
        """Return evidence management metrics from Module 10."""
        from_dt, to_dt = self._date_bounds(time_range, start_date, end_date)

        try:
            ev_q = self._apply_date_filter(
                db.query(EvidenceItemDB), EvidenceItemDB.created_at, from_dt, to_dt
            )
            total = ev_q.count()
            images = ev_q.filter(EvidenceItemDB.evidence_type == "IMAGE").count()
            videos = ev_q.filter(EvidenceItemDB.evidence_type == "VIDEO").count()
            docs = ev_q.filter(
                EvidenceItemDB.evidence_type.notin_(["IMAGE", "VIDEO"])
            ).count()
            archived = ev_q.filter(EvidenceItemDB.status == "ARCHIVED").count()
            total_size = int(
                db.query(func.sum(EvidenceItemDB.file_size_bytes)).scalar() or 0
            )

            # Integrity checks / failures
            integrity_checks = ev_q.filter(
                EvidenceItemDB.integrity_status.isnot(None)
            ).count()
            integrity_failures = ev_q.filter(
                EvidenceItemDB.integrity_status == "FAILED"
            ).count()

            # Access logs in time window
            acc_q = self._apply_date_filter(
                db.query(EvidenceAccessLogDB),
                EvidenceAccessLogDB.accessed_at,
                from_dt,
                to_dt,
            )
            access_events = acc_q.count()

            # Exports
            exp_q = self._apply_date_filter(
                db.query(EvidenceExportDB),
                EvidenceExportDB.exported_at,
                from_dt,
                to_dt,
            )
            exports = exp_q.count()

            return EvidenceMetricsResponse(
                evidence_created=total,
                images=images,
                videos=videos,
                documents=docs,
                integrity_checks=integrity_checks,
                integrity_failures=integrity_failures,
                evidence_access_events=access_events,
                evidence_exports=exports,
                archived_evidence=archived,
                total_size_bytes=total_size,
            )
        except Exception as exc:
            logger.error("get_evidence_metrics error: %s", exc)
            return EvidenceMetricsResponse()

    # ------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------

    def get_overview(
        self,
        db: Session,
        time_range: str = "7d",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> OverviewResponse:
        """Return aggregated analytics overview for the dashboard."""
        return OverviewResponse(
            system=self.get_system_health(db),
            pipeline=self.get_pipeline_metrics(db, time_range, start_date, end_date),
            matching=self.get_matching_metrics(db, time_range, start_date, end_date),
            reviews=self.get_review_metrics(db, time_range, start_date, end_date),
            alerts=self.get_alert_metrics(db, time_range, start_date, end_date),
            evidence=self.get_evidence_metrics(db, time_range, start_date, end_date),
            time_range=time_range,
            generated_at=datetime.utcnow(),
        )

    # ------------------------------------------------------------------
    # Model Registry
    # ------------------------------------------------------------------

    def register_model(
        self, db: Session, data: ModelRegistryCreate, user: User
    ) -> ModelRegistryResponse:
        """Register a new AI model version in the model registry."""
        model = ModelRegistryDB(
            model_name=data.model_name,
            model_type=data.model_type,
            version=data.version,
            framework=data.framework,
            checksum=data.checksum,
            dataset_version=data.dataset_version,
            configuration_json=data.configuration_json,
            notes=data.notes,
            status="TESTING",
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        return ModelRegistryResponse.model_validate(model)

    def activate_model(
        self, db: Session, model_id: int, user: User
    ) -> ModelRegistryResponse:
        """Activate a model (set status to ACTIVE). Requires admin authorization."""
        model = db.query(ModelRegistryDB).filter(ModelRegistryDB.id == model_id).first()
        if not model:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Model not found")
        model.status = "ACTIVE"
        model.deployed_at = datetime.utcnow()
        db.commit()
        db.refresh(model)
        return ModelRegistryResponse.model_validate(model)

    def retire_model(
        self, db: Session, model_id: int, user: User
    ) -> ModelRegistryResponse:
        """Retire a model. Production model changes require authorized human action."""
        model = db.query(ModelRegistryDB).filter(ModelRegistryDB.id == model_id).first()
        if not model:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Model not found")
        model.status = "RETIRED"
        model.retired_at = datetime.utcnow()
        db.commit()
        db.refresh(model)
        return ModelRegistryResponse.model_validate(model)

    def list_models(self, db: Session) -> list[ModelRegistryResponse]:
        """List all registered model versions."""
        models = db.query(ModelRegistryDB).order_by(ModelRegistryDB.created_at.desc()).all()
        return [ModelRegistryResponse.model_validate(m) for m in models]

    def get_model(self, db: Session, model_id: int) -> ModelRegistryResponse:
        """Get a specific model by ID."""
        model = db.query(ModelRegistryDB).filter(ModelRegistryDB.id == model_id).first()
        if not model:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Model not found")
        return ModelRegistryResponse.model_validate(model)

    # ------------------------------------------------------------------
    # Dataset Registry
    # ------------------------------------------------------------------

    def register_dataset(
        self, db: Session, data: DatasetRegistryCreate, user: User
    ) -> DatasetRegistryResponse:
        """Register an authorized dataset. Only legitimate data sources may be registered."""
        dataset = DatasetRegistryDB(
            dataset_name=data.dataset_name,
            dataset_version=data.dataset_version,
            category=data.category,
            source_type=data.source_type,
            sample_count=data.sample_count,
            notes=data.notes,
            creation_date=data.creation_date,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        return DatasetRegistryResponse.model_validate(dataset)

    def list_datasets(self, db: Session) -> list[DatasetRegistryResponse]:
        """List all registered datasets."""
        datasets = (
            db.query(DatasetRegistryDB)
            .order_by(DatasetRegistryDB.registered_at.desc())
            .all()
        )
        return [DatasetRegistryResponse.model_validate(d) for d in datasets]

    # ------------------------------------------------------------------
    # Evaluation Runs
    # ------------------------------------------------------------------

    def create_evaluation_run(
        self, db: Session, data: EvaluationRunCreate, user: User
    ) -> EvaluationRunResponse:
        """Create a new evaluation run record."""
        run_id = f"EVAL-{uuid4().hex[:8].upper()}"
        run = EvaluationRunDB(
            run_id=run_id,
            run_name=data.run_name,
            model_name=data.model_name,
            model_version=data.model_version,
            dataset_name=data.dataset_name,
            dataset_version=data.dataset_version,
            threshold=data.threshold,
            notes=data.notes,
            justification=data.justification,
            dataset_registry_id=data.dataset_registry_id,
            model_registry_id=data.model_registry_id,
            created_by_user_id=user.id if user else None,
            status="PENDING",
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return EvaluationRunResponse.model_validate(run)

    def execute_evaluation_run(
        self, db: Session, run_id: str, user: User
    ) -> EvaluationResultResponse:
        """
        Execute an evaluation run by computing metrics from live data.

        Computes confusion matrix from match_events + review_events.
        DISCLAIMER: Results are specific to the current data in the system
        and the evaluated time window; they must not be generalized automatically.
        """
        run = db.query(EvaluationRunDB).filter(EvaluationRunDB.run_id == run_id).first()
        if not run:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Evaluation run not found")

        run.status = "RUNNING"
        run.started_at = datetime.utcnow()
        db.commit()

        try:
            # Join match_events with review decisions to build confusion matrix
            threshold = run.threshold or 0.70

            # TP: rank==1 match, similarity >= threshold, decision = CONFIRM_FOR_ACTION
            tp_q = (
                db.query(func.count(MatchEventDB.id))
                .join(ReviewEventDB, ReviewEventDB.match_event_id == MatchEventDB.event_id)
                .filter(
                    MatchEventDB.rank == 1,
                    MatchEventDB.similarity_score >= threshold,
                    ReviewEventDB.decision == ReviewDecision.CONFIRM_FOR_ACTION.value,
                )
                .scalar() or 0
            )

            # FP: rank==1 match, similarity >= threshold, decision = REJECTED
            fp_q = (
                db.query(func.count(MatchEventDB.id))
                .join(ReviewEventDB, ReviewEventDB.match_event_id == MatchEventDB.event_id)
                .filter(
                    MatchEventDB.rank == 1,
                    MatchEventDB.similarity_score >= threshold,
                    ReviewEventDB.decision == ReviewDecision.REJECTED.value,
                )
                .scalar() or 0
            )

            # FN: rank==1 match, similarity < threshold, decision = CONFIRM_FOR_ACTION
            fn_q = (
                db.query(func.count(MatchEventDB.id))
                .join(ReviewEventDB, ReviewEventDB.match_event_id == MatchEventDB.event_id)
                .filter(
                    MatchEventDB.rank == 1,
                    MatchEventDB.similarity_score < threshold,
                    ReviewEventDB.decision == ReviewDecision.CONFIRM_FOR_ACTION.value,
                )
                .scalar() or 0
            )

            # TN: rank==1 match, similarity < threshold, decision = REJECTED
            tn_q = (
                db.query(func.count(MatchEventDB.id))
                .join(ReviewEventDB, ReviewEventDB.match_event_id == MatchEventDB.event_id)
                .filter(
                    MatchEventDB.rank == 1,
                    MatchEventDB.similarity_score < threshold,
                    ReviewEventDB.decision == ReviewDecision.REJECTED.value,
                )
                .scalar() or 0
            )

            tp, fp, fn, tn = int(tp_q), int(fp_q), int(fn_q), int(tn_q)

            precision = self._safe_div(tp, tp + fp)
            recall = self._safe_div(tp, tp + fn)
            f1 = (
                self._safe_div(2 * precision * recall, precision + recall)
                if precision and recall
                else None
            )
            fmr = self._safe_div(fp, fp + tn)
            fnmr = self._safe_div(fn, fn + tp)

            # Top-1 and Top-5 retrieval
            confirmed_events = (
                db.query(ReviewEventDB.match_event_id)
                .filter(ReviewEventDB.decision == ReviewDecision.CONFIRM_FOR_ACTION.value)
                .subquery()
                .select()
            )
            total_confirmed = db.query(func.count(MatchEventDB.id)).filter(
                MatchEventDB.event_id.in_(confirmed_events)
            ).scalar() or 0

            top1_hits = db.query(func.count(MatchEventDB.id)).filter(
                MatchEventDB.event_id.in_(confirmed_events),
                MatchEventDB.rank == 1,
            ).scalar() or 0

            top5_hits = db.query(func.count(MatchEventDB.id)).filter(
                MatchEventDB.event_id.in_(confirmed_events),
                MatchEventDB.rank <= 5,
            ).scalar() or 0

            top1 = self._safe_div(top1_hits, total_confirmed)
            top5 = self._safe_div(top5_hits, total_confirmed)

            avg_sim = db.query(func.avg(MatchEventDB.similarity_score)).scalar()
            avg_lat = db.query(func.avg(MatchEventDB.search_latency_ms)).scalar()

            result = EvaluationResultDB(
                run_id=run_id,
                true_positives=tp,
                false_positives=fp,
                true_negatives=tn,
                false_negatives=fn,
                precision=round(precision, 4) if precision is not None else None,
                recall=round(recall, 4) if recall is not None else None,
                f1_score=round(f1, 4) if f1 is not None else None,
                false_match_rate=round(fmr, 4) if fmr is not None else None,
                false_non_match_rate=round(fnmr, 4) if fnmr is not None else None,
                top1_accuracy=round(top1, 4) if top1 is not None else None,
                top5_retrieval_rate=round(top5, 4) if top5 is not None else None,
                average_similarity_score=round(avg_sim, 4) if avg_sim else None,
                average_latency_ms=round(avg_lat, 2) if avg_lat else None,
            )
            db.add(result)

            run.status = "COMPLETED"
            run.completed_at = datetime.utcnow()
            db.commit()
            db.refresh(result)

            return EvaluationResultResponse.model_validate(result)

        except Exception as exc:
            run.status = "FAILED"
            db.commit()
            logger.error("execute_evaluation_run error for %s: %s", run_id, exc)
            raise

    def get_evaluation_run(self, db: Session, run_id: str) -> EvaluationRunResponse:
        """Get evaluation run details."""
        run = db.query(EvaluationRunDB).filter(EvaluationRunDB.run_id == run_id).first()
        if not run:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Evaluation run not found")
        return EvaluationRunResponse.model_validate(run)

    def list_evaluation_runs(self, db: Session) -> list[EvaluationRunResponse]:
        """List all evaluation runs ordered by creation date."""
        runs = (
            db.query(EvaluationRunDB)
            .order_by(EvaluationRunDB.created_at.desc())
            .all()
        )
        return [EvaluationRunResponse.model_validate(r) for r in runs]

    def get_evaluation_results(
        self, db: Session, run_id: str
    ) -> EvaluationResultResponse:
        """Get computed results for a completed evaluation run."""
        result = (
            db.query(EvaluationResultDB)
            .filter(EvaluationResultDB.run_id == run_id)
            .first()
        )
        if not result:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Results not found. Run the evaluation first.")
        return EvaluationResultResponse.model_validate(result)

    # ------------------------------------------------------------------
    # Threshold Evaluation
    # ------------------------------------------------------------------

    def evaluate_threshold(
        self, db: Session, req: ThresholdEvaluationRequest
    ) -> ThresholdEvaluationResult:
        """
        Estimate FMR/FNMR for a given similarity threshold using current data.

        This is an experimental tool only. Do NOT automatically adjust production
        thresholds based on this result alone. Human/researcher review is required.
        """
        from_dt, _ = self._date_bounds(req.time_range)
        threshold = req.threshold

        try:
            me_base = db.query(MatchEventDB).filter(MatchEventDB.rank == 1)
            if from_dt:
                me_base = me_base.filter(MatchEventDB.created_at >= from_dt)

            total = me_base.count()
            above = me_base.filter(MatchEventDB.similarity_score >= threshold).count()
            below = me_base.filter(MatchEventDB.similarity_score < threshold).count()

            confirmed_ids_subq = (
                db.query(ReviewEventDB.match_event_id)
                .filter(ReviewEventDB.decision == ReviewDecision.CONFIRM_FOR_ACTION.value)
                .subquery()
                .select()
            )
            rejected_ids_subq = (
                db.query(ReviewEventDB.match_event_id)
                .filter(ReviewEventDB.decision == ReviewDecision.REJECTED.value)
                .subquery()
                .select()
            )

            confirmed_above = (
                me_base.filter(MatchEventDB.similarity_score >= threshold)
                .filter(MatchEventDB.event_id.in_(confirmed_ids_subq))
                .count()
            )
            rejected_above = (
                me_base.filter(MatchEventDB.similarity_score >= threshold)
                .filter(MatchEventDB.event_id.in_(rejected_ids_subq))
                .count()
            )
            confirmed_below = (
                me_base.filter(MatchEventDB.similarity_score < threshold)
                .filter(MatchEventDB.event_id.in_(confirmed_ids_subq))
                .count()
            )
            rejected_below = (
                me_base.filter(MatchEventDB.similarity_score < threshold)
                .filter(MatchEventDB.event_id.in_(rejected_ids_subq))
                .count()
            )

            fmr = self._safe_div(rejected_above, rejected_above + rejected_below)
            fnmr = self._safe_div(confirmed_below, confirmed_below + confirmed_above)
            precision = self._safe_div(confirmed_above, confirmed_above + rejected_above)
            recall = self._safe_div(confirmed_above, confirmed_above + confirmed_below)

            return ThresholdEvaluationResult(
                threshold=threshold,
                time_range=req.time_range,
                total_matches_evaluated=total,
                above_threshold=above,
                below_threshold=below,
                confirmed_above=confirmed_above,
                rejected_above=rejected_above,
                confirmed_below=confirmed_below,
                rejected_below=rejected_below,
                estimated_fmr=round(fmr, 4) if fmr is not None else None,
                estimated_fnmr=round(fnmr, 4) if fnmr is not None else None,
                estimated_precision=round(precision, 4) if precision is not None else None,
                estimated_recall=round(recall, 4) if recall is not None else None,
            )
        except Exception as exc:
            logger.error("evaluate_threshold error: %s", exc)
            return ThresholdEvaluationResult(
                threshold=threshold,
                time_range=req.time_range,
                total_matches_evaluated=0,
                above_threshold=0,
                below_threshold=0,
                confirmed_above=0,
                rejected_above=0,
                confirmed_below=0,
                rejected_below=0,
            )

    # ------------------------------------------------------------------
    # Drift Detection
    # ------------------------------------------------------------------

    def check_and_record_drift(self, db: Session) -> list[DriftEventDB]:
        """
        Compare recent metrics against prior period baselines.

        If a significant deviation is detected, a DriftEventDB record is created.
        Drift events are advisory; they do NOT trigger automatic model changes.
        """
        now = datetime.utcnow()
        recent_start = now - timedelta(days=7)
        baseline_start = now - timedelta(days=14)
        baseline_end = now - timedelta(days=7)

        new_events: list[DriftEventDB] = []

        try:
            # Monitor 1: Average face quality score drift
            recent_qs = (
                db.query(func.avg(FaceQualityResultDB.quality_score))
                .filter(FaceQualityResultDB.timestamp >= recent_start)
                .scalar()
            )
            baseline_qs = (
                db.query(func.avg(FaceQualityResultDB.quality_score))
                .filter(
                    FaceQualityResultDB.timestamp >= baseline_start,
                    FaceQualityResultDB.timestamp < baseline_end,
                )
                .scalar()
            )

            if recent_qs and baseline_qs and baseline_qs > 0:
                deviation = abs(recent_qs - baseline_qs) / baseline_qs * 100
                severity = "INFO"
                if deviation > 25:
                    severity = "CRITICAL"
                elif deviation > 15:
                    severity = "WARNING"

                if deviation > 15:
                    event = DriftEventDB(
                        event_type="DATA_DRIFT",
                        metric_name="avg_quality_score",
                        baseline_value=round(float(baseline_qs), 4),
                        current_value=round(float(recent_qs), 4),
                        deviation=round(deviation, 2),
                        severity=severity,
                        description=(
                            f"Average face quality score changed by {deviation:.1f}% "
                            f"from baseline {baseline_qs:.3f} to {recent_qs:.3f}. "
                            "Human review of camera/data quality recommended."
                        ),
                    )
                    db.add(event)
                    new_events.append(event)

            # Monitor 2: Similarity score distribution drift
            recent_sim = (
                db.query(func.avg(MatchEventDB.similarity_score))
                .filter(MatchEventDB.created_at >= recent_start)
                .scalar()
            )
            baseline_sim = (
                db.query(func.avg(MatchEventDB.similarity_score))
                .filter(
                    MatchEventDB.created_at >= baseline_start,
                    MatchEventDB.created_at < baseline_end,
                )
                .scalar()
            )

            if recent_sim and baseline_sim and baseline_sim > 0:
                sim_deviation = abs(recent_sim - baseline_sim) / baseline_sim * 100
                if sim_deviation > 20:
                    severity = "CRITICAL" if sim_deviation > 35 else "WARNING"
                    event = DriftEventDB(
                        event_type="MODEL_DRIFT",
                        metric_name="avg_similarity_score",
                        baseline_value=round(float(baseline_sim), 4),
                        current_value=round(float(recent_sim), 4),
                        deviation=round(sim_deviation, 2),
                        severity=severity,
                        description=(
                            f"Similarity score distribution shifted by {sim_deviation:.1f}%. "
                            "Authorized researcher review required before any model change."
                        ),
                    )
                    db.add(event)
                    new_events.append(event)

            if new_events:
                db.commit()

        except Exception as exc:
            logger.error("check_and_record_drift error: %s", exc)

        return new_events

    def get_drift_events(
        self, db: Session, limit: int = 50
    ) -> list[DriftEventResponse]:
        """Return recent drift events."""
        events = (
            db.query(DriftEventDB)
            .order_by(DriftEventDB.detected_at.desc())
            .limit(limit)
            .all()
        )
        return [DriftEventResponse.model_validate(e) for e in events]

    def acknowledge_drift_event(
        self, db: Session, event_id: int, user: User
    ) -> DriftEventResponse:
        """Acknowledge a drift event."""
        event = db.query(DriftEventDB).filter(DriftEventDB.id == event_id).first()
        if not event:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Drift event not found")
        event.is_acknowledged = True
        event.acknowledged_at = datetime.utcnow()
        event.acknowledged_by_user_id = user.id
        db.commit()
        db.refresh(event)
        return DriftEventResponse.model_validate(event)

    # ------------------------------------------------------------------
    # Analytics Alerts (Technical System Alerts)
    # ------------------------------------------------------------------

    def get_analytics_alerts(
        self, db: Session, resolved: bool = False
    ) -> list[AnalyticsAlertResponse]:
        """Return technical system alerts. Separate from Module 9 operational alerts."""
        q = db.query(AnalyticsAlertDB).filter(
            AnalyticsAlertDB.is_resolved == resolved
        ).order_by(AnalyticsAlertDB.detected_at.desc())
        return [AnalyticsAlertResponse.model_validate(a) for a in q.all()]

    def acknowledge_analytics_alert(
        self, db: Session, alert_id: int, user: User
    ) -> AnalyticsAlertResponse:
        """Acknowledge a technical analytics alert."""
        alert = db.query(AnalyticsAlertDB).filter(AnalyticsAlertDB.id == alert_id).first()
        if not alert:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Alert not found")
        alert.is_acknowledged = True
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by_user_id = user.id
        db.commit()
        db.refresh(alert)
        return AnalyticsAlertResponse.model_validate(alert)

    def resolve_analytics_alert(
        self, db: Session, alert_id: int, user: User
    ) -> AnalyticsAlertResponse:
        """Mark a technical analytics alert as resolved."""
        alert = db.query(AnalyticsAlertDB).filter(AnalyticsAlertDB.id == alert_id).first()
        if not alert:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Alert not found")
        alert.is_resolved = True
        alert.resolved_at = datetime.utcnow()
        db.commit()
        db.refresh(alert)
        return AnalyticsAlertResponse.model_validate(alert)

    def create_analytics_alert(
        self,
        db: Session,
        alert_type: str,
        severity: str,
        title: str,
        description: str | None = None,
    ) -> AnalyticsAlertDB:
        """Create a new technical system alert."""
        alert = AnalyticsAlertDB(
            alert_type=alert_type,
            severity=severity,
            title=title,
            description=description,
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert

    # ------------------------------------------------------------------
    # Score Distribution
    # ------------------------------------------------------------------

    def get_score_distribution(
        self,
        db: Session,
        time_range: str = "30d",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> ScoreDistributionResponse:
        """
        Return similarity score distributions for confirmed matches vs rejected pairs.

        Genuine scores: similarity values where human examiner confirmed match.
        Non-match scores: similarity values where human examiner rejected.

        These distributions are used for research threshold analysis only.
        """
        from_dt, to_dt = self._date_bounds(time_range, start_date, end_date)

        try:
            confirmed_ids = (
                db.query(ReviewEventDB.match_event_id)
                .filter(ReviewEventDB.decision == ReviewDecision.CONFIRM_FOR_ACTION.value)
                .subquery()
                .select()
            )
            rejected_ids = (
                db.query(ReviewEventDB.match_event_id)
                .filter(ReviewEventDB.decision == ReviewDecision.REJECTED.value)
                .subquery()
                .select()
            )

            genuine_rows = (
                db.query(MatchEventDB.similarity_score)
                .filter(MatchEventDB.event_id.in_(confirmed_ids))
                .filter(MatchEventDB.created_at >= from_dt if from_dt else True)
                .limit(500)
                .all()
            )
            non_match_rows = (
                db.query(MatchEventDB.similarity_score)
                .filter(MatchEventDB.event_id.in_(rejected_ids))
                .filter(MatchEventDB.created_at >= from_dt if from_dt else True)
                .limit(500)
                .all()
            )

            genuine_scores = [float(r[0]) for r in genuine_rows if r[0] is not None]
            non_match_scores = [float(r[0]) for r in non_match_rows if r[0] is not None]

            avg_genuine = sum(genuine_scores) / len(genuine_scores) if genuine_scores else None
            avg_non_match = sum(non_match_scores) / len(non_match_scores) if non_match_scores else None

            return ScoreDistributionResponse(
                genuine_scores=genuine_scores,
                non_match_scores=non_match_scores,
                threshold=0.70,
                total_genuine=len(genuine_scores),
                total_non_match=len(non_match_scores),
                avg_genuine_score=round(avg_genuine, 4) if avg_genuine else None,
                avg_non_match_score=round(avg_non_match, 4) if avg_non_match else None,
            )
        except Exception as exc:
            logger.error("get_score_distribution error: %s", exc)
            return ScoreDistributionResponse()


analytics_service = AnalyticsService()
