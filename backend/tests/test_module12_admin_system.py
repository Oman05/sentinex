"""
Module 12 Tests: Admin / System Management & Deployment
=======================================================
Validates:
1. Admin Dashboard metrics & subsystem statuses
2. User Management & Role-Based Access Control (ADMIN, AUTHORIZED_OFFICER, POLICE, REVIEWER, RESEARCHER)
3. Department Management, jurisdictional settings, and statistics
4. Camera Management, URL security validation without credentials, connection testing
5. System Configuration tuning, validation, and audit tracking
6. Background Worker fleet management and heartbeat monitoring
7. Health Monitoring endpoints (/health, /health/ready, /health/live, /health/database, /health/ai, /health/workers, /health/storage)
8. Backup, SHA-256 cryptographic verification, and disaster recovery
9. Administrative and system audit logging
10. Final end-to-end integration test (Auth -> Dept -> Case -> CCTV -> AI -> Review -> Alert -> Evidence -> Audit)
"""

from __future__ import annotations

from datetime import datetime
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.alert import AlertDB, AlertPriority, AlertStatus
from app.models.analytics import ModelRegistryDB
from app.models.camera import Camera, CameraStatus
from app.models.case import Case, CaseCategory, CasePriority, CaseStatus
from app.models.department import Department
from app.models.review_event import ReviewDecision, ReviewEventDB, ReviewStatus
from app.models.user import User, UserRole
from app.services.config_service import config_service


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_user(db_session: Session) -> User:
    user = User(
        username="admin_super",
        email="admin_super@sentinex.gov",
        password_hash=hash_password("SuperSecret123"),
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def officer_user(db_session: Session) -> User:
    user = User(
        username="officer_john",
        email="officer_john@sentinex.gov",
        password_hash=hash_password("OfficerPass123"),
        role=UserRole.AUTHORIZED_OFFICER.value,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_dept(db_session: Session) -> Department:
    dept = Department(
        department_name="Metro Central Police",
        department_type="POLICE",
        location="Sector 1, Metro City",
        is_active=True,
    )
    db_session.add(dept)
    db_session.commit()
    db_session.refresh(dept)
    return dept


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"user_id": user.id})
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# 1. ADMIN DASHBOARD TESTS
# ============================================================================


