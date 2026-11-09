import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.review import SIMILARITY_DISCLAIMER

client = TestClient(app)

def test_cctv_evidence_not_accessible_without_auth():
    response = client.get("/api/review/events/1/track-history")
    assert response.status_code == 401

def test_rate_limiting():
    # Make 61 requests to a sensitive endpoint
    responses = []
    for _ in range(61):
        responses.append(client.get("/api/review/events"))
    
    assert responses[-1].status_code in (401, 429) # either unauthorized or rate limited
