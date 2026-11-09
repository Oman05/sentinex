"""
Module 11 – Analytics, Evaluation & Model Monitoring API Router
===============================================================
Provides all analytics, evaluation, model registry, and dataset registry endpoints.

Role-based access:
  - POLICE / ADMIN: Read-only analytics overview, pipeline, matching, review, alert, evidence.
  - ADMIN only: Model registry management, dataset registry, evaluation runs, drift events,
                score distribution, threshold evaluation, technical alerts.

Privacy rules:
  - No raw biometric data, no personal identifiers, no raw case details.
  - All metrics are aggregated counts or statistical summaries.
  - Evaluation results carry an explicit generalization disclaimer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import get_current_user, require_admin, require_police
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsAlertResponse,
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
    AlertMetricsResponse,
    ScoreDistributionResponse,
    SystemHealthResponse,
    ThresholdEvaluationRequest,
    ThresholdEvaluationResult,
    CameraAnalyticsItem,
)
from app.services.analytics_service import analytics_service

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/analytics",
    tags=["Module 11 – Analytics & Evaluation"],
)

eval_router = APIRouter(
    prefix="/evaluation",
    tags=["Module 11 – Evaluation Engine"],
)

model_router = APIRouter(
    prefix="/models",
    tags=["Module 11 – Model & Dataset Registry"],
)


# ---------------------------------------------------------------------------
# Helper: parse time-range params
# ---------------------------------------------------------------------------


def _tr_params(
    time_range: str = Query("7d", description="Time range: today | 7d | 30d | custom"),
    start_date: Optional[datetime] = Query(None, description="Start date (custom range)"),
    end_date: Optional[datetime] = Query(None, description="End date (custom range)"),
) -> tuple[str, datetime | None, datetime | None]:
    if time_range == "custom" and (start_date is None or end_date is None):
        raise HTTPException(
            status_code=400,
            detail="start_date and end_date are required when time_range=custom",
        )
    return time_range, start_date, end_date


# ===========================================================================
# Analytics Endpoints
# ===========================================================================


@router.get(
    "/overview",
    response_model=OverviewResponse,
    summary="Analytics overview dashboard",
    description=(
        "Returns aggregated metrics across all pipeline stages. "
        "All metrics cover the selected time period and contain NO personal identifiers."
    ),
)
def get_overview(
    tr: tuple = Depends(_tr_params),
    db: Session = Depends(get_db),
    _: User = Depends(require_police),
) -> OverviewResponse:
    """Return full analytics overview for the dashboard."""
    time_range, start_date, end_date = tr
    return analytics_service.get_overview(db, time_range, start_date, end_date)


@router.get(
    "/system",
    response_model=SystemHealthResponse,
    summary="System health metrics",
)
def get_system_health(
    db: Session = Depends(get_db),
    _: User = Depends(require_police),
) -> SystemHealthResponse:
    """Return current system health: camera status, frame counts, latency, DB health."""
    return analytics_service.get_system_health(db)


@router.get(
    "/cameras",
    response_model=list[CameraAnalyticsItem],
    summary="Per-camera analytics",
)
def get_camera_analytics(
    tr: tuple = Depends(_tr_params),
    db: Session = Depends(get_db),
    _: User = Depends(require_police),
) -> list[CameraAnalyticsItem]:
    """Return per-camera frame, detection, and quality metrics."""
    time_range, start_date, end_date = tr
    return analytics_service.get_camera_analytics(db, time_range, start_date, end_date)


@router.get(
    "/pipeline",
    response_model=list[PipelineStageMetrics],
    summary="AI pipeline stage metrics",
)
def get_pipeline_metrics(
    tr: tuple = Depends(_tr_params),
    db: Session = Depends(get_db),
    _: User = Depends(require_police),
) -> list[PipelineStageMetrics]:
    """Return per-stage input/success/failure counts and latency across the AI pipeline."""
    time_range, start_date, end_date = tr
    return analytics_service.get_pipeline_metrics(db, time_range, start_date, end_date)


@router.get(
    "/quality",
    response_model=FaceQualityBreakdown,
    summary="Face quality assessment analytics",
)
def get_face_quality_breakdown(
    tr: tuple = Depends(_tr_params),
    db: Session = Depends(get_db),
    _: User = Depends(require_police),
) -> FaceQualityBreakdown:
    """Return face quality pass/fail rates and rejection reason breakdown."""
    time_range, start_date, end_date = tr
    return analytics_service.get_face_quality_breakdown(db, time_range, start_date, end_date)


@router.get(
    "/matching",
    response_model=MatchingMetricsResponse,
    summary="Candidate matching performance metrics",
)
def get_matching_metrics(
    tr: tuple = Depends(_tr_params),
    db: Session = Depends(get_db),
    _: User = Depends(require_police),
) -> MatchingMetricsResponse:
    """Return matching metrics: Top-1/Top-5 retrieval, FMR, FNMR, avg latency."""
    time_range, start_date, end_date = tr
    return analytics_service.get_matching_metrics(db, time_range, start_date, end_date)


@router.get(
    "/reviews",
    response_model=ReviewMetricsResponse,
    summary="Human review workflow metrics",
    description=(
        "Returns review workflow performance metrics. "
        "IMPORTANT: These metrics describe system workflow only. "
        "They must NOT be used to rank or evaluate individual reviewers."
    ),
)
def get_review_metrics(
    tr: tuple = Depends(_tr_params),
    db: Session = Depends(get_db),
    _: User = Depends(require_police),
) -> ReviewMetricsResponse:
    """Return review created/completed/pending counts and average review time."""
    time_range, start_date, end_date = tr
    return analytics_service.get_review_metrics(db, time_range, start_date, end_date)


@router.get(
    "/alerts",
    response_model=AlertMetricsResponse,
    summary="Operational alert metrics",
)
def get_alert_metrics(
    tr: tuple = Depends(_tr_params),
    db: Session = Depends(get_db),
    _: User = Depends(require_police),
) -> AlertMetricsResponse:
    """Return operational alert counts, acknowledgment times, and notification failures."""
    time_range, start_date, end_date = tr
    return analytics_service.get_alert_metrics(db, time_range, start_date, end_date)


@router.get(
    "/evidence",
    response_model=EvidenceMetricsResponse,
    summary="Evidence management metrics",
)
def get_evidence_metrics(
    tr: tuple = Depends(_tr_params),
    db: Session = Depends(get_db),
    _: User = Depends(require_police),
) -> EvidenceMetricsResponse:
    """Return evidence item counts by type, integrity check results, and storage usage."""
    time_range, start_date, end_date = tr
    return analytics_service.get_evidence_metrics(db, time_range, start_date, end_date)


@router.get(
    "/drift",
    response_model=list[DriftEventResponse],
    summary="Data & model drift events",
    description="Admin-only. Returns detected statistical drift events.",
)
def get_drift_events(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[DriftEventResponse]:
    """Return recent drift monitoring events. Advisory only — human review required."""
    return analytics_service.get_drift_events(db, limit)


@router.post(
    "/drift/check",
    response_model=list[DriftEventResponse],
    summary="Trigger drift check",
    description="Admin-only. Runs drift detection and stores any new events.",
)
def run_drift_check(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[DriftEventResponse]:
    """Run drift detection now. Returns any newly created drift events."""
    new_events = analytics_service.check_and_record_drift(db)
    return [DriftEventResponse.model_validate(e) for e in new_events]


@router.post(
    "/drift/{event_id}/acknowledge",
    response_model=DriftEventResponse,
    summary="Acknowledge a drift event",
)
def acknowledge_drift_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> DriftEventResponse:
    """Acknowledge a drift event. Does NOT trigger any automated model change."""
    return analytics_service.acknowledge_drift_event(db, event_id, current_user)


@router.get(
    "/alerts/technical",
    response_model=list[AnalyticsAlertResponse],
    summary="Technical system alerts",
    description="Admin-only. Returns infrastructure/AI pipeline health alerts.",
)
def get_technical_alerts(
    resolved: bool = Query(False),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[AnalyticsAlertResponse]:
    """Return technical system alerts (separate from Module 9 operational alerts)."""
    return analytics_service.get_analytics_alerts(db, resolved)


@router.post(
    "/alerts/technical/{alert_id}/acknowledge",
    response_model=AnalyticsAlertResponse,
    summary="Acknowledge a technical alert",
)
def acknowledge_technical_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> AnalyticsAlertResponse:
    return analytics_service.acknowledge_analytics_alert(db, alert_id, current_user)


@router.post(
    "/alerts/technical/{alert_id}/resolve",
    response_model=AnalyticsAlertResponse,
    summary="Resolve a technical alert",
)
def resolve_technical_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> AnalyticsAlertResponse:
    return analytics_service.resolve_analytics_alert(db, alert_id, current_user)


@router.get(
    "/scores/distribution",
    response_model=ScoreDistributionResponse,
    summary="Similarity score distribution for research analysis",
    description=(
        "Admin-only. Returns genuine and non-match similarity scores for threshold research. "
        "Do NOT interpret scores as guaranteed identity probabilities."
    ),
)
def get_score_distribution(
    tr: tuple = Depends(_tr_params),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ScoreDistributionResponse:
    """Return score distributions separated by human review outcome."""
    time_range, start_date, end_date = tr
    return analytics_service.get_score_distribution(db, time_range, start_date, end_date)


# ===========================================================================
# Evaluation Endpoints
# ===========================================================================


@eval_router.post(
    "/run",
    response_model=EvaluationRunResponse,
    status_code=201,
    summary="Create a new evaluation run",
    description=(
        "Admin-only. Creates a new evaluation run record. "
        "Call POST /evaluation/runs/{run_id}/execute to compute results."
    ),
)
def create_evaluation_run(
    data: EvaluationRunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> EvaluationRunResponse:
    """Create and register a new evaluation run."""
    return analytics_service.create_evaluation_run(db, data, current_user)


@eval_router.get(
    "/runs",
    response_model=list[EvaluationRunResponse],
    summary="List all evaluation runs",
)
def list_evaluation_runs(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[EvaluationRunResponse]:
    """List all evaluation runs ordered by creation date."""
    return analytics_service.list_evaluation_runs(db)


@eval_router.get(
    "/runs/{run_id}",
    response_model=EvaluationRunResponse,
    summary="Get evaluation run details",
)
def get_evaluation_run(
    run_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> EvaluationRunResponse:
    """Get details of a specific evaluation run."""
    return analytics_service.get_evaluation_run(db, run_id)


@eval_router.post(
    "/runs/{run_id}/execute",
    response_model=EvaluationResultResponse,
    summary="Execute an evaluation run",
    description=(
        "Admin-only. Computes confusion matrix, precision, recall, F1, FMR, FNMR, "
        "Top-1 and Top-5 using current system data. "
        "DISCLAIMER: Results are specific to the evaluated dataset and conditions."
    ),
)
def execute_evaluation_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> EvaluationResultResponse:
    """Execute an evaluation run and return computed metrics."""
    return analytics_service.execute_evaluation_run(db, run_id, current_user)


@eval_router.get(
    "/runs/{run_id}/results",
    response_model=EvaluationResultResponse,
    summary="Get evaluation run results",
)
def get_evaluation_results(
    run_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> EvaluationResultResponse:
    """Get computed results for a completed evaluation run."""
    return analytics_service.get_evaluation_results(db, run_id)


@eval_router.post(
    "/threshold",
    response_model=ThresholdEvaluationResult,
    summary="Evaluate a similarity threshold",
    description=(
        "Admin-only. Estimates FMR/FNMR for a given threshold. "
        "For experimental research use only. "
        "Do NOT automatically adjust production thresholds based on this result."
    ),
)
def evaluate_threshold(
    req: ThresholdEvaluationRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ThresholdEvaluationResult:
    """Estimate false match/non-match rates for a specific threshold value."""
    return analytics_service.evaluate_threshold(db, req)


# ===========================================================================
# Model Registry Endpoints
# ===========================================================================


@model_router.post(
    "/registry",
    response_model=ModelRegistryResponse,
    status_code=201,
    summary="Register a new AI model version",
)
def register_model(
    data: ModelRegistryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ModelRegistryResponse:
    """Register a new model version. Initial status is TESTING."""
    return analytics_service.register_model(db, data, current_user)


@model_router.get(
    "/registry",
    response_model=list[ModelRegistryResponse],
    summary="List model registry",
)
def list_models(
    db: Session = Depends(get_db),
    _: User = Depends(require_police),
) -> list[ModelRegistryResponse]:
    """List all registered model versions."""
    return analytics_service.list_models(db)


@model_router.get(
    "/registry/{model_id}",
    response_model=ModelRegistryResponse,
    summary="Get model details",
)
def get_model(
    model_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_police),
) -> ModelRegistryResponse:
    """Get details of a specific model version."""
    return analytics_service.get_model(db, model_id)


@model_router.post(
    "/registry/{model_id}/activate",
    response_model=ModelRegistryResponse,
    summary="Activate a model",
    description="Admin-only. Sets model status to ACTIVE. Authorized human action required.",
)
def activate_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ModelRegistryResponse:
    """Activate a model. Must be done by an authorized administrator."""
    return analytics_service.activate_model(db, model_id, current_user)


@model_router.post(
    "/registry/{model_id}/retire",
    response_model=ModelRegistryResponse,
    summary="Retire a model",
    description="Admin-only. Sets model status to RETIRED. Authorized human action required.",
)
def retire_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ModelRegistryResponse:
    """Retire a model. Must be done by an authorized administrator."""
    return analytics_service.retire_model(db, model_id, current_user)


@model_router.post(
    "/datasets",
    response_model=DatasetRegistryResponse,
    status_code=201,
    summary="Register an authorized dataset",
    description=(
        "Admin-only. Register an authorized, licensed, or synthetic dataset. "
        "Only legitimately licensed, consented, or synthetic data may be registered."
    ),
)
def register_dataset(
    data: DatasetRegistryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> DatasetRegistryResponse:
    """Register a new authorized dataset for evaluation/training tracking."""
    return analytics_service.register_dataset(db, data, current_user)


@model_router.get(
    "/datasets",
    response_model=list[DatasetRegistryResponse],
    summary="List dataset registry",
)
def list_datasets(
    db: Session = Depends(get_db),
    _: User = Depends(require_police),
) -> list[DatasetRegistryResponse]:
    """List all registered datasets."""
    return analytics_service.list_datasets(db)

# ===========================================================================
# Export & Research Report Endpoints
# ===========================================================================


@router.get(
    "/export/csv",
    summary="Export analytics overview as CSV",
    description="Authorized users can export analytics data as CSV. Creates an audit record.",
    response_class=Response,
)
def export_analytics_csv(
    tr: tuple = Depends(_tr_params),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
) -> Response:
    """Export analytics overview data as CSV. Every export creates an audit record."""
    import io
    import csv
    time_range, start_date, end_date = tr
    overview = analytics_service.get_overview(db, time_range, start_date, end_date)

    output = io.StringIO()
    writer = csv.writer(output)

    # System Health
    writer.writerow(["SYSTEM HEALTH METRICS"])
    writer.writerow(["Metric", "Value"])
    writer.writerow(["cameras_online", overview.system.cameras_online])
    writer.writerow(["cameras_offline", overview.system.cameras_offline])
    writer.writerow(["cameras_error", overview.system.cameras_error])
    writer.writerow(["frames_received", overview.system.frames_received])
    writer.writerow(["frames_processed", overview.system.frames_processed])
    writer.writerow(["frames_dropped", overview.system.frames_dropped])
    writer.writerow(["avg_latency_ms", overview.system.avg_latency_ms])
    writer.writerow([])

    # Matching
    writer.writerow(["MATCHING METRICS"])
    writer.writerow(["Metric", "Value"])
    writer.writerow(["queries_processed", overview.matching.queries_processed])
    writer.writerow(["possible_matches", overview.matching.possible_matches])
    writer.writerow(["no_candidate_results", overview.matching.no_candidate_results])
    writer.writerow(["top1_accuracy", overview.matching.top1_accuracy])
    writer.writerow(["top5_retrieval_rate", overview.matching.top5_retrieval_rate])
    writer.writerow(["fmr", overview.matching.fmr])
    writer.writerow(["fnmr", overview.matching.fnmr])
    writer.writerow([])

    # Reviews
    writer.writerow(["REVIEW METRICS"])
    writer.writerow(["Metric", "Value"])
    writer.writerow(["reviews_created", overview.reviews.reviews_created])
    writer.writerow(["reviews_completed", overview.reviews.reviews_completed])
    writer.writerow(["confirmed_for_action", overview.reviews.confirmed_for_action])
    writer.writerow(["rejected", overview.reviews.rejected])
    writer.writerow(["avg_review_time_seconds", overview.reviews.avg_review_time_seconds])
    writer.writerow([])

    # Alerts
    writer.writerow(["ALERT METRICS"])
    writer.writerow(["Metric", "Value"])
    writer.writerow(["alerts_created", overview.alerts.alerts_created])
    writer.writerow(["alerts_acknowledged", overview.alerts.alerts_acknowledged])
    writer.writerow(["alerts_resolved", overview.alerts.alerts_resolved])
    writer.writerow(["notification_failures", overview.alerts.notification_failures])
    writer.writerow([])

    writer.writerow(["EXPORT METADATA"])
    writer.writerow(["time_range", time_range])
    writer.writerow(["generated_at", overview.generated_at.isoformat()])
    writer.writerow(["exported_by_user_id", current_user.id])
    writer.writerow(["disclaimer", "These metrics are aggregated system statistics. No personal data is included."])

    content = output.getvalue()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="sentinex_analytics_{time_range}_{datetime.utcnow().strftime("%Y%m%d")}.csv"'},
    )


@router.get(
    "/export/json",
    summary="Export analytics overview as JSON",
    description="Authorized users can export analytics data as JSON.",
)
def export_analytics_json(
    tr: tuple = Depends(_tr_params),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_police),
) -> dict:
    """Export analytics overview data as JSON with metadata."""
    import json
    time_range, start_date, end_date = tr
    overview = analytics_service.get_overview(db, time_range, start_date, end_date)
    data = overview.model_dump()
    data["export_metadata"] = {
        "exported_by_user_id": current_user.id,
        "export_timestamp": datetime.utcnow().isoformat(),
        "disclaimer": (
            "These metrics are aggregated system statistics. "
            "No personal data is included. "
            "Evaluation results are specific to the evaluated dataset and must not be generalized."
        ),
    }
    return data


@router.get(
    "/report/research",
    summary="Generate research evaluation report",
    description=(
        "Admin-only. Generate a structured research report for a completed evaluation run. "
        "Includes full disclaimer per research ethics requirements."
    ),
)
def generate_research_report(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    """
    Generate a research-ready report for an evaluation run.

    IMPORTANT DISCLAIMER:
    Results are specific to the evaluated dataset, camera conditions, model version,
    and experimental configuration and should not automatically be generalized to
    other populations or deployment environments.
    """
    run = analytics_service.get_evaluation_run(db, run_id)
    try:
        results = analytics_service.get_evaluation_results(db, run_id)
        has_results = True
    except Exception:
        results = None
        has_results = False

    report = {
        "report_type": "SENTINEX Research Evaluation Report",
        "evaluation_run": {
            "run_id": run.run_id,
            "run_name": run.run_name,
            "model_name": run.model_name,
            "model_version": run.model_version,
            "dataset_name": run.dataset_name,
            "dataset_version": run.dataset_version,
            "threshold": run.threshold,
            "justification": run.justification,
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        },
        "metrics": (
            {
                "confusion_matrix": {
                    "true_positives": results.true_positives,
                    "false_positives": results.false_positives,
                    "true_negatives": results.true_negatives,
                    "false_negatives": results.false_negatives,
                },
                "precision": results.precision,
                "recall": results.recall,
                "f1_score": results.f1_score,
                "false_match_rate": results.false_match_rate,
                "false_non_match_rate": results.false_non_match_rate,
                "top1_accuracy": results.top1_accuracy,
                "top5_retrieval_rate": results.top5_retrieval_rate,
                "average_similarity_score": results.average_similarity_score,
                "average_latency_ms": results.average_latency_ms,
                "evaluated_at": results.evaluated_at.isoformat(),
            }
            if has_results
            else None
        ),
        "limitations": [
            "Metrics are computed on system data which may include human review decisions as ground truth.",
            "Performance depends on CCTV camera quality, lighting, and face angle.",
            "Results should not be used to make automated identity decisions.",
            "Human review is always required for operational decisions.",
            "This report is for research and system evaluation purposes only.",
        ],
        "disclaimer": (
            "Results are specific to the evaluated dataset, camera conditions, "
            "model version, and experimental configuration and should not "
            "automatically be generalized to other populations or deployment environments."
        ),
        "generated_at": datetime.utcnow().isoformat(),
        "generated_by_user_id": current_user.id,
    }
    return report
