"""
Module 11 – Analytics, Evaluation & Model Monitoring ORM Models
================================================================
Database models for the analytics layer.

Design Invariants:
    1. Analytics tables aggregate data from Modules 1–10; they do NOT store
       raw biometric data, PII, or raw CCTV frames.
    2. Evaluation results are linked to specific dataset and model versions
       so results are reproducible.
    3. Drift events and analytics alerts are technical monitoring records
       and do NOT constitute operational decisions.
    4. Model registry status changes require authorized human action.
    5. Evaluation results include the disclaimer that they are specific to
       the evaluated dataset/model/conditions and must not be automatically
       generalized.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


# ---------------------------------------------------------------------------
# Model Registry
# ---------------------------------------------------------------------------


class ModelRegistryDB(Base):
    """
    Registry of all AI model versions deployed or under evaluation.

    Every AI result in the system should be traceable back to a record
    in this table via (model_name, model_version).
    """

    __tablename__ = "model_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    model_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    """Human-readable model name, e.g. 'FACE_EMBEDDING_MODEL'."""

    model_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    """Type of model: PERSON_DETECTION, FACE_DETECTION, FACE_EMBEDDING, QUALITY, etc."""

    version: Mapped[str] = mapped_column(String(50), nullable=False)
    """Semantic version string, e.g. '1.4.2'."""

    framework: Mapped[str | None] = mapped_column(String(100), nullable=True)
    """ML framework used, e.g. 'PyTorch 2.1', 'ONNX 1.15'."""

    checksum: Mapped[str | None] = mapped_column(String(255), nullable=True)
    """SHA-256 or MD5 checksum of the model weights file for integrity verification."""

    dataset_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    """Version of the training dataset used to produce this model."""

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="TESTING", index=True
    )
    """Lifecycle status: TESTING | ACTIVE | RETIRED."""

    configuration_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    """JSON string of model configuration/hyper-parameters (no weights)."""

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Free-text notes about this model version."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    """UTC timestamp when status was set to ACTIVE."""

    retired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    """UTC timestamp when status was set to RETIRED."""


# ---------------------------------------------------------------------------
# Dataset Registry
# ---------------------------------------------------------------------------


class DatasetRegistryDB(Base):
    """
    Registry of authorized evaluation / training datasets.

    Only legitimately licensed, consented, or synthetic datasets
    should be registered here.
    """

    __tablename__ = "dataset_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    dataset_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    """Descriptive name of the dataset."""

    dataset_version: Mapped[str] = mapped_column(String(50), nullable=False)
    """Version string, e.g. '2.0', 'v1.1-synthetic'."""

    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    """Purpose: TRAINING | VALIDATION | TEST.
    TEST datasets must not be used for continuous threshold tuning."""

    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    """Data provenance: SYNTHETIC | LICENSED | CONSENTED | INTERNAL."""

    sample_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """Number of samples/records in the dataset."""

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Free-text description including licensing info and limitations."""

    creation_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    """Date the dataset was created or last updated."""

    registered_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


# ---------------------------------------------------------------------------
# Evaluation Runs
# ---------------------------------------------------------------------------


class EvaluationRunDB(Base):
    """
    A controlled evaluation run linking a model version to a dataset version.

    Results from this run allow reproducible performance measurement.
    """

    __tablename__ = "evaluation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    run_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    """Unique run identifier, e.g. 'EVAL-A3F7C1B2'."""

    run_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    """Optional human-readable name for this run."""

    dataset_registry_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("dataset_registry.id"), nullable=True, index=True
    )
    model_registry_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("model_registry.id"), nullable=True, index=True
    )

    # Denormalized for traceability even if registry rows are deleted
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(150), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(50), nullable=False)

    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    """Similarity threshold used during this evaluation run."""

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING", index=True
    )
    """Run lifecycle: PENDING | RUNNING | COMPLETED | FAILED."""

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Justification for selected threshold or configuration."""

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


# ---------------------------------------------------------------------------
# Evaluation Results
# ---------------------------------------------------------------------------


class EvaluationResultDB(Base):
    """
    Quantitative results for a completed evaluation run.

    IMPORTANT DISCLAIMER: Results are specific to the evaluated dataset,
    camera conditions, model version, and experimental configuration and
    should not automatically be generalized to other populations or
    deployment environments.
    """

    __tablename__ = "evaluation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    run_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("evaluation_runs.run_id"), nullable=False, index=True
    )

    # Confusion matrix components
    true_positives: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    false_positives: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    true_negatives: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    false_negatives: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Derived metrics (None if insufficient data)
    precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    recall: Mapped[float | None] = mapped_column(Float, nullable=True)
    f1_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    false_match_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    false_non_match_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Retrieval metrics
    top1_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    top5_retrieval_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Latency
    average_similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


# ---------------------------------------------------------------------------
# Drift Events
# ---------------------------------------------------------------------------


class DriftEventDB(Base):
    """
    Records detected statistical drift in system input distributions or model outputs.

    A drift event is a technical monitoring signal — it does NOT automatically
    trigger model retraining or threshold changes.  Human review is required.
    """

    __tablename__ = "drift_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    """DATA_DRIFT | MODEL_DRIFT."""

    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    """Name of the monitored metric, e.g. 'avg_quality_score', 'similarity_distribution'."""

    baseline_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    """Baseline metric value (prior period average)."""

    current_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    """Current metric value (recent period average)."""

    deviation: Mapped[float | None] = mapped_column(Float, nullable=True)
    """Percentage deviation from baseline."""

    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="INFO", index=True
    )
    """INFO | WARNING | CRITICAL."""

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_acknowledged: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )


# ---------------------------------------------------------------------------
# Analytics Alerts (Technical System Alerts)
# ---------------------------------------------------------------------------


class AnalyticsAlertDB(Base):
    """
    Technical system monitoring alerts generated by the analytics engine.

    These are SEPARATE from Module 9 operational alerts.
    They cover infrastructure and AI pipeline health issues.
    """

    __tablename__ = "analytics_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    """
    HIGH_LATENCY | CAMERA_OUTAGE | HIGH_ERROR_RATE | DB_FAILURE |
    QUEUE_BACKLOG | MODEL_FAILURE | INTEGRITY_FAILURE |
    UNEXPECTED_SCORE_DISTRIBUTION | POTENTIAL_DATA_DRIFT.
    """

    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="INFO", index=True
    )
    """INFO | WARNING | CRITICAL."""

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    detected_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )


# ---------------------------------------------------------------------------
# System Metrics Snapshots
# ---------------------------------------------------------------------------


class SystemMetricsSnapshotDB(Base):
    """
    Periodic snapshot of high-level system health metrics.

    Written by a background monitor; used to power trend charts
    without requiring expensive real-time aggregations.
    """

    __tablename__ = "system_metrics_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    cameras_online: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cameras_offline: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cameras_error: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    frames_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    frames_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    frames_dropped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    average_fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    api_response_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    queue_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_streams: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
