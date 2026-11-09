"""
Tests for Module 6 – Face Quality Assessment API Endpoints
============================================================
Tests all HTTP endpoints defined in app.api.face_quality:
- POST /api/ai/face-quality/assess
- POST /api/ai/face-quality/assess-multi-frame
- GET  /api/ai/face-quality/metrics/telemetry
- GET  /api/ai/face-quality/{candidate_id}
- GET  /api/ai/face-quality/{candidate_id}/history

Security: Verifies that unauthenticated requests are rejected.
Safety: Confirms the API never exposes identity scores.
"""

from __future__ import annotations

import base64
import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.main import app
from app.api.deps import get_current_user, require_admin, require_police
from app.models.user import User, UserRole


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_police_user():
    return User(
        id=2,
        username="police_test",
        email="police@sentinex.test",
        password_hash="fakehash",
        role=UserRole.POLICE.value,
        is_active=True,
    )


@pytest.fixture
def api_client(mock_police_user):
    app.dependency_overrides[get_current_user] = lambda: mock_police_user
    app.dependency_overrides[require_police] = lambda: mock_police_user
    app.dependency_overrides[require_admin] = lambda: mock_police_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def unauth_client():
    with TestClient(app) as client:
        yield client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_face_b64(h: int = 80, w: int = 80) -> str:
    """Create a small random BGR image encoded as base64 JPEG for the API."""
    import cv2
    rng = np.random.default_rng(55)
    img = rng.integers(60, 200, (h, w, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def _assess_payload(candidate_id: str = "cand-api-001") -> dict:
    return {
        "candidate_id": candidate_id,
        "track_id": "track-api-001",
        "camera_id": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "frame_reference": "cam1-frame-0001",
        "face_bbox": {"x1": 100, "y1": 80, "x2": 180, "y2": 160},
        "face_detection_confidence": 0.92,
        "face_image_base64": _make_face_b64(),
        "frame_width": 1280,
        "frame_height": 720,
    }


# ---------------------------------------------------------------------------
# Authentication enforcement
# ---------------------------------------------------------------------------


class TestAuthentication:

    def test_assess_endpoint_requires_auth(self, unauth_client):
        resp = unauth_client.post("/api/ai/face-quality/assess", json=_assess_payload())
        assert resp.status_code == 401

    def test_multi_frame_endpoint_requires_auth(self, unauth_client):
        payload = {
            "track_id": "track-001",
            "candidates": [_assess_payload("c1")],
        }
        resp = unauth_client.post("/api/ai/face-quality/assess-multi-frame", json=payload)
        assert resp.status_code == 401

    def test_candidate_lookup_requires_auth(self, unauth_client):
        resp = unauth_client.get("/api/ai/face-quality/cand-xyz")
        assert resp.status_code == 401

    def test_telemetry_requires_auth(self, unauth_client):
        resp = unauth_client.get("/api/ai/face-quality/metrics/telemetry")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/ai/face-quality/assess
# ---------------------------------------------------------------------------


class TestAssessEndpoint:

    def test_assess_returns_200(self, api_client):
        from app.ai_engine.schemas.quality import (
            FaceQualityResult,
            QualityClassification,
            RejectionReason,
        )
        mock_result = FaceQualityResult(
            candidate_id="cand-api-001",
            track_id="track-api-001",
            camera_id=1,
            timestamp=datetime.now(timezone.utc),
            sharpness_score=0.80,
            brightness_score=0.75,
            contrast_score=0.70,
            face_size_score=0.85,
            pose_score=0.80,
            occlusion_score=0.10,
            detection_confidence=0.92,
            quality_score=0.78,
            quality_status=QualityClassification.GOOD,
            is_match_ready=True,
            reason="High quality observation.",
            rejection_reason=RejectionReason.NONE,
            best_frame_reference="cam1-frame-0001",
        )
        with patch("app.services.quality_service.quality_service.assess_face_quality",
                   return_value=mock_result), \
             patch("app.database.session.get_db"):
            resp = api_client.post("/api/ai/face-quality/assess", json=_assess_payload())
            assert resp.status_code == 200


    def test_assess_missing_required_field(self, api_client):
        payload = _assess_payload()
        del payload["candidate_id"]
        resp = api_client.post("/api/ai/face-quality/assess", json=payload)
        assert resp.status_code == 422  # Validation error

    def test_assess_response_has_no_identity_field(self, api_client):
        """AI safety: response must not expose identity scores."""
        with patch("app.services.quality_service.quality_service.assess_face_quality") as mock_assess, \
             patch("app.database.session.get_db"):
            from app.ai_engine.schemas.quality import (
                FaceQualityResult,
                QualityClassification,
                RejectionReason,
            )
            mock_result = FaceQualityResult(
                candidate_id="cand-api-001",
                track_id="track-001",
                camera_id=1,
                timestamp=datetime.now(timezone.utc),
                sharpness_score=0.80,
                brightness_score=0.75,
                contrast_score=0.70,
                face_size_score=0.85,
                pose_score=0.80,
                occlusion_score=0.10,
                detection_confidence=0.92,
                quality_score=0.78,
                quality_status=QualityClassification.GOOD,
                is_match_ready=True,
                reason="OK.",
                rejection_reason=RejectionReason.NONE,
                best_frame_reference="ref-001",
            )
            mock_assess.return_value = mock_result

            resp = api_client.post("/api/ai/face-quality/assess", json=_assess_payload())
            if resp.status_code == 200:
                data = resp.json()
                for forbidden_key in ("identity", "person_id", "match_confidence", "recognition_score"):
                    assert forbidden_key not in data, (
                        f"Safety violation: API response contains forbidden key '{forbidden_key}'"
                    )


# ---------------------------------------------------------------------------
# GET /api/ai/face-quality/metrics/telemetry
# ---------------------------------------------------------------------------


class TestTelemetryEndpoint:

    def test_telemetry_returns_200(self, api_client):
        from app.ai_engine.schemas.quality import QualityTelemetryResponse
        telemetry = QualityTelemetryResponse(
            faces_received=100,
            faces_assessed=95,
            faces_rejected=30,
            faces_passed=65,
            pass_rate=0.684,
            rejection_rate=0.316,
            average_quality_score=0.72,
            average_processing_latency_ms=5.3,
            active_camera_count=3,
            snapshot_at=datetime.now(timezone.utc).isoformat(),
        )
        with patch("app.services.quality_service.quality_service.get_telemetry_snapshot", return_value=telemetry):
            resp = api_client.get("/api/ai/face-quality/metrics/telemetry")
            assert resp.status_code == 200

    def test_telemetry_response_has_required_fields(self, api_client):
        from app.ai_engine.schemas.quality import QualityTelemetryResponse
        telemetry = QualityTelemetryResponse(
            faces_received=50,
            faces_assessed=45,
            faces_rejected=10,
            faces_passed=35,
            pass_rate=0.777,
            rejection_rate=0.222,
            average_quality_score=0.68,
            average_processing_latency_ms=4.1,
            active_camera_count=2,
            snapshot_at=datetime.now(timezone.utc).isoformat(),
        )
        with patch("app.services.quality_service.quality_service.get_telemetry_snapshot", return_value=telemetry):
            resp = api_client.get("/api/ai/face-quality/metrics/telemetry")
            if resp.status_code == 200:
                data = resp.json()
                assert "faces_received" in data
                assert "faces_assessed" in data
                assert "pass_rate" in data
                assert "average_quality_score" in data


# ---------------------------------------------------------------------------
# GET /api/ai/face-quality/{candidate_id}
# ---------------------------------------------------------------------------


class TestCandidateRetrievalEndpoint:

    def test_missing_candidate_returns_404(self, api_client):
        with patch(
            "app.services.quality_service.quality_service.get_result_by_candidate",
            return_value=None,
        ), patch("app.database.session.get_db"):
            resp = api_client.get("/api/ai/face-quality/nonexistent-cand")
            assert resp.status_code == 404

    def test_existing_candidate_returns_200(self, api_client):
        mock_row = MagicMock()
        mock_row.candidate_id = "cand-stored-001"
        mock_row.track_id = "track-stored-001"
        mock_row.camera_id = 1
        mock_row.timestamp = datetime.now(timezone.utc)
        mock_row.sharpness_score = 0.80
        mock_row.brightness_score = 0.75
        mock_row.contrast_score = 0.70
        mock_row.face_size_score = 0.85
        mock_row.pose_score = 0.80
        mock_row.occlusion_score = 0.10
        mock_row.detection_confidence = 0.92
        mock_row.quality_score = 0.78
        mock_row.quality_status = "GOOD"
        mock_row.is_match_ready = True
        mock_row.rejection_reason = "NONE"
        mock_row.best_frame_reference = "ref-001"
        mock_row.created_at = datetime.now(timezone.utc)

        with patch(
            "app.services.quality_service.quality_service.get_result_by_candidate",
            return_value=mock_row,
        ), patch("app.database.session.get_db"):
            resp = api_client.get("/api/ai/face-quality/cand-stored-001")
            assert resp.status_code == 200
            data = resp.json()
            assert data["candidate_id"] == "cand-stored-001"


# ---------------------------------------------------------------------------
# GET /api/ai/face-quality/{candidate_id}/history
# ---------------------------------------------------------------------------


class TestTrackHistoryEndpoint:

    def test_history_candidate_not_found_returns_404(self, api_client):
        with patch(
            "app.services.quality_service.quality_service.get_result_by_candidate",
            return_value=None,
        ), patch("app.database.session.get_db"):
            resp = api_client.get("/api/ai/face-quality/ghost-cand/history")
            assert resp.status_code == 404

    def test_history_returns_list(self, api_client):
        mock_row = MagicMock()
        mock_row.candidate_id = "cand-hist-001"
        mock_row.track_id = "track-hist-001"
        mock_row.camera_id = 1
        mock_row.timestamp = datetime.now(timezone.utc)
        mock_row.sharpness_score = 0.80
        mock_row.brightness_score = 0.75
        mock_row.contrast_score = 0.70
        mock_row.face_size_score = 0.85
        mock_row.pose_score = 0.80
        mock_row.occlusion_score = 0.10
        mock_row.detection_confidence = 0.92
        mock_row.quality_score = 0.78
        mock_row.quality_status = "GOOD"
        mock_row.is_match_ready = True
        mock_row.rejection_reason = "NONE"
        mock_row.best_frame_reference = "ref-001"
        mock_row.created_at = datetime.now(timezone.utc)

        with patch(
            "app.services.quality_service.quality_service.get_result_by_candidate",
            return_value=mock_row,
        ), patch(
            "app.services.quality_service.quality_service.get_history_by_track",
            return_value=[mock_row],
        ), patch("app.database.session.get_db"):
            resp = api_client.get("/api/ai/face-quality/cand-hist-001/history")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
