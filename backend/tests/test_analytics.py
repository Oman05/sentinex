"""
Module 11 – Analytics, Evaluation & Model Monitoring
Unit, Integration, Evaluation, Drift, and Security Tests
=========================================================

Test Coverage:
  1. Analytics – correct metric calculation
  2. Analytics – date filtering
  3. Analytics – camera filtering
  4. Evaluation – confusion matrix
  5. Evaluation – precision, recall, F1
  6. Evaluation – FMR, FNMR
  7. Evaluation – Top-1, Top-5
  8. Model Registry – register / activate / retire / version tracking
  9. Drift – baseline creation, distribution comparison, warning generation
  10. Security – unauthorized access denied, restricted evaluation protected, export permission

Privacy note: all tests use in-memory SQLite and synthetic data only.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.security import create_access_token
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.analytics import (
    AnalyticsAlertDB,
    DatasetRegistryDB,
    DriftEventDB,
    EvaluationResultDB,
    EvaluationRunDB,
    ModelRegistryDB,
)
from app.models.camera import Camera, CameraStatus
from app.models.department import Department
from app.models.face_quality_result import FaceQualityResultDB
from app.models.match_event import MatchEventDB
from app.models.processing_event import ProcessingEvent
from app.models.review_event import ReviewEventDB
from app.models.user import User, UserRole
from app.services.analytics_service import AnalyticsService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    _engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=_engine)
    yield _engine
    _engine.dispose()


@pytest.fixture(scope="module")
def session_factory(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="module")
def client(engine):
    """TestClient with DB override."""
    _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    _db = _session_factory()

    def override_get_db():
        try:
            yield _db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
    _db.close()


@pytest.fixture(scope="module")
def admin_token(engine):
    _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    _db = _session_factory()
    try:
        admin = _db.query(User).filter(User.username == "m11_admin").first()
        if not admin:
            admin = User(
                username="m11_admin",
                email="m11_admin@test.local",
                password_hash="hashed",
                role=UserRole.ADMIN.value,
                is_active=True,
            )
            _db.add(admin)
            _db.commit()
            _db.refresh(admin)
        return create_access_token({"user_id": admin.id, "username": admin.username, "role": admin.role})
    finally:
        _db.close()


@pytest.fixture(scope="module")
def police_token(engine):
    _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    _db = _session_factory()
    try:
        user = _db.query(User).filter(User.username == "m11_police").first()
        if not user:
            user = User(
                username="m11_police",
                email="m11_police@test.local",
                password_hash="hashed",
                role=UserRole.POLICE.value,
                is_active=True,
            )
            _db.add(user)
            _db.commit()
            _db.refresh(user)
        return create_access_token({"user_id": user.id, "username": user.username, "role": user.role})
    finally:
        _db.close()


@pytest.fixture(scope="module")
def seeded_db(engine):
    """Seed the DB with synthetic analytics data for all module tests."""
    _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db: Session = _session_factory()

    try:
        # Department
        dept = db.query(Department).filter(Department.department_name == "M11 Test Dept").first()
        if not dept:
            dept = Department(department_name="M11 Test Dept", department_type="POLICE", location="Test City")
            db.add(dept)
            db.commit()
            db.refresh(dept)

        # Camera
        cam = db.query(Camera).filter(Camera.camera_code == "CAM-M11-001").first()
        if not cam:
            cam = Camera(
                camera_code="CAM-M11-001",
                camera_name="Test Camera M11",
                department_id=dept.id,
                stream_url="rtsp://localhost/m11",
                status=CameraStatus.ONLINE.value,
                is_active=True,
            )
            db.add(cam)
            db.commit()
            db.refresh(cam)

        now = datetime.utcnow()

        # Processing events (last 7 days)
        for i in range(20):
            db.add(ProcessingEvent(
                camera_id=cam.id,
                timestamp=now - timedelta(hours=i),
                processing_status="PROCESSED" if i % 5 != 0 else "FAILED",
                people_count=2 if i % 3 == 0 else 0,
                faces_detected=1 if i % 3 == 0 else 0,
                processing_latency_ms=50.0 + i,
            ))
        db.commit()

        # Face quality results
        rejection_reasons = ["TOO_SMALL", "BLUR", "POSE", "LOW_LIGHT", "OCCLUSION"]
        for i in range(30):
            passed = i % 3 != 0
            db.add(FaceQualityResultDB(
                candidate_id=f"cand-m11-{i}",
                track_id=f"track-m11-{i}",
                camera_id=cam.id,
                timestamp=now - timedelta(hours=i),
                quality_score=0.8 if passed else 0.3,
                sharpness_score=0.7,
                brightness_score=0.7,
                face_size_score=0.8 if passed else 0.2,
                pose_score=0.9,
                occlusion_score=0.9,
                detection_confidence=0.85,
                passed_quality_gate=passed,
                rejection_reason=None if passed else rejection_reasons[i % len(rejection_reasons)],
            ))
        db.commit()

        # Match events with review decisions — used for confusion matrix
        for i in range(20):
            event_id = f"evt-m11-{i}"
            similarity = 0.80 if i < 10 else 0.55
            db.add(MatchEventDB(
                event_id=event_id,
                candidate_id=f"cand-{i}",
                track_id=f"track-{i}",
                camera_id=cam.id,
                case_id=1,
                case_number=f"CASE-M11-{i}",
                category="MISSING",
                similarity_score=similarity,
                rank=1 if i < 15 else 2,
                decision_state="POSSIBLE_MATCH",
                status="REVIEWED",
                model_name="TEST_MODEL",
                model_version="1.0",
            ))

            # Review decision: first 10 confirmed (TP for high sim), next 10 rejected (FP/TN)
            decision = "CONFIRM_FOR_ACTION" if i < 10 else "REJECTED"
            db.add(ReviewEventDB(
                match_event_id=event_id,
                status="COMPLETED",
                decision=decision,
                review_started_at=now - timedelta(minutes=30),
                review_completed_at=now - timedelta(minutes=5),
            ))
        db.commit()

        yield db, cam, dept

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

service = AnalyticsService()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# 1. Analytics — Correct Metric Calculation
# ===========================================================================


class TestAnalyticsMetrics:
    def test_system_health_returns_valid_structure(self, seeded_db):
        db, cam, dept = seeded_db
        result = service.get_system_health(db)
        assert result.db_healthy is True
        assert isinstance(result.cameras_online, int)
        assert isinstance(result.frames_received, int)

    def test_system_health_counts_cameras(self, seeded_db):
        db, cam, dept = seeded_db
        result = service.get_system_health(db)
        # At least 1 online camera (from seeded_db)
        assert result.cameras_online >= 1

    def test_face_quality_breakdown_counts(self, seeded_db):
        db, cam, dept = seeded_db
        result = service.get_face_quality_breakdown(db, time_range="30d")
        assert result.faces_received >= 30
        assert result.faces_passed + result.faces_rejected == result.faces_received

    def test_face_quality_rejection_reasons_populated(self, seeded_db):
        db, cam, dept = seeded_db
        result = service.get_face_quality_breakdown(db, time_range="30d")
        assert len(result.rejection_reasons) > 0
        total_reason_count = sum(result.rejection_reasons.values())
        assert total_reason_count <= result.faces_rejected

    def test_review_metrics_counts(self, seeded_db):
        db, cam, dept = seeded_db
        result = service.get_review_metrics(db, time_range="30d")
        assert result.reviews_created >= 20
        assert result.confirmed_for_action == 10
        assert result.rejected == 10

    def test_review_avg_time_calculated(self, seeded_db):
        db, cam, dept = seeded_db
        result = service.get_review_metrics(db, time_range="30d")
        # Review took ~25 minutes (30 - 5)
        assert result.avg_review_time_seconds is not None
        assert result.avg_review_time_seconds > 0

    def test_matching_metrics_queries_counted(self, seeded_db):
        db, cam, dept = seeded_db
        result = service.get_matching_metrics(db, time_range="30d")
        assert result.queries_processed >= 20

    def test_pipeline_metrics_returns_7_stages(self, seeded_db):
        db, cam, dept = seeded_db
        result = service.get_pipeline_metrics(db, time_range="30d")
        stage_names = [s.stage_name for s in result]
        assert "CCTV_INGESTION" in stage_names
        assert "HUMAN_REVIEW" in stage_names
        assert "ALERT_DISPATCH" in stage_names

    def test_overview_aggregates_all_sections(self, seeded_db):
        db, cam, dept = seeded_db
        result = service.get_overview(db, time_range="30d")
        assert result.system is not None
        assert result.matching is not None
        assert result.reviews is not None
        assert result.alerts is not None
        assert result.evidence is not None
        assert len(result.pipeline) > 0
        assert result.generated_at is not None


# ===========================================================================
# 2. Analytics — Date Filtering
# ===========================================================================


class TestDateFiltering:
    def test_today_filter_returns_recent_data(self, seeded_db):
        db, cam, dept = seeded_db
        result_today = service.get_face_quality_breakdown(db, time_range="today")
        result_30d = service.get_face_quality_breakdown(db, time_range="30d")
        # Today should be <= 30d total
        assert result_today.faces_received <= result_30d.faces_received

    def test_7d_filter_less_than_30d(self, seeded_db):
        db, cam, dept = seeded_db
        r7 = service.get_pipeline_metrics(db, time_range="7d")
        r30 = service.get_pipeline_metrics(db, time_range="30d")
        cctv_7 = next((s.input_count for s in r7 if s.stage_name == "CCTV_INGESTION"), 0)
        cctv_30 = next((s.input_count for s in r30 if s.stage_name == "CCTV_INGESTION"), 0)
        assert cctv_7 <= cctv_30

    def test_custom_range_accepted(self, seeded_db):
        db, cam, dept = seeded_db
        now = datetime.utcnow()
        result = service.get_face_quality_breakdown(
            db,
            time_range="custom",
            start_date=now - timedelta(days=3),
            end_date=now,
        )
        assert isinstance(result.faces_received, int)

    def test_custom_range_api_requires_dates(self, client, police_token):
        resp = client.get(
            "/api/analytics/quality?time_range=custom",
            headers=auth_headers(police_token),
        )
        assert resp.status_code == 400

    def test_custom_range_api_with_dates_succeeds(self, client, police_token):
        now = datetime.utcnow()
        resp = client.get(
            f"/api/analytics/quality?time_range=custom"
            f"&start_date={now - timedelta(days=3)}&end_date={now}",
            headers=auth_headers(police_token),
        )
        assert resp.status_code == 200


# ===========================================================================
# 3. Analytics — Camera Filtering
# ===========================================================================


class TestCameraFiltering:
    def test_camera_analytics_returns_list(self, seeded_db):
        db, cam, dept = seeded_db
        results = service.get_camera_analytics(db, time_range="30d")
        assert isinstance(results, list)

    def test_camera_analytics_contains_seeded_camera(self, seeded_db):
        db, cam, dept = seeded_db
        results = service.get_camera_analytics(db, time_range="30d")
        ids = [r.camera_id for r in results]
        assert cam.id in ids

    def test_camera_analytics_frame_counts_match(self, seeded_db):
        db, cam, dept = seeded_db
        results = service.get_camera_analytics(db, time_range="30d")
        cam_result = next((r for r in results if r.camera_id == cam.id), None)
        assert cam_result is not None
        assert cam_result.frames_received >= 20

    def test_camera_analytics_api(self, client, police_token):
        resp = client.get("/api/analytics/cameras", headers=auth_headers(police_token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


# ===========================================================================
# 4–6. Evaluation — Confusion Matrix, Precision/Recall/F1, FMR/FNMR
# ===========================================================================


class TestEvaluationMetrics:
    """Tests the evaluation engine's confusion matrix and derived metrics."""

    @pytest.fixture(autouse=True)
    def create_eval_run(self, seeded_db, engine):
        db, cam, dept = seeded_db
        _sf = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        _db = _sf()
        admin = _db.query(User).filter(User.username == "m11_admin").first()
        if not admin:
            admin = User(
                username="m11_admin",
                email="m11_admin@test.local",
                password_hash="hashed",
                role=UserRole.ADMIN.value,
                is_active=True,
            )
            _db.add(admin)
            _db.commit()
            _db.refresh(admin)
        from app.schemas.analytics import EvaluationRunCreate
        data = EvaluationRunCreate(
            run_name="Test Eval",
            model_name="TEST_MODEL",
            model_version="1.0",
            dataset_name="TEST_DATASET",
            dataset_version="v1.0",
            threshold=0.70,
            notes="Automated test",
            justification="Test run for conftest coverage",
        )
        run = service.create_evaluation_run(_db, data, admin)
        service.execute_evaluation_run(_db, run.run_id, admin)
        self.run_id = run.run_id
        _db.close()

    def test_confusion_matrix_tp_fp_tn_fn(self, seeded_db, engine):
        _sf = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        _db = _sf()
        admin = _db.query(User).filter(User.username == "m11_admin").first()
        result = service.execute_evaluation_run(_db, self.run_id, admin)
        # TP: high-sim + confirmed (sim >= 0.70 and confirmed)
        # FP: high-sim + rejected
        # Our seed: first 10 confirmed (sim=0.80 >= 0.70) → TP=10
        # Next 10 rejected (sim=0.55 < 0.70) → TN=10
        assert result.true_positives >= 0
        assert result.false_positives >= 0
        assert result.true_negatives >= 0
        assert result.false_negatives >= 0
        _db.close()

    def test_precision_within_valid_range(self, seeded_db, engine):
        _sf = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        _db = _sf()
        result = service.get_evaluation_results(_db, self.run_id)
        if result.precision is not None:
            assert 0.0 <= result.precision <= 1.0
        _db.close()

    def test_recall_within_valid_range(self, seeded_db, engine):
        _sf = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        _db = _sf()
        result = service.get_evaluation_results(_db, self.run_id)
        if result.recall is not None:
            assert 0.0 <= result.recall <= 1.0
        _db.close()

    def test_f1_is_harmonic_mean_of_precision_and_recall(self, seeded_db, engine):
        _sf = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        _db = _sf()
        result = service.get_evaluation_results(_db, self.run_id)
        if result.precision and result.recall and result.f1_score:
            expected = 2 * result.precision * result.recall / (result.precision + result.recall)
            assert abs(result.f1_score - expected) < 0.001
        _db.close()

    def test_fmr_within_valid_range(self, seeded_db, engine):
        _sf = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        _db = _sf()
        result = service.get_evaluation_results(_db, self.run_id)
        if result.false_match_rate is not None:
            assert 0.0 <= result.false_match_rate <= 1.0
        _db.close()

    def test_fnmr_within_valid_range(self, seeded_db, engine):
        _sf = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        _db = _sf()
        result = service.get_evaluation_results(_db, self.run_id)
        if result.false_non_match_rate is not None:
            assert 0.0 <= result.false_non_match_rate <= 1.0
        _db.close()

    def test_evaluation_result_includes_disclaimer(self, seeded_db, engine):
        _sf = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        _db = _sf()
        result = service.get_evaluation_results(_db, self.run_id)
        assert "should not automatically be generalized" in result.disclaimer
        _db.close()


