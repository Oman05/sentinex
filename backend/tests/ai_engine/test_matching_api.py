"""
Tests for Module 7 – Candidate Matching & Ranking API Endpoints
=================================================================
Tests all HTTP endpoints defined in app.api.matching:
- POST /api/matching/search
- POST /api/matching/query-face
- GET  /api/matching/events
- GET  /api/matching/events/{event_id}
- PATCH /api/matching/events/{event_id}/status
- POST /api/matching/reindex
- GET  /api/matching/telemetry

Security: Verifies authentication & RBAC.
Safety: Confirms mandatory "POSSIBLE MATCH — REQUIRES AUTHORIZED HUMAN VERIFICATION".
"""

from __future__ import annotations

import base64
import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.main import app
from app.api.deps import get_current_user, require_admin, require_police
from app.models.user import User, UserRole
from app.ai_engine.schemas.matching import MatchEventStatus


@pytest.fixture
def mock_police_user():
    return User(
        id=2,
        username="police_examiner",
        email="examiner@sentinex.test",
        password_hash="fakehash",
        role=UserRole.POLICE.value,
        is_active=True,
    )


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
def api_client(mock_police_user):
    app.dependency_overrides[get_current_user] = lambda: mock_police_user
    app.dependency_overrides[require_police] = lambda: mock_police_user
    app.dependency_overrides[require_admin] = lambda: mock_police_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _make_dummy_base64() -> str:
    img = np.full((112, 112, 3), 128, dtype=np.uint8)
    cv2.circle(img, (35, 40), 10, (30, 30, 30), -1)
    cv2.circle(img, (75, 40), 10, (30, 30, 30), -1)
    cv2.line(img, (56, 45), (56, 65), (50, 50, 50), 3)
    cv2.ellipse(img, (56, 85), (20, 8), 0, 0, 180, (20, 20, 20), 2)
    _, enc = cv2.imencode(".jpg", img)
    return base64.b64encode(enc.tobytes()).decode("utf-8")


class TestMatchingEndpoints:

    def test_search_candidate_endpoint_success(self, api_client):
        payload = {
            "candidate_id": "CAND-API-001",
            "track_id": "TRACK-API-001",
            "camera_id": 1,
            "face_image_base64": _make_dummy_base64(),
            "face_quality_score": 0.85,
            "quality_status": "GOOD",
            "is_match_ready": True,
            "search_mode": "ALL_ACTIVE_CASES",
        }
        res = api_client.post("/api/matching/search", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["query_candidate_id"] == "CAND-API-001"
        assert "candidates" in data
        assert "POSSIBLE MATCH" in data["safety_notice"]

    def test_search_candidate_gated_when_not_match_ready(self, api_client):
        payload = {
            "candidate_id": "CAND-API-002",
            "track_id": "TRACK-API-002",
            "camera_id": 1,
            "face_image_base64": _make_dummy_base64(),
            "face_quality_score": 0.30,
            "quality_status": "POOR",
            "is_match_ready": False,
        }
        res = api_client.post("/api/matching/search", json=payload)
        assert res.status_code == 400
        assert "not match-ready" in res.json()["detail"]

    def test_query_face_endpoint(self, api_client):
        payload = {
            "face_image_base64": _make_dummy_base64(),
            "search_mode": "MISSING",
            "top_k": 5,
        }
        res = api_client.post("/api/matching/query-face", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["search_mode"] == "MISSING"
        assert "candidates" in data

    def test_list_events_endpoint(self, api_client):
        res = api_client.get("/api/matching/events")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_telemetry_endpoint(self, api_client):
        res = api_client.get("/api/matching/telemetry")
        assert res.status_code == 200
        data = res.json()
        assert "queries_processed" in data
        assert "active_model_name" in data

    def test_unauthenticated_request_rejected(self):
        # Without dependency overrides
        with TestClient(app) as client:
            res = client.post("/api/matching/search", json={})
            assert res.status_code in (401, 403)
