"""
Module 11 – Analytics & Evaluation Pydantic Schemas
====================================================
Request/response schemas for the analytics API.

Privacy notes:
  - No raw biometric data, PII, or case details are included.
  - All metrics are aggregated counts or statistical summaries.
  - Evaluation results carry an explicit generalization disclaimer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Common helpers
# ---------------------------------------------------------------------------


TimeRange = Literal["today", "7d", "30d", "custom"]


# ---------------------------------------------------------------------------
# System Health
# ---------------------------------------------------------------------------


class SystemHealthResponse(BaseModel):
    cameras_online: int = 0
    cameras_offline: int = 0
    cameras_error: int = 0
    frames_received: int = 0
    frames_processed: int = 0
    frames_dropped: int = 0
    avg_fps: float | None = None
    avg_latency_ms: float | None = None
    api_response_time_ms: float | None = None
    queue_size: int | None = None
    db_healthy: bool = True

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Camera Analytics
# ---------------------------------------------------------------------------


class CameraAnalyticsItem(BaseModel):
    camera_id: int
    camera_name: str
    frames_received: int = 0
    frames_processed: int = 0
    frames_dropped: int = 0
    avg_fps: float | None = None
    avg_latency_ms: float | None = None
    detections: int = 0
    face_candidates: int = 0
    stream_uptime_pct: float | None = None
    error_count: int = 0

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Pipeline Stage Metrics
# ---------------------------------------------------------------------------


class PipelineStageMetrics(BaseModel):
    stage_name: str
    input_count: int = 0
    successful_count: int = 0
    failed_count: int = 0
    avg_latency_ms: float | None = None
    error_count: int = 0

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Face Quality
# ---------------------------------------------------------------------------


class FaceQualityBreakdown(BaseModel):
    faces_received: int = 0
    faces_passed: int = 0
    faces_rejected: int = 0
    avg_quality_score: float | None = None
    avg_processing_time_ms: float | None = None
    rejection_reasons: dict[str, int] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Matching Metrics
# ---------------------------------------------------------------------------


class MatchingMetricsResponse(BaseModel):
    queries_processed: int = 0
    candidates_retrieved: int = 0
    possible_matches: int = 0
    no_candidate_results: int = 0
    avg_search_latency_ms: float | None = None
    top1_accuracy: float | None = None
    top5_retrieval_rate: float | None = None
    fmr: float | None = None
    fnmr: float | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Human Review Metrics
# ---------------------------------------------------------------------------


class ReviewMetricsResponse(BaseModel):
    reviews_created: int = 0
    reviews_completed: int = 0
    pending_reviews: int = 0
    confirmed_for_action: int = 0
    rejected: int = 0
    need_more_evidence: int = 0
    avg_review_time_seconds: float | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Alert Metrics
# ---------------------------------------------------------------------------


class AlertMetricsResponse(BaseModel):
    alerts_created: int = 0
    alerts_acknowledged: int = 0
    alerts_in_progress: int = 0
    alerts_resolved: int = 0
    alerts_failed: int = 0
    avg_acknowledgment_time_seconds: float | None = None
    avg_notification_latency_ms: float | None = None
    notification_failures: int = 0

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Evidence Metrics
# ---------------------------------------------------------------------------


class EvidenceMetricsResponse(BaseModel):
    evidence_created: int = 0
    images: int = 0
    videos: int = 0
    documents: int = 0
    integrity_checks: int = 0
    integrity_failures: int = 0
    evidence_access_events: int = 0
    evidence_exports: int = 0
    archived_evidence: int = 0
    total_size_bytes: int = 0

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Overview (Aggregated Dashboard)
# ---------------------------------------------------------------------------


class OverviewResponse(BaseModel):
    system: SystemHealthResponse
    pipeline: list[PipelineStageMetrics]
    matching: MatchingMetricsResponse
    reviews: ReviewMetricsResponse
    alerts: AlertMetricsResponse
    evidence: EvidenceMetricsResponse
    time_range: str
    generated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Model Registry
# ---------------------------------------------------------------------------


class ModelRegistryCreate(BaseModel):
    model_name: str = Field(..., max_length=100)
    model_type: str = Field(..., max_length=50)
    version: str = Field(..., max_length=50)
    framework: str | None = Field(None, max_length=100)
    checksum: str | None = Field(None, max_length=255)
    dataset_version: str | None = Field(None, max_length=50)
    configuration_json: str | None = None
    notes: str | None = None


class ModelRegistryUpdate(BaseModel):
    notes: str | None = None
    configuration_json: str | None = None
    framework: str | None = None
    checksum: str | None = None
    dataset_version: str | None = None


class ModelRegistryResponse(BaseModel):
    id: int
    model_name: str
    model_type: str
    version: str
    framework: str | None
    checksum: str | None
    dataset_version: str | None
    status: str
    configuration_json: str | None
    notes: str | None
    created_at: datetime
    deployed_at: datetime | None
    retired_at: datetime | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Dataset Registry
# ---------------------------------------------------------------------------


class DatasetRegistryCreate(BaseModel):
    dataset_name: str = Field(..., max_length=150)
    dataset_version: str = Field(..., max_length=50)
    category: Literal["TRAINING", "VALIDATION", "TEST"]
    source_type: str = Field(..., max_length=50)
    sample_count: int | None = None
    notes: str | None = None
    creation_date: datetime | None = None


class DatasetRegistryResponse(BaseModel):
    id: int
    dataset_name: str
    dataset_version: str
    category: str
    source_type: str
    sample_count: int | None
    notes: str | None
    creation_date: datetime | None
    registered_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Evaluation Runs
# ---------------------------------------------------------------------------


class EvaluationRunCreate(BaseModel):
    run_name: str | None = None
    model_name: str = Field(..., max_length=100)
    model_version: str = Field(..., max_length=50)
    dataset_name: str = Field(..., max_length=150)
    dataset_version: str = Field(..., max_length=50)
    threshold: float | None = Field(None, ge=0.0, le=1.0)
    notes: str | None = None
    justification: str | None = None
    dataset_registry_id: int | None = None
    model_registry_id: int | None = None


class EvaluationRunResponse(BaseModel):
    id: int
    run_id: str
    run_name: str | None
    model_name: str
    model_version: str
    dataset_name: str
    dataset_version: str
    threshold: float | None
    status: str
    notes: str | None
    justification: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Evaluation Results
# ---------------------------------------------------------------------------


class ConfusionMatrixData(BaseModel):
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    precision: float | None = None
    recall: float | None = None
    f1_score: float | None = None
    false_match_rate: float | None = None
    false_non_match_rate: float | None = None

    model_config = {"from_attributes": True}


class EvaluationResultResponse(BaseModel):
    id: int
    run_id: str
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float | None
    recall: float | None
    f1_score: float | None
    false_match_rate: float | None
    false_non_match_rate: float | None
    top1_accuracy: float | None
    top5_retrieval_rate: float | None
    average_similarity_score: float | None
    average_latency_ms: float | None
    evaluated_at: datetime
    disclaimer: str = (
        "Results are specific to the evaluated dataset, camera conditions, "
        "model version, and experimental configuration and should not "
        "automatically be generalized to other populations or deployment environments."
    )

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Threshold Evaluation
# ---------------------------------------------------------------------------


class ThresholdEvaluationRequest(BaseModel):
    threshold: float = Field(..., ge=0.0, le=1.0)
    time_range: TimeRange = "30d"


class ThresholdEvaluationResult(BaseModel):
    threshold: float
    time_range: str
    total_matches_evaluated: int
    above_threshold: int
    below_threshold: int
    confirmed_above: int
    rejected_above: int
    confirmed_below: int
    rejected_below: int
    estimated_fmr: float | None = None
    estimated_fnmr: float | None = None
    estimated_precision: float | None = None
    estimated_recall: float | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Drift Events
# ---------------------------------------------------------------------------


class DriftEventResponse(BaseModel):
    id: int
    event_type: str
    metric_name: str
    baseline_value: float | None
    current_value: float | None
    deviation: float | None
    severity: str
    description: str | None
    is_acknowledged: bool
    detected_at: datetime
    acknowledged_at: datetime | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Analytics Alerts
# ---------------------------------------------------------------------------


class AnalyticsAlertResponse(BaseModel):
    id: int
    alert_type: str
    severity: str
    title: str
    description: str | None
    is_resolved: bool
    is_acknowledged: bool
    detected_at: datetime
    resolved_at: datetime | None
    acknowledged_at: datetime | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Score Distribution
# ---------------------------------------------------------------------------


class ScoreDistributionResponse(BaseModel):
    genuine_scores: list[float] = Field(default_factory=list)
    """Similarity scores for pairs confirmed as matches by human examiners."""

    non_match_scores: list[float] = Field(default_factory=list)
    """Similarity scores for pairs rejected by human examiners."""

    threshold: float = 0.70
    total_genuine: int = 0
    total_non_match: int = 0
    avg_genuine_score: float | None = None
    avg_non_match_score: float | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# System Metrics Snapshot
# ---------------------------------------------------------------------------


class SystemMetricsSnapshotResponse(BaseModel):
    id: int
    snapshot_at: datetime
    cameras_online: int
    cameras_offline: int
    cameras_error: int
    frames_received: int
    frames_processed: int
    frames_dropped: int
    average_fps: float | None
    average_latency_ms: float | None

    model_config = {"from_attributes": True}
