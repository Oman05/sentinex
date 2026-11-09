import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_unauthenticated_access():
    response = client.get("/api/review/events")
    assert response.status_code == 401

def test_invalid_token():
    response = client.get("/api/review/events", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401