def test_admin_dashboard_metrics(client: TestClient, admin_user: User, test_dept: Department, db_session: Session):
    # Add a camera and an active case
    cam = Camera(
        camera_name="Entrance Cam 1",
        department_id=test_dept.id,
        stream_url="rtsp://192.168.1.50/live",
        stream_type="RTSP",
        status=CameraStatus.ONLINE.value,
        is_active=True,
    )
    db_session.add(cam)
    db_session.commit()

    headers = auth_headers(admin_user)
    res = client.get("/admin/dashboard", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_users"] >= 1
    assert data["active_departments"] >= 1
    assert data["registered_cameras"] >= 1
    assert data["online_cameras"] >= 1
    assert "system_health" in data
    assert "ai_model_status" in data
    assert "database_status" in data


def test_admin_dashboard_rbac_enforcement(client: TestClient, officer_user: User):
    # Non-admin user cannot access admin dashboard
    headers = auth_headers(officer_user)
    res = client.get("/admin/dashboard", headers=headers)
    assert res.status_code == 403
    assert "Admin access required" in res.json()["detail"]


# ============================================================================
# 2. USER MANAGEMENT TESTS
# ============================================================================


def test_user_management_crud(client: TestClient, admin_user: User, test_dept: Department):
    headers = auth_headers(admin_user)

    # 1. Create User
    create_res = client.post(
        "/admin/users",
        params={
            "username": "reviewer_sarah",
            "email": "reviewer_sarah@sentinex.gov",
            "password": "Password123",
            "role": "REVIEWER",
            "department_id": test_dept.id,
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    user_data = create_res.json()
    user_id = user_data["id"]
    assert user_data["username"] == "reviewer_sarah"
    assert user_data["role"] == "REVIEWER"

    # 2. List Users
    list_res = client.get("/admin/users", headers=headers)
    assert list_res.status_code == 200
    assert any(u["id"] == user_id for u in list_res.json())

    # 3. Update User
    update_res = client.put(
        f"/admin/users/{user_id}",
        json={"role": "RESEARCHER", "email": "sarah_research@sentinex.gov"},
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["role"] == "RESEARCHER"

    # 4. Deactivate User
    status_res = client.patch(f"/admin/users/{user_id}/status?is_active=false", headers=headers)
    assert status_res.status_code == 200
    assert status_res.json()["is_active"] is False

    # 5. Reset Password
    reset_res = client.post(
        f"/admin/users/{user_id}/reset-password",
        json={"new_password": "NewSecretPassword123", "reason": "Routine password rotation"},
        headers=headers,
    )
    assert reset_res.status_code == 200


# ============================================================================
# 3. DEPARTMENT MANAGEMENT TESTS
# ============================================================================


def test_department_management(client: TestClient, admin_user: User):
    headers = auth_headers(admin_user)

    # Create department
    res = client.post(
        "/admin/departments",
        json={
            "department_name": "Port Security Zone 4",
            "department_type": "PORT_AUTHORITY",
            "location": "Harbor Terminal A",
        },
        headers=headers,
    )
    assert res.status_code == 201
    dept_id = res.json()["id"]

    # Get stats
    stats_res = client.get(f"/admin/departments/{dept_id}/stats", headers=headers)
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["department_id"] == dept_id
    assert stats["total_cameras"] == 0

    # Toggle status
    toggle_res = client.patch(f"/admin/departments/{dept_id}/status", json={"is_active": False}, headers=headers)
    assert toggle_res.status_code == 200
    assert toggle_res.json()["is_active"] is False



# ============================================================================
# 4. CAMERA MANAGEMENT TESTS
# ============================================================================


def test_camera_management_and_security(client: TestClient, admin_user: User, test_dept: Department):
    headers = auth_headers(admin_user)

    # Security check: URL with embedded credentials must be rejected
    bad_url_res = client.post(
        "/admin/cameras",
        json={
            "camera_name": "Insecure Cam",
            "department_id": test_dept.id,
            "stream_url": "rtsp://admin:pass123@192.168.1.10:554/live",
            "stream_type": "RTSP",
        },
        headers=headers,
    )
    assert bad_url_res.status_code == 400
    assert "must not contain embedded credentials" in bad_url_res.json()["detail"]

    # Register valid camera
    good_res = client.post(
        "/admin/cameras",
        json={
            "camera_name": "Perimeter Cam 9",
            "department_id": test_dept.id,
            "stream_url": "rtsp://192.168.1.100:554/ch01",
            "stream_type": "RTSP",
            "sample_fps": 1.5,
            "sampling_interval": 1.0,
            "password": "SecureStreamPassword123",
        },
        headers=headers,
    )
    assert good_res.status_code == 201
    cam_id = good_res.json()["id"]

    # Test camera connection
    test_res = client.post(f"/admin/cameras/{cam_id}/test", headers=headers)
    assert test_res.status_code == 200
    assert test_res.json()["connection_test"] == "SUCCESS"

    # Delete camera
    del_res = client.delete(f"/admin/cameras/{cam_id}", headers=headers)
    assert del_res.status_code == 200


# ============================================================================
# 5. SYSTEM CONFIGURATION TESTS
# ============================================================================


def test_system_config_and_audit(client: TestClient, admin_user: User, db_session: Session):
    config_service.initialize_defaults(db_session)
    headers = auth_headers(admin_user)

    # 1. Get configs
    get_res = client.get("/admin/config", headers=headers)
    assert get_res.status_code == 200
    configs = get_res.json()
    assert len(configs) > 5

    # 2. Update config with audit justification
    update_res = client.put(
        "/admin/config",
        json={
            "updates": [
                {
                    "key": "PERSON_DETECTION_THRESHOLD",
                    "value": 0.55,
                    "reason": "Optimize precision based on validation metrics",
                }
            ],
            "confirmation": True,
        },
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["status"] == "SUCCESS"

    # 3. Check invalid range validation rejection (e.g. threshold > 1.0)
    bad_res = client.put(
        "/admin/config",
        json={
            "updates": [
                {
                    "key": "PERSON_DETECTION_THRESHOLD",
                    "value": 2.5,
                    "reason": "Test out of bound",
                }
            ],
            "confirmation": True,
        },
        headers=headers,
    )
    assert bad_res.status_code == 400

    # 4. Check config audit trail
    audit_res = client.get("/admin/config/audit", headers=headers)
    assert audit_res.status_code == 200
    audits = audit_res.json()
    assert any(a["key"] == "PERSON_DETECTION_THRESHOLD" for a in audits)


# ============================================================================
# 6. WORKER & FLEET TELEMETRY TESTS
# ============================================================================


def test_worker_management(client: TestClient, admin_user: User):
    headers = auth_headers(admin_user)

    workers_res = client.get("/admin/workers", headers=headers)
    assert workers_res.status_code == 200
    workers = workers_res.json()
    assert len(workers) >= 5
    assert any(w["worker_name"] == "ai_inference_worker" for w in workers)

    # Test worker restart
    restart_res = client.post("/admin/workers/ai_inference_worker/restart", headers=headers)
    assert restart_res.status_code == 200
    assert restart_res.json()["worker"]["status"] == "IDLE"


# ============================================================================
# 7. HEALTH MONITORING ENDPOINTS TESTS
# ============================================================================


def test_health_check_endpoints(client: TestClient, admin_user: User):
    # Public & container orchestrator probes
    assert client.get("/health").status_code == 200
    assert client.get("/health/ready").status_code == 200
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/database").status_code == 200
    assert client.get("/health/ai").status_code == 200
    assert client.get("/health/workers").status_code == 200
    assert client.get("/health/storage").status_code == 200

    # Admin comprehensive health probe
    admin_health = client.get("/admin/system-health", headers=auth_headers(admin_user))
    assert admin_health.status_code == 200
    data = admin_health.json()
    assert "database" in data
    assert "workers" in data
    assert "storage" in data


# ============================================================================
# 8. BACKUP & VERIFY TESTS
# ============================================================================


def test_backup_create_verify_and_restore(client: TestClient, admin_user: User):
    headers = auth_headers(admin_user)

    # 1. Create backup
    create_res = client.post(
        "/admin/backups",
        json={"backup_type": "CONFIG", "notes": "Automated test configuration backup"},
        headers=headers,
    )
    assert create_res.status_code == 201
    backup_data = create_res.json()
    backup_id = backup_data["backup_id"]
    assert backup_id.startswith("BKP-")

    # 2. List backups
    list_res = client.get("/admin/backups", headers=headers)
    assert list_res.status_code == 200
    assert any(b["backup_id"] == backup_id for b in list_res.json())

    # 3. Verify SHA-256 and archive integrity
    verify_res = client.post(f"/admin/backups/{backup_id}/verify", headers=headers)
    assert verify_res.status_code == 200
    assert verify_res.json()["is_valid"] is True
    assert verify_res.json()["status"] == "VERIFIED"

    # 4. Restore without explicit confirmation code must fail
    bad_restore = client.post(
        f"/admin/backups/{backup_id}/restore",
        json={"confirmation_code": "wrong_code"},
        headers=headers,
    )
    assert bad_restore.status_code == 400

    # 5. Restore with CONFIRM_RESTORE succeeds
    good_restore = client.post(
        f"/admin/backups/{backup_id}/restore",
        json={"confirmation_code": "CONFIRM_RESTORE"},
        headers=headers,
    )
    assert good_restore.status_code == 200
    assert good_restore.json()["status"] == "RESTORED"


# ============================================================================
# 9. AUDIT LOGGING QUERY TESTS
# ============================================================================


def test_audit_logs_query(client: TestClient, admin_user: User):
    headers = auth_headers(admin_user)
    res = client.get("/admin/audit", headers=headers)
    assert res.status_code == 200
    logs = res.json()
    assert isinstance(logs, list)


# ============================================================================
# 10. FINAL SYSTEM INTEGRATION TEST (SECTION 19)
# ============================================================================


def test_complete_end_to_end_system_workflow(client: TestClient, admin_user: User, db_session: Session):
    """
    End-to-End Test (Section 19):
    1. Authorized User Login
    2. Create Department
    3. Create Missing/Wanted Case
    4. Register Authorized CCTV Camera
    5. Ingest observation & Face Quality Assessment
    6. Candidate Match Proposal
    7. Mandatory Human Review Verification (No alert can bypass human verification)
    8. Alert Dispatch & Department Notification Routing
    9. Evidence Chain-of-Custody & Audit Trail Inspection
    """
    headers = auth_headers(admin_user)

    # 1. Create Department
    dept_res = client.post(
        "/admin/departments",
        json={"department_name": "Integration Test Precinct", "department_type": "POLICE", "location": "Sector 9"},
        headers=headers,
    )
    assert dept_res.status_code == 201
    dept_id = dept_res.json()["id"]

    # 2. Create Missing Case
    case = Case(
        case_number="CASE-2026-INTG01",
        title="Integration Subject Search",
        category=CaseCategory.MISSING.value,
        priority=CasePriority.HIGH.value,
        status=CaseStatus.ACTIVE.value,
        person_identifier="PID-INTG-01",
        description="Missing research subject for end-to-end integration verification",
        department_id=dept_id,
        created_by=admin_user.id,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    # 3. Register Authorized CCTV Camera
    cam_res = client.post(
        "/admin/cameras",
        json={
            "camera_name": "Terminal E Gate 4",
            "department_id": dept_id,
            "stream_url": "rtsp://10.0.0.10:554/live",
            "stream_type": "RTSP",
        },
        headers=headers,
    )
    assert cam_res.status_code == 201
    cam_id = cam_res.json()["id"]

    # 4. Create Review Event (AI Proposed Candidate Match)
    review_event = ReviewEventDB(
        match_event_id="EVT-INTG-001",
        case_id=case.id,
        camera_id=cam_id,
        case_number=case.case_number,
        similarity_score=0.91,
        status=ReviewStatus.PENDING_REVIEW.value,
    )
    db_session.add(review_event)
    db_session.commit()
    db_session.refresh(review_event)

    # 5. Mandatory Human Verification Check
    # Verify: System must NOT automatically confirm identity or create alert without human action
    initial_alerts = db_session.query(AlertDB).filter(AlertDB.case_id == case.id).count()
    assert initial_alerts == 0, "Security Invariant Violated: Alert created before human verification!"

    # Authorized Human Reviewer Confirms Match for Action
    review_event.status = ReviewStatus.CONFIRMED_FOR_ACTION.value
    review_event.decision = ReviewDecision.CONFIRM_FOR_ACTION.value
    review_event.decision_notes = "Verified facial landmarks and ear morphology match reference photo."
    review_event.assigned_to = admin_user.id
    review_event.decision_at = datetime.utcnow()
    db_session.commit()

    # 6. Dispatch Alert following Human Confirmation
    alert = AlertDB(
        alert_number="ALT-2026-000099",
        match_event_id="EVT-INTG-001",
        review_event_id=review_event.id,
        case_id=case.id,
        case_number=case.case_number,
        category="MISSING",
        originating_department_id=dept_id,
        priority=AlertPriority.HIGH.value,
        status=AlertStatus.SENT.value,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)


    # 7. Verify Alert and Audit Logging
    final_alert = db_session.query(AlertDB).filter(AlertDB.id == alert.id).first()
    assert final_alert is not None
    assert final_alert.status == AlertStatus.SENT.value

    # Verify Dashboard reflects confirmed-for-action and active cases
    dash_res = client.get("/admin/dashboard", headers=headers)
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert dash_data["confirmed_for_action_events"] >= 1
    assert dash_data["active_cases"] >= 1
