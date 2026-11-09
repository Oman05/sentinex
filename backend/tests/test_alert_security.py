"""
Module 9 Unit & Integration Tests – Security & Department Access Control
========================================================================
Tests Section 24, 25, 29, 31:
- Department-level access control (unauthorized departments cannot view/acknowledge).
- Admin system-wide access vs Police jurisdiction access.
- Unauthenticated access rejection (401).
- Immutable audit trail recording.
- Unacknowledged alert escalation framework.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.main import app
from app.models.alert import AlertDB, AlertPriority, AlertStatus
from app.models.case import Case, CaseCategory, CasePriority, CaseStatus
from app.models.department import Department
from app.models.user import User, UserRole
from app.services.alert_service import alert_service


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def security_setup(db_session: Session):
    # Dept A: Originating
    dept_a = Department(
        department_name="Department Alpha",
        department_code="DEPT-ALPHA",
        department_type="POLICE",
        is_active=True,
        notification_enabled=True,
    )
    # Dept B: Nearest
    dept_b = Department(
        department_name="Department Bravo",
        department_code="DEPT-BRAVO",
        department_type="POLICE",
        is_active=True,
        notification_enabled=True,
    )
    # Dept C: Unrelated
    dept_c = Department(
        department_name="Department Charlie (Unrelated)",
        department_code="DEPT-CHARLIE",
        department_type="POLICE",
        is_active=True,
        notification_enabled=True,
    )
    db_session.add_all([dept_a, dept_b, dept_c])
    db_session.flush()

    user_a = User(
        username="officer_alpha",
        email="alpha@police.gov",
        password_hash="hashed",
        role=UserRole.POLICE.value,
        department_id=dept_a.id,
        is_active=True,
    )
    user_b = User(
        username="officer_bravo",
        email="bravo@police.gov",
        password_hash="hashed",
        role=UserRole.POLICE.value,
        department_id=dept_b.id,
        is_active=True,
    )
    user_c = User(
        username="officer_charlie",
        email="charlie@police.gov",
        password_hash="hashed",
        role=UserRole.POLICE.value,
        department_id=dept_c.id,
        is_active=True,
    )
    admin_user = User(
        username="admin_super",
        email="admin@sentinex.gov",
        password_hash="hashed",
        role=UserRole.ADMIN.value,
        department_id=None,
        is_active=True,
    )
    db_session.add_all([user_a, user_b, user_c, admin_user])
    db_session.flush()

    case = Case(
        case_number="CASE-SEC-001",
        category=CaseCategory.WANTED.value,
        title="Security Test Case",
        person_identifier="SEC-001",
        description="Testing security boundaries",
        department_id=dept_a.id,
        created_by=user_a.id,
        status=CaseStatus.ACTIVE.value,
        priority=CasePriority.HIGH.value,
        is_active=True,
    )
    db_session.add(case)
    db_session.flush()

    alert = AlertDB(
        alert_number="ALT-2026-SEC001",
        match_event_id="match-sec-001",
        review_event_id=1,
        case_id=case.id,
        case_number=case.case_number,
        category=case.category,
        originating_department_id=dept_a.id,
        nearest_department_id=dept_b.id,
        priority=AlertPriority.HIGH.value,
        status=AlertStatus.DELIVERED.value,
    )
    db_session.add(alert)
    db_session.commit()

    token_a = create_access_token({"sub": user_a.username, "role": user_a.role, "user_id": user_a.id})
    token_b = create_access_token({"sub": user_b.username, "role": user_b.role, "user_id": user_b.id})
    token_c = create_access_token({"sub": user_c.username, "role": user_c.role, "user_id": user_c.id})
    token_admin = create_access_token({"sub": admin_user.username, "role": admin_user.role, "user_id": admin_user.id})

    return {
        "alert": alert,
        "token_a": token_a,
        "token_b": token_b,
        "token_c": token_c,
        "token_admin": token_admin,
    }


def test_unauthenticated_requests_blocked(client: TestClient, security_setup):
    alert = security_setup["alert"]
    resp = client.get(f"/api/alerts/{alert.id}")
    assert resp.status_code == 401


def test_unauthorized_department_cannot_view_alert(client: TestClient, security_setup):
    alert = security_setup["alert"]
    token_c = security_setup["token_c"]

    resp = client.get(
        f"/api/alerts/{alert.id}",
        headers={"Authorization": f"Bearer {token_c}"},
    )
    assert resp.status_code == 403
    assert "not authorized" in resp.json()["detail"].lower()


def test_originating_and_nearest_departments_can_view(client: TestClient, security_setup):
    alert = security_setup["alert"]
    token_a = security_setup["token_a"]
    token_b = security_setup["token_b"]

    resp_a = client.get(f"/api/alerts/{alert.id}", headers={"Authorization": f"Bearer {token_a}"})
    assert resp_a.status_code == 200

    resp_b = client.get(f"/api/alerts/{alert.id}", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == 200


def test_admin_can_view_all_alerts(client: TestClient, security_setup):
    alert = security_setup["alert"]
    token_admin = security_setup["token_admin"]

    resp = client.get(f"/api/alerts/{alert.id}", headers={"Authorization": f"Bearer {token_admin}"})
    assert resp.status_code == 200
    assert resp.json()["alert_number"] == alert.alert_number


def test_acknowledgment_workflow_and_audit_trail(client: TestClient, security_setup, db_session: Session):
    alert = security_setup["alert"]
    token_a = security_setup["token_a"]

    # Acknowledge
    resp = client.post(
        f"/api/alerts/{alert.id}/acknowledge",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"notes": "Deploying patrol unit 4 to scene."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ACKNOWLEDGED"

    # Verify audit log recorded
    resp_timeline = client.get(
        f"/api/alerts/{alert.id}/timeline",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    events = [t["event_type"] for t in resp_timeline.json()]
    assert "ALERT_ACKNOWLEDGED" in events


@pytest.mark.asyncio
async def test_escalation_framework(db_session: Session, security_setup):
    alert = security_setup["alert"]
    # Backdate created_at to 30 minutes ago
    alert.created_at = datetime.utcnow() - timedelta(minutes=30)
    db_session.commit()

    escalated = await alert_service.check_and_escalate_unacknowledged_alerts(db_session)
    assert len(escalated) >= 1
    assert any(a.id == alert.id for a in escalated)

    # Check that escalation recipient was added
    db_session.refresh(alert)
    recip_types = [r.recipient_type for r in alert.recipients]
    assert "ESCALATION_RECIPIENT" in recip_types