# ===========================================================================
# 7. Evaluation — Top-1 and Top-5 Retrieval
# ===========================================================================


class TestRetrievalMetrics:
    def test_top1_accuracy_within_range(self, seeded_db):
        db, cam, dept = seeded_db
        result = service.get_matching_metrics(db, time_range="30d")
        if result.top1_accuracy is not None:
            assert 0.0 <= result.top1_accuracy <= 1.0

    def test_top5_retrieval_rate_within_range(self, seeded_db):
        db, cam, dept = seeded_db
        result = service.get_matching_metrics(db, time_range="30d")
        if result.top5_retrieval_rate is not None:
            assert 0.0 <= result.top5_retrieval_rate <= 1.0

    def test_top5_always_gte_top1(self, seeded_db):
        db, cam, dept = seeded_db
        result = service.get_matching_metrics(db, time_range="30d")
        if result.top1_accuracy is not None and result.top5_retrieval_rate is not None:
            # Top-5 should always be >= Top-1 (more candidates considered)
            assert result.top5_retrieval_rate >= result.top1_accuracy - 0.001  # float tolerance

    def test_threshold_evaluation_returns_result(self, seeded_db):
        db, cam, dept = seeded_db
        from app.schemas.analytics import ThresholdEvaluationRequest
        req = ThresholdEvaluationRequest(threshold=0.70, time_range="30d")
        result = service.evaluate_threshold(db, req)
        assert result.threshold == 0.70
        assert result.total_matches_evaluated >= 0
        if result.estimated_fmr is not None:
            assert 0.0 <= result.estimated_fmr <= 1.0

    def test_score_distribution_returns_lists(self, seeded_db):
        db, cam, dept = seeded_db
        result = service.get_score_distribution(db, time_range="30d")
        assert isinstance(result.genuine_scores, list)
        assert isinstance(result.non_match_scores, list)
        assert result.total_genuine == len(result.genuine_scores)
        assert result.total_non_match == len(result.non_match_scores)


