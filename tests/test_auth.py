from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.user import User, UserRole
from app.services.auth_service import create_access_token, hash_password, verify_password


@pytest.fixture
def client():
    db_path = Path("sentinex_test.db")
    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            pass

    settings.DATABASE_URL = "sqlite:///./sentinex_test.db"
    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield {"client": test_client, "engine": engine}
    app.dependency_overrides.clear()
    try:
        if db_path.exists():
            db_path.unlink()
    except PermissionError:
        pass


def test_register_user(client):
    test_client = client["client"]
    response = test_client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "StrongPass123"},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["username"] == "alice"
    assert payload["email"] == "alice@example.com"
    assert payload["role"] == "POLICE"
    assert "password_hash" not in payload
    assert payload["is_active"] is True


def test_duplicate_username_and_email(client):
    test_client = client["client"]
    test_client.post("/api/auth/register", json={"username": "bob", "email": "bob@example.com", "password": "StrongPass123"})

    dup_username = test_client.post(
        "/api/auth/register",
        json={"username": "bob", "email": "other@example.com", "password": "StrongPass123"},
    )
    assert dup_username.status_code == 400

    dup_email = test_client.post(
        "/api/auth/register",
        json={"username": "robert", "email": "bob@example.com", "password": "StrongPass123"},
    )
    assert dup_email.status_code == 400


def test_password_hashing_and_verification():
    raw_password = "StrongPass123"
    hashed = hash_password(raw_password)
    assert hashed != raw_password
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPass123", hashed) is False


def test_valid_and_invalid_login(client):
    test_client = client["client"]
    test_client.post("/api/auth/register", json={"username": "charlie", "email": "charlie@example.com", "password": "StrongPass123"})

    valid = test_client.post("/api/auth/login", json={"username": "charlie", "password": "StrongPass123"})
    assert valid.status_code == 200, valid.text
    token = valid.json()["access_token"]
    assert token

    invalid = test_client.post("/api/auth/login", json={"username": "charlie", "password": "WrongPass123"})
    assert invalid.status_code == 401


def test_jwt_authentication_and_me(client):
    test_client = client["client"]
    test_client.post("/api/auth/register", json={"username": "dana", "email": "dana@example.com", "password": "StrongPass123"})
    login = test_client.post("/api/auth/login", json={"username": "dana", "password": "StrongPass123"})
    token = login.json()["access_token"]

    me = test_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "dana"

    no_token = test_client.get("/api/auth/me")
    assert no_token.status_code == 401


def test_admin_and_police_permissions(client):
    test_client = client["client"]
    engine = client["engine"]
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        admin = User(
            username="admin_user",
            email="admin@example.com",
            password_hash=hash_password("StrongPass123"),
            role=UserRole.ADMIN.value,
            is_active=True,
        )
        police = User(
            username="police_user",
            email="police@example.com",
            password_hash=hash_password("StrongPass123"),
            role=UserRole.POLICE.value,
            is_active=True,
        )

        db.add_all([admin, police])
        db.commit()
        db.refresh(admin)
        db.refresh(police)

        admin_token = create_access_token({"sub": admin.username, "user_id": admin.id, "role": admin.role})
        police_token = create_access_token({"sub": police.username, "user_id": police.id, "role": police.role})

        admin_ok = test_client.get("/api/admin/test", headers={"Authorization": f"Bearer {admin_token}"})
        assert admin_ok.status_code == 200

        police_ok = test_client.get("/api/police/test", headers={"Authorization": f"Bearer {police_token}"})
        assert police_ok.status_code == 200

        police_forbidden = test_client.get("/api/admin/test", headers={"Authorization": f"Bearer {police_token}"})
        assert police_forbidden.status_code == 403
    finally:
        db.close()


def test_unauthorized_access_and_inactive_account(client):
    test_client = client["client"]
    engine = client["engine"]
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    test_client.post("/api/auth/register", json={"username": "erin", "email": "erin@example.com", "password": "StrongPass123"})
    login = test_client.post("/api/auth/login", json={"username": "erin", "password": "StrongPass123"})
    token = login.json()["access_token"]

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(username="erin").first()
        user.is_active = False
        db.commit()
    finally:
        db.close()

    inactive_login = test_client.post("/api/auth/login", json={"username": "erin", "password": "StrongPass123"})
    assert inactive_login.status_code == 401

    inactive_access = test_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert inactive_access.status_code == 401

    bad_token = test_client.get("/api/auth/me", headers={"Authorization": "Bearer badtoken"})
    assert bad_token.status_code == 401


def test_input_validation(client):
    test_client = client["client"]
    too_short = test_client.post("/api/auth/register", json={"username": "ab", "email": "bad@example.com", "password": "short"})
    assert too_short.status_code == 422

    weak_password = test_client.post("/api/auth/register", json={"username": "frank", "email": "frank@example.com", "password": "password"})
    assert weak_password.status_code == 422

    invalid_email = test_client.post("/api/auth/register", json={"username": "gina", "email": "not-an-email", "password": "StrongPass123"})
    assert invalid_email.status_code == 422
