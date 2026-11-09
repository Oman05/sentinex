"""
Module 9 Unit Tests – Notification Delivery & Channels
======================================================
Tests Section 11, 12, 14, 28, 29:
- Multi-channel notification delivery (IN-APP, EMAIL sandbox).
- Standardized notification message formatting.
- AI safety invariant: No biometric data or raw CCTV frames in notifications.
- Failed notification recording and retry mechanism.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.models.alert import (
    AlertDB,
    AlertNotificationDB,
    AlertPriority,
    AlertRecipientDB,
    AlertStatus,
    DeliveryChannel,
    RecipientType,
)
from app.models.case import Case, CaseCategory, CasePriority, CaseStatus
from app.models.department import Department
from app.models.review_event import ReviewDecision, ReviewEventDB, ReviewStatus
from app.models.user import User, UserRole
from app.services.alert_service import alert_service
from app.services.notification_adapters import (
    build_standard_alert_message,
    notification_dispatcher,
)


@pytest.fixture
def notif_test_data(db_session: Session):
    dept = Department(
        department_name="Notif Police Dept",
        department_code="DEPT-NOTIF",
        department_type="POLICE",
        contact_email="notif@police.gov",
        is_active=True,
        notification_enabled=True,
    )
    db_session.add(dept)
    db_session.flush()

    user = User(
        username="officer_notif",
        email="officer_notif@police.gov",
        password_hash="hashed",
        role=UserRole.POLICE.value,
        department_id=dept.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    case = Case(
        case_number="CASE-NOTIF-001",
        category=CaseCategory.WANTED.value,
        title="Wanted Suspect Investigation",
        person_identifier="WANTED-001",
        description="High Priority",
        department_id=dept.id,
        created_by=user.id,
        status=CaseStatus.ACTIVE.value,
        priority=CasePriority.HIGH.value,
        is_active=True,
    )
    db_session.add(case)
    db_session.commit()
    return user, dept, case


def test_standard_notification_message_formatting(db_session: Session, notif_test_data):
    user, dept, case = notif_test_data

    alert = AlertDB(
        alert_number="ALT-2026-000042",
        match_event_id="match-42",
        review_event_id=1,
        case_id=case.id,
        case_number=case.case_number,
        category=case.category,
        originating_department_id=dept.id,
        detected_camera_code="CCTV-004",
        detected_location="North Exit Gate",
        priority=AlertPriority.HIGH.value,
        status=AlertStatus.CREATED.value,
    )
    recipient = AlertRecipientDB(
        alert_id=1,
        department_id=dept.id,
        recipient_type=RecipientType.ORIGINATING_DEPARTMENT.value,
        delivery_channel=DeliveryChannel.EMAIL.value,
        destination_reference=dept.contact_email,
    )

    msg = build_standard_alert_message(alert, recipient)

    # Required fields per Section 14
    assert "NEW AUTHORIZED ALERT" in msg
    assert "ALT-2026-000042" in msg
    assert case.case_number in msg
    assert "CCTV-004" in msg
    assert "CONFIRMED FOR ACTION" in msg
    assert "secure SENTINEX investigation dashboard" in msg

    # AI Safety Invariant: No raw biometric or image payloads in external message text
    assert "vector" not in msg.lower()
    assert "embedding" not in msg.lower()
    assert "data:image" not in msg
    assert "0x" not in msg


@pytest.mark.asyncio
async def test_in_app_notification_dispatch(db_session: Session, notif_test_data):
    user, dept, case = notif_test_data

    alert = AlertDB(
        alert_number="ALT-2026-000050",
        match_event_id="match-50",
        review_event_id=1,
        case_id=case.id,
        case_number=case.case_number,
        category=case.category,
        originating_department_id=dept.id,
        status=AlertStatus.CREATED.value,
    )
    db_session.add(alert)
    db_session.flush()

    recipient = AlertRecipientDB(
        alert_id=alert.id,
        department_id=dept.id,
        recipient_type=RecipientType.ORIGINATING_DEPARTMENT.value,
        delivery_channel=DeliveryChannel.IN_APP.value,
    )
    db_session.add(recipient)
    db_session.flush()

    notification = AlertNotificationDB(
        alert_id=alert.id,
        recipient_id=recipient.id,
        channel=DeliveryChannel.IN_APP.value,
        status=AlertStatus.QUEUED.value,
    )
    db_session.add(notification)
    db_session.flush()

    res = await notification_dispatcher.dispatch(alert, recipient, notification)
    assert res.success is True
    assert res.status == AlertStatus.DELIVERED.value
    assert notification.delivered_at is not None
    assert notification.attempt_count == 1


@pytest.mark.asyncio
async def test_email_simulation_failure_and_retry(db_session: Session, notif_test_data):
    user, dept, case = notif_test_data

    alert = AlertDB(
        alert_number="ALT-2026-000051",
        match_event_id="match-51",
        review_event_id=1,
        case_id=case.id,
        case_number=case.case_number,
        category=case.category,
        originating_department_id=dept.id,
        status=AlertStatus.FAILED.value,
    )
    db_session.add(alert)
    db_session.flush()

    # Destination configured to simulate failure
    recipient = AlertRecipientDB(
        alert_id=alert.id,
        department_id=dept.id,
        recipient_type=RecipientType.ORIGINATING_DEPARTMENT.value,
        delivery_channel=DeliveryChannel.EMAIL.value,
        destination_reference="fail@police.gov",  # Trigger simulation
        status=AlertStatus.FAILED.value,
    )
    db_session.add(recipient)
    db_session.flush()

    notification = AlertNotificationDB(
        alert_id=alert.id,
        recipient_id=recipient.id,
        channel=DeliveryChannel.EMAIL.value,
        status=AlertStatus.QUEUED.value,
    )
    db_session.add(notification)
    db_session.flush()

    # Dispatch to failing address
    res = await notification_dispatcher.dispatch(alert, recipient, notification)
    assert res.success is False
    assert notification.status == AlertStatus.FAILED.value
    assert notification.error_code == "SMTP_RECIPIENT_REJECTED"
    db_session.commit()

    # Now fix destination and trigger retry via service
    recipient.destination_reference = "repaired@police.gov"
    db_session.commit()

    retried = await alert_service.retry_failed_notifications(
        alert_id=alert.id,
        user=user,
        notification_id=notification.id,
        db=db_session,
    )
    assert len(retried) == 1
    assert retried[0].status == AlertStatus.DELIVERED.value
    assert retried[0].attempt_count == 2
