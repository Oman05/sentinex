import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.department import Department
from app.models.user import User, UserRole
from app.services.auth_service import create_access_token, hash_password


@pytest.fixture
def case_client(tmp_path):
    db_path = tmp_path / "sentinex_test.db"
    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            pass

    settings.DATABASE_URL = f"sqlite:///{db_path}"
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
    engine.dispose()
    try:
        if db_path.exists():
            db_path.unlink()
    except PermissionError:
        pass


def test_case_creation_and_department_access(case_client):
    client = case_client["client"]
    engine = case_client["engine"]
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    try:
        dept_one = Department(department_name="North District", department_type="POLICE", location="North City")
        dept_two = Department(department_name="South District", department_type="POLICE", location="South City")
        admin = User(
            username="admin_case_user",
            email="admincase@example.com",
            password_hash=hash_password("StrongPass123"),
            role=UserRole.ADMIN.value,
            is_active=True,
            department_id=None,
        )
        police_one = User(
            username="police_case_user",
            email="policecase@example.com",
            password_hash=hash_password("StrongPass123"),
            role=UserRole.POLICE.value,
            is_active=True,
            department_id=1,
        )
        police_two = User(
            username="police_case_user_2",
            email="policecase2@example.com",
            password_hash=hash_password("StrongPass123"),
            role=UserRole.POLICE.value,
            is_active=True,
            department_id=2,
        )
        db.add_all([dept_one, dept_two, admin, police_one, police_two])
        db.commit()
        db.refresh(dept_one)
        db.refresh(dept_two)
        db.refresh(police_one)
        db.refresh(police_two)
        db.refresh(admin)
    finally:
        db.close()

    admin_token = create_access_token({"sub": "admin_case_user", "user_id": admin.id, "role": admin.role})
    police_one_token = create_access_token({"sub": "police_case_user", "user_id": police_one.id, "role": police_one.role})
    police_two_token = create_access_token({"sub": "police_case_user_2", "user_id": police_two.id, "role": police_two.role})

    response = client.post(
        "/api/cases",
        json={
            "category": "MISSING",
            "title": "Missing Child Case",
            "person_identifier": "ID-1001",
            "description": "A missing child was reported in the North District area.",
            "department_id": dept_one.id,
            "priority": "HIGH",
            "last_known_location": "North City Station",
        },
        headers={"Authorization": f"Bearer {police_one_token}"},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["case_number"].startswith("MP-")
    assert payload["department_id"] == dept_one.id
    assert payload["status"] == "DRAFT"

    list_response = client.get("/api/cases", headers={"Authorization": f"Bearer {police_one_token}"})
    assert list_response.status_code == 200
    assert list_response.json()["total"] >= 1

    forbidden = client.get(f"/api/cases/{payload['id']}", headers={"Authorization": f"Bearer {police_two_token}"})
    assert forbidden.status_code == 403

    admin_access = client.get(f"/api/cases/{payload['id']}", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_access.status_code == 200


def test_case_status_validation_and_soft_delete(case_client):
    client = case_client["client"]
    engine = case_client["engine"]
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    try:
        dept = Department(department_name="Central District", department_type="POLICE", location="Central City")
        police = User(
            username="central_police",
            email="central@example.com",
            password_hash=hash_password("StrongPass123"),
            role=UserRole.POLICE.value,
            is_active=True,
            department_id=1,
        )
        db.add_all([dept, police])
        db.commit()
        db.refresh(dept)
        db.refresh(police)
    finally:
        db.close()

    token = create_access_token({"sub": "central_police", "user_id": police.id, "role": police.role})
    create_response = client.post(
        "/api/cases",
        json={
            "category": "WANTED",
            "title": "Wanted Suspect Case",
            "person_identifier": "W-9001",
            "description": "Wanted suspect with current alias and active outstanding warrant.",
            "department_id": dept.id,
            "priority": "CRITICAL",
            "last_known_location": "Central City",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    case_id = create_response.json()["id"]
    assert create_response.status_code == 201

    invalid_status = client.patch(
        f"/api/cases/{case_id}/status",
        json={"status": "CLOSED"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert invalid_status.status_code == 400

    valid_status = client.patch(
        f"/api/cases/{case_id}/status",
        json={"status": "ACTIVE"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert valid_status.status_code == 200
    assert valid_status.json()["status"] == "ACTIVE"

    delete_response = client.delete(f"/api/cases/{case_id}", headers={"Authorization": f"Bearer {token}"})
    assert delete_response.status_code == 200
    assert delete_response.json()["case_id"] == case_id

    list_response = client.get("/api/cases", headers={"Authorization": f"Bearer {token}"})
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 0
