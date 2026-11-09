"""
Tests for Module 5 – AI Processing API Router
=============================================
Tests all HTTP endpoints defined in app.api.ai_processing:
- GET  /api/ai-processing/status
- GET  /api/ai-processing/metrics
- GET  /api/ai-processing/metrics/{camera_id}
- POST /api/ai-processing/cameras/{camera_id}/start
- POST /api/ai-processing/cameras/{camera_id}/stop
- POST /api/ai-processing/stop-all
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.main import app
from app.api.deps import get_current_user, require_admin, require_police
from app.models.user import User, UserRole
from app.ai_engine.pipeline.processing_pipeline import video_pipeline
from app.ai_engine.metrics.performance_monitor import performance_monitor
from app.utils.frame_queue import BoundedFrameQueue


@pytest.fixture
def mock_admin_user():
    return User(
        id=1,
        username="admin_test",
        email="admin@sentinex.test",
        password_hash="fakehash",
        role=UserRole.ADMIN.value,
        is_active=True,
    )


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
def api_client(mock_admin_user):
    app.dependency_overrides[get_current_user] = lambda: mock_admin_user
    app.dependency_overrides[require_admin] = lambda: mock_admin_user
    app.dependency_overrides[require_police] = lambda: mock_admin_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


class TestAIProcessingEndpoints:

    def test_status_unauthenticated(self):
        with TestClient(app) as client:
            resp = client.get("/api/ai-processing/status")
            assert resp.status_code == 401

    def test_status_authenticated(self, api_client):
        resp = api_client.get("/api/ai-processing/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "active_cameras" in data
        assert "camera_ids" in data
        assert isinstance(data["camera_ids"], list)

    def test_status_root_mount(self, api_client):
        resp = api_client.get("/ai-processing/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_get_all_metrics_empty(self, api_client):
        performance_monitor.reset_camera(9999)
        resp = api_client.get("/api/ai-processing/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_camera_metrics(self, api_client):
        performance_monitor.record_frame_received(camera_id=42)
        performance_monitor.record_frame_processed(camera_id=42, latency_s=0.025)

        resp = api_client.get("/api/ai-processing/metrics/42")
        assert resp.status_code == 200
        data = resp.json()
        assert data["camera_id"] == 42
        assert data["frames_received"] >= 1
        assert data["frames_processed"] >= 1
        assert data["average_latency_ms"] >= 0.0

    def test_start_camera_pipeline_stream_not_found(self, api_client):
        resp = api_client.post("/api/ai-processing/cameras/999/start")
        assert resp.status_code == 404
        assert "No active stream found" in resp.json()["detail"]

    def test_start_camera_pipeline_success(self, api_client):
        queue = BoundedFrameQueue(maxsize=8)
        mock_camera = MagicMock(
            id=10,
            camera_code="CAM-10",
            location_name="North Gate",
            department_id=1,
        )

        with patch("app.services.stream_manager.stream_manager.get_frame_queue", return_value=queue), \
             patch("app.database.session.SessionLocal") as mock_session_local:
            mock_db = MagicMock()
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = mock_camera

            resp = api_client.post("/api/ai-processing/cameras/10/start")
            assert resp.status_code == 202
            data = resp.json()
            assert data["camera_id"] == 10
            assert "started" in data["message"]
            assert video_pipeline.is_running(10)

            # Cleanup
            stop_resp = api_client.post("/api/ai-processing/cameras/10/stop")
            assert stop_resp.status_code == 202

    def test_stop_camera_pipeline(self, api_client):
        resp = api_client.post("/api/ai-processing/cameras/10/stop")
        assert resp.status_code == 202
        assert "stopped" in resp.json()["message"]

    def test_stop_all_pipelines(self, api_client):
        resp = api_client.post("/api/ai-processing/stop-all")
        assert resp.status_code == 202
        assert "stopped" in resp.json()["message"]
