"""
Module 9 Unit Tests – Department Routing & Geospatial Lookup
============================================================
Tests Section 3, 6, 7, 29:
- Originating department routing from case.
- Nearest authorized department via Haversine distance.
- Filtering of inactive or notification-disabled departments.
- Fallback routing when coordinates are absent.
- Transparency of routing_reason.
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
from app.services.geo_routing_service import geo_routing_service, haversine_distance


def test_haversine_distance_calculation():
    # Bangalore (12.9716, 77.5946) to Chennai (13.0827, 80.2707) is approx 290 km
    dist = haversine_distance(12.9716, 77.5946, 13.0827, 80.2707)
    assert 280 <= dist <= 310

    # Same location should be 0.0
    zero_dist = haversine_distance(12.9716, 77.5946, 12.9716, 77.5946)
    assert zero_dist == 0.0


def test_geospatial_nearest_department_selection(db_session: Session):
    # Camera in Downtown
    camera = Camera(
        camera_name="Downtown Cam 1",
        camera_code="CAM-GEO-001",
        department_id=1,
        stream_url="rtsp://localhost/geo1",
        latitude=12.9716,
        longitude=77.5946,
        location_name="Downtown Plaza",
        is_active=True,
    )
    db_session.add(camera)

    # Dept Near (0.5 km)
    dept_near = Department(
        department_name="Downtown Police Station",
        department_code="DEPT-NEAR",
        department_type="POLICE",
        latitude=12.9750,
        longitude=77.5970,
        is_active=True,
        notification_enabled=True,
    )
    # Dept Far (25 km)
    dept_far = Department(
        department_name="Suburban Precinct",
        department_code="DEPT-FAR",
        department_type="POLICE",
        latitude=13.1500,
        longitude=77.8000,
        is_active=True,
        notification_enabled=True,
    )
    db_session.add_all([dept_near, dept_far])
    db_session.commit()

    result = geo_routing_service.find_nearest_authorized_department(camera, db_session)
    assert result.department is not None
    assert result.department.id == dept_near.id
    assert result.distance_km is not None
    assert result.distance_km < 1.0
    assert "Downtown Police Station" in result.routing_reason


def test_inactive_and_disabled_departments_are_filtered(db_session: Session):
    camera = Camera(
        camera_name="North Cam",
        camera_code="CAM-NORTH",
        department_id=1,
        stream_url="rtsp://localhost/north",
        latitude=12.9716,
        longitude=77.5946,
        is_active=True,
    )
    db_session.add(camera)

    # Dept 1: very close, but inactive
    dept_inactive = Department(
        department_name="Inactive Station",
        department_code="DEPT-INACTIVE",
        department_type="POLICE",
        latitude=12.9720,
        longitude=77.5950,
        is_active=False,  # Inactive
        notification_enabled=True,
    )
    # Dept 2: close, but notifications disabled
    dept_disabled = Department(
        department_name="Disabled Station",
        department_code="DEPT-DISABLED",
        department_type="POLICE",
        latitude=12.9722,
        longitude=77.5952,
        is_active=True,
        notification_enabled=False,  # Disabled
    )
    # Dept 3: further away, but active and enabled
    dept_active = Department(
        department_name="Active Station",
        department_code="DEPT-ACTIVE",
        department_type="POLICE",
        latitude=12.9900,
        longitude=77.6100,
        is_active=True,
        notification_enabled=True,
    )
    db_session.add_all([dept_inactive, dept_disabled, dept_active])
    db_session.commit()

    result = geo_routing_service.find_nearest_authorized_department(camera, db_session)
    assert result.department is not None
    assert result.department.id == dept_active.id
    assert result.department.department_code == "DEPT-ACTIVE"


def test_jurisdiction_fallback_when_coordinates_absent(db_session: Session):
    camera = Camera(
        camera_name="No GPS Cam",
        camera_code="CAM-NO-GPS",
        department_id=1,
        stream_url="rtsp://localhost/nogps",
        latitude=None,
        longitude=None,
        jurisdiction="Airport Security Zone",
        is_active=True,
    )
    db_session.add(camera)

    dept_airport = Department(
        department_name="Airport Police Unit",
        department_code="DEPT-AIRPORT",
        department_type="POLICE",
        jurisdiction="Airport Security Zone",
        is_active=True,
        notification_enabled=True,
    )
    dept_other = Department(
        department_name="Harbor Police Unit",
        department_code="DEPT-HARBOR",
        department_type="POLICE",
        jurisdiction="Harbor Zone",
        is_active=True,
        notification_enabled=True,
    )
    db_session.add_all([dept_airport, dept_other])
    db_session.commit()

    result = geo_routing_service.find_nearest_authorized_department(camera, db_session)
    assert result.department is not None
    assert result.department.id == dept_airport.id
    assert "Airport Security Zone" in result.routing_reason


@pytest.mark.asyncio
async def test_full_alert_creates_dual_recipients(db_session: Session):
    # Originating department
    dept_orig = Department(
        department_name="Case Registry Dept",
        department_code="DEPT-REG",
        department_type="POLICE",
        contact_email="registry@police.gov",
        is_active=True,
        notification_enabled=True,
    )
    # Nearest department
    dept_nearest = Department(
        department_name="Field Local Station",
        department_code="DEPT-LOCAL",
        department_type="POLICE",
        contact_email="local@police.gov",
        latitude=12.9800,
        longitude=77.6000,
        is_active=True,
        notification_enabled=True,
    )
    db_session.add_all([dept_orig, dept_nearest])
    db_session.flush()

    user = User(
        username="officer_routing",
        email="routing@police.gov",
        password_hash="hashed",
        role=UserRole.POLICE.value,
        department_id=dept_orig.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    case = Case(
        case_number="CASE-ROUTING-001",
        category=CaseCategory.MISSING.value,
        title="Missing Child Investigation",
        person_identifier="CHILD-001",
        description="Priority Search",
        department_id=dept_orig.id,
        created_by=user.id,
        status=CaseStatus.ACTIVE.value,
        priority=CasePriority.HIGH.value,
        is_active=True,
    )
    db_session.add(case)
    db_session.flush()

    camera = Camera(
        camera_name="Mall Cam 2",
        camera_code="CAM-MALL-2",
        department_id=dept_nearest.id,
        stream_url="rtsp://localhost/mall",
        latitude=12.9810,
        longitude=77.6010,
        location_name="Mall West Entrance",
        is_active=True,
    )
    db_session.add(camera)
    db_session.flush()

    event = ReviewEventDB(
        match_event_id="match-routing-001",
        case_id=case.id,
        case_number=case.case_number,
        category=case.category,
        similarity_score=0.96,
        candidate_ranking_score=0.96,
        decision_state="POSSIBLE_MATCH",
        camera_id=camera.id,
        camera_location="Mall West Entrance",
        status=ReviewStatus.CONFIRMED_FOR_ACTION.value,
        decision=ReviewDecision.CONFIRM_FOR_ACTION.value,
    )
    db_session.add(event)
    db_session.commit()

    alert = await alert_service.create_alert_from_review_event(event, db_session, actor=user)

    assert alert.originating_department_id == dept_orig.id
    assert alert.nearest_department_id == dept_nearest.id
    assert len(alert.recipients) >= 2

    # Check recipient types
    recipient_types = {r.recipient_type for r in alert.recipients}
    assert "ORIGINATING_DEPARTMENT" in recipient_types
    assert "NEAREST_AUTHORIZED_DEPARTMENT" in recipient_types
