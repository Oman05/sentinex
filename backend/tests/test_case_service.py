from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.case import Case
from app.models.department import Department
from app.models.user import User, UserRole
from app.services.case_service import CaseService


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:", echo=False, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def create_demo_user_and_department(db):
    dept = Department(department_name="Test Dept", department_type="Local")
    db.add(dept)
    db.commit()
    db.refresh(dept)

    admin = User(username="admin", email="admin@example.com", password_hash="x", role=UserRole.ADMIN.value, department_id=dept.id)
    police = User(username="police", email="police@example.com", password_hash="x", role=UserRole.POLICE.value, department_id=dept.id)
    other = User(username="other", email="other@example.com", password_hash="x", role=UserRole.POLICE.value, department_id=None)
    db.add_all([admin, police, other])
    db.commit()
    db.refresh(admin)
    db.refresh(police)
    db.refresh(other)
    return dept, admin, police, other


def test_create_case_and_audit_logged():
    db = setup_in_memory_db()
    dept, admin, police, other = create_demo_user_and_department(db)

    class Payload:
        category = "MISSING"
        title = "Missing Person"
        person_identifier = "PID123"
        description = "Someone missing"
        department_id = None
        priority = "HIGH"
        last_known_location = "Location X"
        status = None

    case = CaseService.create_case(db, police, Payload)
    assert case.id is not None
    assert case.case_number.startswith("MP-")
    assert case.department_id == dept.id
    # An audit log should have been created
    from app.models.audit_log import AuditLog

    logs = db.query(AuditLog).filter(AuditLog.resource_type == 'CASE', AuditLog.resource_id == case.id).all()
    assert len(logs) >= 1


def test_status_transitions_and_validation():
    db = setup_in_memory_db()
    dept, admin, police, other = create_demo_user_and_department(db)

    # Create a case
    c = Case(case_number="MP-2026-0005", category="MISSING", title="T", person_identifier="p", description="d", department_id=dept.id, created_by=police.id, status="DRAFT", priority="MEDIUM")
    db.add(c)
    db.commit()
    db.refresh(c)

    # Valid transition: DRAFT -> ACTIVE
    updated = CaseService.update_case_status(db, police, c, "ACTIVE")
    assert updated.status == "ACTIVE"

    # Invalid transition: ACTIVE -> DRAFT (not allowed)
    with pytest.raises(ValueError):
        CaseService.update_case_status(db, police, updated, "DRAFT")

    # Admin can change status freely where allowed
    updated2 = CaseService.update_case_status(db, admin, updated, "UNDER_REVIEW")
    assert updated2.status == "UNDER_REVIEW"


def test_access_control_enforcement_on_update():
    db = setup_in_memory_db()
    dept, admin, police, other = create_demo_user_and_department(db)

    # Create a case by police
    c = Case(case_number="MP-2026-0010", category="MISSING", title="T2", person_identifier="p2", description="d2", department_id=dept.id, created_by=police.id, status="DRAFT", priority="MEDIUM")
    db.add(c)
    db.commit()
    db.refresh(c)

    class Payload:
        title = "Updated Title"
        person_identifier = None
        description = None
        department_id = None
        priority = None
        last_known_location = None
        category = None

    # Other user with no department should not be allowed to update
    with pytest.raises(PermissionError):
        CaseService.update_case(db, other, c, Payload)

    # Admin can update
    updated = CaseService.update_case(db, admin, c, Payload)
    assert updated.title == "Updated Title"
