"""
Module 9 Unit Tests – Duplicate Alert Prevention & Deduplication
==============================================================
Tests Section 18, 19, 29:
- Preventing repeated alerts for the same case/camera within configured window.
- Multiple observations increment observation_count and update timeline.
- Distinct cases/cameras properly create new alerts.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.models.camera import Camera
from app.models.case import Case, CaseCategory, CasePriority, CaseStatus
from app.models.department import Department
from app.models.review_event import ReviewDecision, ReviewEventDB, ReviewStatus
from app.models.user import User, UserRole
from app.services.alert_service import alert_service


@pytest.fixture
def dedup_setup(db_session: Session):
    dept = Department(
        department_name="Dedup Police Dept",
        department_code="DEPT-DEDUP",
        department_type="POLICE",
        is_active=True,
        notification_enabled=True,
    )
    db_session.add(dept)
    db_session.flush()

    user = User(
        username="officer_dedup",
        email="officer_dedup@police.gov",
        password_hash="hashed",
        role=UserRole.POLICE.value,
        department_id=dept.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    case = Case(
        case_number="CASE-DEDUP-001",
        category=CaseCategory.WANTED.value,
        title="Deduplication Target",
        person_identifier="DEDUP-001",
        description="Testing duplicate prevention",
        department_id=dept.id,
        created_by=user.id,
        status=CaseStatus.ACTIVE.value,
        priority=CasePriority.HIGH.value,
        is_active=True,
    )
    db_session.add(case)
    db_session.flush()

    camera = Camera(
        camera_name="Main Gate Cam",
        camera_code="CAM-DEDUP-1",
        department_id=dept.id,
        stream_url="rtsp://localhost/dedup1",
        location_name="Gate 1",
        is_active=True,
    )
    db_session.add(camera)
    db_session.commit()
    return user, dept, case, camera


@pytest.mark.asyncio
async def test_repeated_observation_updates_existing_alert(db_session: Session, dedup_setup):
    user, dept, case, camera = dedup_setup

    # Observation 1
    event_1 = ReviewEventDB(
        match_event_id="match-obs-001",
        case_id=case.id,
        case_number=case.case_number,
        category=case.category,
        similarity_score=0.93,
        candidate_ranking_score=0.93,
        decision_state="POSSIBLE_MATCH",
        camera_id=camera.id,
        camera_location="Gate 1",
        track_id="TRK-100",
        status=ReviewStatus.CONFIRMED_FOR_ACTION.value,
        decision=ReviewDecision.CONFIRM_FOR_ACTION.value,
    )
    db_session.add(event_1)
    db_session.commit()

    alert_1 = await alert_service.create_alert_from_review_event(event_1, db_session, actor=user)
    assert alert_1.observation_count == 1
    initial_alert_id = alert_1.id
    initial_alert_number = alert_1.alert_number

    # Observation 2 (same case, same camera, 2 minutes later)
    event_2 = ReviewEventDB(
        match_event_id="match-obs-002",
        case_id=case.id,
        case_number=case.case_number,
        category=case.category,
        similarity_score=0.95,
        candidate_ranking_score=0.95,
        decision_state="POSSIBLE_MATCH",
        camera_id=camera.id,
        camera_location="Gate 1",
        track_id="TRK-100",
        status=ReviewStatus.CONFIRMED_FOR_ACTION.value,
        decision=ReviewDecision.CONFIRM_FOR_ACTION.value,
    )
    db_session.add(event_2)
    db_session.commit()

    alert_2 = await alert_service.create_alert_from_review_event(event_2, db_session, actor=user)

    # Must return the SAME alert instance, NOT create a second row
    assert alert_2.id == initial_alert_id
    assert alert_2.alert_number == initial_alert_number
    assert alert_2.observation_count == 2

    # Check timeline has OBSERVATION_UPDATED
    events = [t.event_type for t in alert_2.timeline]
    assert "OBSERVATION_UPDATED" in events


@pytest.mark.asyncio
async def test_distinct_camera_creates_separate_alert(db_session: Session, dedup_setup):
    user, dept, case, camera = dedup_setup

    camera_2 = Camera(
        camera_name="Back Gate Cam",
        camera_code="CAM-DEDUP-2",
        department_id=dept.id,
        stream_url="rtsp://localhost/dedup2",
        location_name="Gate 2",
        is_active=True,
    )
    db_session.add(camera_2)
    db_session.commit()

    event_cam1 = ReviewEventDB(
        match_event_id="match-cam1",
        case_id=case.id,
        case_number=case.case_number,
        category=case.category,
        similarity_score=0.92,
        candidate_ranking_score=0.92,
        decision_state="POSSIBLE_MATCH",
        camera_id=camera.id,
        status=ReviewStatus.CONFIRMED_FOR_ACTION.value,
        decision=ReviewDecision.CONFIRM_FOR_ACTION.value,
    )
    event_cam2 = ReviewEventDB(
        match_event_id="match-cam2",
        case_id=case.id,
        case_number=case.case_number,
        category=case.category,
        similarity_score=0.94,
        candidate_ranking_score=0.94,
        decision_state="POSSIBLE_MATCH",
        camera_id=camera_2.id,
        status=ReviewStatus.CONFIRMED_FOR_ACTION.value,
        decision=ReviewDecision.CONFIRM_FOR_ACTION.value,
    )
    db_session.add_all([event_cam1, event_cam2])
    db_session.commit()

    alert_1 = await alert_service.create_alert_from_review_event(event_cam1, db_session)
    alert_2 = await alert_service.create_alert_from_review_event(event_cam2, db_session)

    assert alert_1.id != alert_2.id
    assert alert_1.alert_number != alert_2.alert_number
