"""
Module 9 Unit & Integration Tests – Approval Validation
======================================================
Tests Section 2 & 29:
- AI possible match, Module 7 match, high similarity, or unreviewed events CANNOT create alerts.
- Only Module 8 events with status=CONFIRMED_FOR_ACTION and decision=CONFIRM_FOR_ACTION
  can create operational alerts.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.main import app
from app.models.case import Case, CaseCategory, CasePriority, CaseStatus
from app.models.department import Department
from app.models.review_event import ReviewDecision, ReviewEventDB, ReviewStatus
from app.models.user import User, UserRole
from app.services.alert_service import alert_service


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_police_token(db_session: Session):
    dept = Department(
        department_name="Validation Police Dept",
        department_type="POLICE",
        department_code="DEPT-VAL-01",
        is_active=True,
        notification_enabled=True,
    )
    db_session.add(dept)
    db_session.flush()

    user = User(
        username="officer_val",
        email="officer_val@sentinex.gov",
        password_hash="hashed",
        role=UserRole.POLICE.value,
        department_id=dept.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return create_access_token({"sub": user.username, "role": user.role, "user_id": user.id}), user, dept


@pytest.fixture
def base_test_data(db_session: Session, auth_police_token):
    token, user, dept = auth_police_token
    case = Case(
        case_number="VAL-CASE-2026-001",
        category=CaseCategory.WANTED.value,
        title="Validation Subject",
        person_identifier="SUBJ-VAL-001",
        description="Testing approval invariants",
        department_id=dept.id,
        created_by=user.id,
        status=CaseStatus.ACTIVE.value,
        priority=CasePriority.HIGH.value,
        is_active=True,
    )
    db_session.add(case)
    db_session.commit()
    return token, user, dept, case


@pytest.mark.asyncio
async def test_module7_unapproved_cannot_trigger_alert_service(db_session: Session, base_test_data):
    token, user, dept, case = base_test_data

    # Event in PENDING_REVIEW (simulating Module 7 output waiting for human)
    unapproved_event = ReviewEventDB(
        match_event_id="match-unapproved-001",
        case_id=case.id,
        case_number=case.case_number,
        category=case.category,
        similarity_score=0.985,  # High similarity from AI
        candidate_ranking_score=0.99,
        decision_state="POSSIBLE_MATCH",
        status=ReviewStatus.PENDING_REVIEW.value,
        decision=None,
    )
    db_session.add(unapproved_event)
    db_session.commit()

    # Attempt alert creation directly on unapproved event -> Must raise ValueError
    with pytest.raises(ValueError, match="Alerts require human approval 'CONFIRMED_FOR_ACTION'"):
        await alert_service.create_alert_from_review_event(unapproved_event, db_session)


@pytest.mark.asyncio
async def test_rejected_review_cannot_trigger_alert(db_session: Session, base_test_data):
    token, user, dept, case = base_test_data

    rejected_event = ReviewEventDB(
        match_event_id="match-rejected-001",
        case_id=case.id,
        case_number=case.case_number,
        category=case.category,
        similarity_score=0.91,
        candidate_ranking_score=0.92,
        decision_state="POSSIBLE_MATCH",
        status=ReviewStatus.REJECTED.value,
        decision=ReviewDecision.REJECTED.value,
    )
    db_session.add(rejected_event)
    db_session.commit()

    with pytest.raises(ValueError, match="Alerts require human approval 'CONFIRMED_FOR_ACTION'"):
        await alert_service.create_alert_from_review_event(rejected_event, db_session)


def test_internal_api_rejects_non_module8_source(client: TestClient, base_test_data, db_session: Session):
    token, user, dept, case = base_test_data

    event = ReviewEventDB(
        match_event_id="match-api-test-001",
        case_id=case.id,
        case_number=case.case_number,
        category=case.category,
        similarity_score=0.94,
        candidate_ranking_score=0.95,
        decision_state="POSSIBLE_MATCH",
        status=ReviewStatus.CONFIRMED_FOR_ACTION.value,
        decision=ReviewDecision.CONFIRM_FOR_ACTION.value,
    )
    db_session.add(event)
    db_session.commit()

    headers = {"Authorization": f"Bearer {token}"}

    # Attempt with source_module = "MODULE_7"
    response = client.post(
        "/api/internal/alerts/create",
        headers=headers,
        json={
            "source_module": "MODULE_7",  # Invalid source module
            "review_status": "CONFIRMED_FOR_ACTION",
            "review_event_id": event.id,
            "match_event_id": event.match_event_id,
            "case_id": case.id,
        },
    )
    assert response.status_code == 400
    assert "MODULE_8" in response.json()["detail"]


def test_internal_api_rejects_unconfirmed_status(client: TestClient, base_test_data, db_session: Session):
    token, user, dept, case = base_test_data

    event = ReviewEventDB(
        match_event_id="match-api-pending-001",
        case_id=case.id,
        case_number=case.case_number,
        category=case.category,
        similarity_score=0.92,
        candidate_ranking_score=0.93,
        decision_state="POSSIBLE_MATCH",
        status=ReviewStatus.PENDING_REVIEW.value,
        decision=None,
    )
    db_session.add(event)
    db_session.commit()

    headers = {"Authorization": f"Bearer {token}"}

    # Attempt with review_status = "PENDING_REVIEW"
    response = client.post(
        "/api/internal/alerts/create",
        headers=headers,
        json={
            "source_module": "MODULE_8",
            "review_status": "PENDING_REVIEW",  # Not confirmed
            "review_event_id": event.id,
            "match_event_id": event.match_event_id,
            "case_id": case.id,
        },
    )
    assert response.status_code == 400
    assert "CONFIRMED_FOR_ACTION" in response.json()["detail"]


def test_internal_api_success_with_confirmed_event(client: TestClient, base_test_data, db_session: Session):
    token, user, dept, case = base_test_data

    event = ReviewEventDB(
        match_event_id="match-api-confirmed-001",
        case_id=case.id,
        case_number=case.case_number,
        category=case.category,
        similarity_score=0.94,
        candidate_ranking_score=0.95,
        decision_state="POSSIBLE_MATCH",
        status=ReviewStatus.CONFIRMED_FOR_ACTION.value,
        decision=ReviewDecision.CONFIRM_FOR_ACTION.value,
    )
    db_session.add(event)
    db_session.commit()

    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/internal/alerts/create",
        headers=headers,
        json={
            "source_module": "MODULE_8",
            "review_status": "CONFIRMED_FOR_ACTION",
            "review_event_id": event.id,
            "match_event_id": event.match_event_id,
            "case_id": case.id,
            "notes": "Authorized confirmation test",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["alert_number"].startswith("ALT-")
    assert data["case_number"] == case.case_number
    assert data["status"] in ("DELIVERED", "SENT", "CREATED")