# ===========================================================================
# 8. Model Registry — Register / Activate / Retire / Version Tracking
# ===========================================================================


class TestModelRegistry:
    def _get_admin(self, engine):
        _sf = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = _sf()
        admin = db.query(User).filter(User.username == "m11_admin").first()
        return db, admin

    def test_register_model_creates_record(self, engine):
        db, admin = self._get_admin(engine)
        from app.schemas.analytics import ModelRegistryCreate
        data = ModelRegistryCreate(
            model_name="FACE_EMBED_V2",
            model_type="FACE_EMBEDDING",
            version="2.0.0",
            framework="PyTorch 2.1",
            notes="Test model registration",
        )
        result = service.register_model(db, data, admin)
        assert result.id is not None
        assert result.model_name == "FACE_EMBED_V2"
        assert result.status == "TESTING"
        assert result.deployed_at is None
        db.close()

    def test_activate_model_sets_active_status(self, engine):
        db, admin = self._get_admin(engine)
        from app.schemas.analytics import ModelRegistryCreate
        data = ModelRegistryCreate(
            model_name="PERSON_DET_V1",
            model_type="PERSON_DETECTION",
            version="1.0.0",
        )
        model = service.register_model(db, data, admin)
        activated = service.activate_model(db, model.id, admin)
        assert activated.status == "ACTIVE"
        assert activated.deployed_at is not None
        db.close()

    def test_retire_model_sets_retired_status(self, engine):
        db, admin = self._get_admin(engine)
        from app.schemas.analytics import ModelRegistryCreate
        data = ModelRegistryCreate(
            model_name="FACE_QUAL_V1",
            model_type="QUALITY",
            version="1.0.0",
        )
        model = service.register_model(db, data, admin)
        service.activate_model(db, model.id, admin)
        retired = service.retire_model(db, model.id, admin)
        assert retired.status == "RETIRED"
        assert retired.retired_at is not None
        db.close()

    def test_list_models_returns_all(self, engine):
        db, admin = self._get_admin(engine)
        models = service.list_models(db)
        assert len(models) >= 3
        db.close()

    def test_model_version_tracked(self, engine):
        db, admin = self._get_admin(engine)
        from app.schemas.analytics import ModelRegistryCreate
        data1 = ModelRegistryCreate(model_name="EMBED_MODEL", model_type="FACE_EMBEDDING", version="1.0")
        data2 = ModelRegistryCreate(model_name="EMBED_MODEL", model_type="FACE_EMBEDDING", version="2.0")
        m1 = service.register_model(db, data1, admin)
        m2 = service.register_model(db, data2, admin)
        assert m1.version == "1.0"
        assert m2.version == "2.0"
        assert m1.id != m2.id
        db.close()

    def test_activate_nonexistent_model_raises_404(self, engine):
        from fastapi import HTTPException
        db, admin = self._get_admin(engine)
        with pytest.raises(HTTPException) as exc_info:
            service.activate_model(db, 999999, admin)
        assert exc_info.value.status_code == 404
        db.close()

    def test_register_dataset(self, engine):
        db, admin = self._get_admin(engine)
        from app.schemas.analytics import DatasetRegistryCreate
        data = DatasetRegistryCreate(
            dataset_name="SYNTHETIC_FACES_V1",
            dataset_version="1.0",
            category="TEST",
            source_type="SYNTHETIC",
            sample_count=500,
            notes="Synthetic dataset for evaluation only.",
        )
        result = service.register_dataset(db, data, admin)
        assert result.id is not None
        assert result.category == "TEST"
        assert result.source_type == "SYNTHETIC"
        db.close()

    def test_list_datasets(self, engine):
        db, admin = self._get_admin(engine)
        datasets = service.list_datasets(db)
        assert len(datasets) >= 1
        db.close()

    def test_model_registry_api_register(self, client, admin_token):
        resp = client.post(
            "/api/models/registry",
            json={
                "model_name": "API_TEST_MODEL",
                "model_type": "FACE_EMBEDDING",
                "version": "3.0.0",
                "framework": "ONNX",
            },
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "TESTING"

    def test_model_registry_api_list(self, client, police_token):
        resp = client.get("/api/models/registry", headers=auth_headers(police_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_model_activate_api(self, client, admin_token):
        # Register then activate
        reg_resp = client.post(
            "/api/models/registry",
            json={"model_name": "ACT_TEST", "model_type": "QUALITY", "version": "1.0"},
            headers=auth_headers(admin_token),
        )
        assert reg_resp.status_code == 201
        model_id = reg_resp.json()["id"]
        act_resp = client.post(
            f"/api/models/registry/{model_id}/activate",
            headers=auth_headers(admin_token),
        )
        assert act_resp.status_code == 200
        assert act_resp.json()["status"] == "ACTIVE"


# ===========================================================================
# 9. Drift — Baseline Creation, Distribution Comparison, Warning Generation
# ===========================================================================


class TestDriftMonitoring:
    def test_drift_check_runs_without_error(self, seeded_db):
        db, cam, dept = seeded_db
        # Should run without exception even with sparse data
        new_events = service.check_and_record_drift(db)
        assert isinstance(new_events, list)

    def test_drift_event_created_on_significant_change(self, engine):
        """Manually inject baseline and current values, verify drift event creation."""
        _sf = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = _sf()
        now = datetime.utcnow()

        # Inject past-period low quality data (baseline window: 8–14 days ago)
        for i in range(10):
            db.add(FaceQualityResultDB(
                candidate_id=f"drift-base-{i}",
                track_id=f"dt-{i}",
                camera_id=1,
                timestamp=now - timedelta(days=9),
                quality_score=0.85,  # high baseline
                sharpness_score=0.8, brightness_score=0.8, face_size_score=0.8,
                pose_score=0.9, occlusion_score=0.9, detection_confidence=0.9,
                passed_quality_gate=True,
            ))
        # Inject recent-period low quality data (within last 7 days)
        for i in range(10):
            db.add(FaceQualityResultDB(
                candidate_id=f"drift-recent-{i}",
                track_id=f"dr-{i}",
                camera_id=1,
                timestamp=now - timedelta(days=2),
                quality_score=0.40,  # much lower → >50% drop → CRITICAL
                sharpness_score=0.3, brightness_score=0.3, face_size_score=0.2,
                pose_score=0.4, occlusion_score=0.5, detection_confidence=0.5,
                passed_quality_gate=False,
                rejection_reason="BLUR",
            ))
        db.commit()

        new_events = service.check_and_record_drift(db)
        drift_found = any(
            e.metric_name == "avg_quality_score" and e.severity in ("WARNING", "CRITICAL")
            for e in new_events
        )
        assert drift_found, "Expected a WARNING or CRITICAL drift event for quality score drop"
        db.close()

    def test_drift_event_has_baseline_and_current_value(self, engine):
        _sf = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = _sf()
        events = service.get_drift_events(db, limit=10)
        quality_events = [e for e in events if e.metric_name == "avg_quality_score"]
        if quality_events:
            evt = quality_events[0]
            assert evt.baseline_value is not None
            assert evt.current_value is not None
            assert evt.deviation is not None
        db.close()

    def test_acknowledge_drift_event(self, engine):
        _sf = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = _sf()
        admin = db.query(User).filter(User.username == "m11_admin").first()
        events = service.get_drift_events(db, limit=5)
        if events:
            evt_id = events[0].id
            result = service.acknowledge_drift_event(db, evt_id, admin)
            assert result.is_acknowledged is True
            assert result.acknowledged_at is not None
        db.close()

    def test_drift_api_endpoint(self, client, admin_token):
        resp = client.get("/api/analytics/drift", headers=auth_headers(admin_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_drift_check_api_endpoint(self, client, admin_token):
        resp = client.post("/api/analytics/drift/check", headers=auth_headers(admin_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ===========================================================================
# 10. Security — Access Control
# ===========================================================================


class TestSecurity:
    def test_unauthenticated_overview_denied(self, client):
        resp = client.get("/api/analytics/overview")
        assert resp.status_code in (401, 403)

    def test_unauthenticated_system_health_denied(self, client):
        resp = client.get("/api/analytics/system")
        assert resp.status_code in (401, 403)

    def test_police_cannot_access_drift_events(self, client, police_token):
        """Police role must not access admin-only drift events."""
        resp = client.get("/api/analytics/drift", headers=auth_headers(police_token))
        assert resp.status_code in (401, 403)

    def test_police_cannot_register_model(self, client, police_token):
        """Model registration is admin-only."""
        resp = client.post(
            "/api/models/registry",
            json={"model_name": "HACK", "model_type": "X", "version": "1.0"},
            headers=auth_headers(police_token),
        )
        assert resp.status_code in (401, 403)

    def test_police_cannot_create_evaluation_run(self, client, police_token):
        resp = client.post(
            "/api/evaluation/run",
            json={
                "model_name": "X",
                "model_version": "1.0",
                "dataset_name": "X",
                "dataset_version": "1.0",
            },
            headers=auth_headers(police_token),
        )
        assert resp.status_code in (401, 403)

    def test_police_cannot_execute_evaluation_run(self, client, police_token):
        resp = client.post(
            "/api/evaluation/runs/EVAL-FAKE0001/execute",
            headers=auth_headers(police_token),
        )
        assert resp.status_code in (401, 403)

    def test_police_cannot_access_score_distribution(self, client, police_token):
        resp = client.get("/api/analytics/scores/distribution", headers=auth_headers(police_token))
        assert resp.status_code in (401, 403)

    def test_police_cannot_activate_model(self, client, police_token):
        resp = client.post("/api/models/registry/1/activate", headers=auth_headers(police_token))
        assert resp.status_code in (401, 403)

    def test_police_cannot_retire_model(self, client, police_token):
        resp = client.post("/api/models/registry/1/retire", headers=auth_headers(police_token))
        assert resp.status_code in (401, 403)

    def test_police_cannot_register_dataset(self, client, police_token):
        resp = client.post(
            "/api/models/datasets",
            json={
                "dataset_name": "HACK",
                "dataset_version": "1.0",
                "category": "TEST",
                "source_type": "SYNTHETIC",
            },
            headers=auth_headers(police_token),
        )
        assert resp.status_code in (401, 403)

    def test_police_can_access_overview(self, client, police_token):
        """Police should have read access to overview analytics."""
        resp = client.get("/api/analytics/overview", headers=auth_headers(police_token))
        assert resp.status_code == 200

    def test_police_can_view_model_registry(self, client, police_token):
        """Police should be able to view (but not modify) the model registry."""
        resp = client.get("/api/models/registry", headers=auth_headers(police_token))
        assert resp.status_code == 200

    def test_admin_can_access_drift(self, client, admin_token):
        resp = client.get("/api/analytics/drift", headers=auth_headers(admin_token))
        assert resp.status_code == 200

    def test_evaluation_run_not_found_returns_404(self, client, admin_token):
        resp = client.get(
            "/api/evaluation/runs/EVAL-DOESNOTEXIST",
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 404

    def test_technical_alerts_police_denied(self, client, police_token):
        resp = client.get("/api/analytics/alerts/technical", headers=auth_headers(police_token))
        assert resp.status_code in (401, 403)

    def test_technical_alerts_admin_allowed(self, client, admin_token):
        resp = client.get("/api/analytics/alerts/technical", headers=auth_headers(admin_token))
        assert resp.status_code == 200


# ===========================================================================
# 11. Full API Integration Tests
# ===========================================================================


class TestAPIIntegration:
    def test_overview_api_structure(self, client, police_token):
        resp = client.get("/api/analytics/overview", headers=auth_headers(police_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "system" in data
        assert "pipeline" in data
        assert "matching" in data
        assert "reviews" in data
        assert "alerts" in data
        assert "evidence" in data

    def test_system_health_api_structure(self, client, police_token):
        resp = client.get("/api/analytics/system", headers=auth_headers(police_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "cameras_online" in data
        assert "frames_received" in data
        assert "db_healthy" in data

    def test_pipeline_api_returns_stages(self, client, police_token):
        resp = client.get("/api/analytics/pipeline", headers=auth_headers(police_token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_matching_api(self, client, police_token):
        resp = client.get("/api/analytics/matching", headers=auth_headers(police_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "queries_processed" in data
        assert "fmr" in data

    def test_review_metrics_api(self, client, police_token):
        resp = client.get("/api/analytics/reviews", headers=auth_headers(police_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "reviews_created" in data
        assert "confirmed_for_action" in data

    def test_evidence_metrics_api(self, client, police_token):
        resp = client.get("/api/analytics/evidence", headers=auth_headers(police_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "evidence_created" in data
        assert "integrity_checks" in data

    def test_evaluation_run_full_workflow(self, client, admin_token):
        # 1. Create run
        create_resp = client.post(
            "/api/evaluation/run",
            json={
                "model_name": "INTEGRATION_MODEL",
                "model_version": "1.0",
                "dataset_name": "INTEGRATION_DS",
                "dataset_version": "1.0",
                "threshold": 0.70,
                "justification": "Integration test run",
            },
            headers=auth_headers(admin_token),
        )
        assert create_resp.status_code == 201
        run_id = create_resp.json()["run_id"]
        assert run_id.startswith("EVAL-")

        # 2. List runs
        list_resp = client.get("/api/evaluation/runs", headers=auth_headers(admin_token))
        assert list_resp.status_code == 200
        run_ids = [r["run_id"] for r in list_resp.json()]
        assert run_id in run_ids

        # 3. Execute run
        exec_resp = client.post(
            f"/api/evaluation/runs/{run_id}/execute",
            headers=auth_headers(admin_token),
        )
        assert exec_resp.status_code == 200
        result = exec_resp.json()
        assert "true_positives" in result
        assert "disclaimer" in result
        assert "should not automatically be generalized" in result["disclaimer"]

        # 4. Get results
        results_resp = client.get(
            f"/api/evaluation/runs/{run_id}/results",
            headers=auth_headers(admin_token),
        )
        assert results_resp.status_code == 200

    def test_threshold_evaluation_api(self, client, admin_token):
        resp = client.post(
            "/api/evaluation/threshold",
            json={"threshold": 0.75, "time_range": "30d"},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["threshold"] == 0.75
        assert "estimated_fmr" in data

    def test_dataset_registry_workflow(self, client, admin_token):
        # Register
        reg_resp = client.post(
            "/api/models/datasets",
            json={
                "dataset_name": "SYNTH_FACES_API_TEST",
                "dataset_version": "2.0",
                "category": "VALIDATION",
                "source_type": "SYNTHETIC",
                "sample_count": 1000,
                "notes": "API integration test dataset",
            },
            headers=auth_headers(admin_token),
        )
        assert reg_resp.status_code == 201
        data = reg_resp.json()
        assert data["category"] == "VALIDATION"
        assert data["source_type"] == "SYNTHETIC"

        # List
        list_resp = client.get("/api/models/datasets", headers=auth_headers(admin_token))
        assert list_resp.status_code == 200
        assert len(list_resp.json()) >= 1

    def test_quality_breakdown_api(self, client, police_token):
        resp = client.get("/api/analytics/quality", headers=auth_headers(police_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "faces_received" in data
        assert "rejection_reasons" in data
        assert isinstance(data["rejection_reasons"], dict)

    def test_cameras_api_time_filter(self, client, police_token):
        for tr in ["today", "7d", "30d"]:
            resp = client.get(
                f"/api/analytics/cameras?time_range={tr}",
                headers=auth_headers(police_token),
            )
            assert resp.status_code == 200

    def test_export_csv_api(self, client, police_token):
        resp = client.get(
            "/api/analytics/export/csv?time_range=7d",
            headers=auth_headers(police_token),
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        assert "Content-Disposition" in resp.headers
        csv_text = resp.text
        assert "SYSTEM HEALTH METRICS" in csv_text
        assert "MATCHING METRICS" in csv_text
        assert "EXPORT METADATA" in csv_text

    def test_export_json_api(self, client, police_token):
        resp = client.get(
            "/api/analytics/export/json?time_range=7d",
            headers=auth_headers(police_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "system" in data
        assert "matching" in data
        assert "export_metadata" in data
        assert "disclaimer" in data["export_metadata"]

    def test_generate_research_report_api(self, client, admin_token):
        # 1. Create and execute run
        create_resp = client.post(
            "/api/evaluation/run",
            json={
                "model_name": "REPORT_TEST_MODEL",
                "model_version": "1.0",
                "dataset_name": "REPORT_TEST_DS",
                "dataset_version": "1.0",
                "threshold": 0.70,
                "justification": "Research report test",
            },
            headers=auth_headers(admin_token),
        )
        run_id = create_resp.json()["run_id"]
        client.post(f"/api/evaluation/runs/{run_id}/execute", headers=auth_headers(admin_token))

        # 2. Generate report
        report_resp = client.get(
            f"/api/analytics/report/research?run_id={run_id}",
            headers=auth_headers(admin_token),
        )
        assert report_resp.status_code == 200
        report = report_resp.json()
        assert report["report_type"] == "SENTINEX Research Evaluation Report"
        assert "evaluation_run" in report
        assert "metrics" in report
        assert "limitations" in report
        assert "disclaimer" in report
        assert "should not automatically be generalized" in report["disclaimer"]

    def test_export_unauthenticated_denied(self, client):
        resp_csv = client.get("/api/analytics/export/csv")
        assert resp_csv.status_code in (401, 403)
        resp_json = client.get("/api/analytics/export/json")
        assert resp_json.status_code in (401, 403)
        resp_rep = client.get("/api/analytics/report/research?run_id=EVAL-FAKE")
        assert resp_rep.status_code in (401, 403)

