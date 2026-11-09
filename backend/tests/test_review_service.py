"""
Module 8 – Human Verification & Investigation Dashboard Unit Tests
===================================================================
Tests for ReviewService, business logic, workflow lifecycle transitions,
append-only audit trails, investigation tasks, dashboard analytics,
and AI Safety invariants.

AI Safety Invariants:
- Zero Automated Decisions: Systems starts in PENDING_REVIEW; human must review.
- No "IDENTITY_CONFIRMED" terminology in decisions or statuses.
- Strict state-machine transitions: invalid jumps rejected with 409 Conflict.
- Append-only audit logging: every review interaction leaves an immutable log.
"""

import os
import sys
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database.base import Base
from app.models.camera import Camera
from app.models.case import Case, CaseCategory, CasePriority, CaseStatus
from app.models.department import Department
from app.models.reference_image import ReferenceImage
from app.models.review_event import (
    InvestigationTaskDB,
    ReviewAuditLogDB,
    ReviewDecision,
    ReviewEventDB,
    ReviewStatus,
    TaskPriority,
    TaskStatus,
)
from app.models.user import User, UserRole
from app.schemas.review import (
    AssignRequest,
    EvidenceRequestRequest,
    InvestigationTaskCreate,
    ReviewDecisionRequest,
    StartReviewRequest,
    TaskUpdateRequest,
    SIMILARITY_DISCLAIMER,
)
from app.services.review_service import ReviewService, review_service


# ---------------------------------------------------------------------------
# Test Fixtures & DB Setup
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def demo_department(db_session):
    dept = Department(department_name="Forensic Analysis Unit", department_type="State Police")
    db_session.add(dept)
    db_session.commit()
    db_session.refresh(dept)
    return dept


@pytest.fixture
def examiner_user(db_session, demo_department):
    user = User(
        id=10,
        username="officer_smith",
        email="smith@police.gov",
        password_hash="hashed_pw",
        role=UserRole.POLICE.value,
        department_id=demo_department.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def second_examiner(db_session, demo_department):
    user = User(
        id=11,
        username="officer_davis",
        email="davis@police.gov",
        password_hash="hashed_pw",
        role=UserRole.POLICE.value,
        department_id=demo_department.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session, demo_department):
    user = User(
        id=1,
        username="admin_lead",
        email="admin@sentinex.gov",
        password_hash="hashed_pw",
        role=UserRole.ADMIN.value,
        department_id=demo_department.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_case(db_session, demo_department, admin_user):
    case = Case(
        id=101,
        case_number="MP-2026-0001",
        category=CaseCategory.MISSING.value,
        title="Missing Person Investigation - John Doe",
        person_identifier="PID-JD-99",
        description="Missing person case description",
        department_id=demo_department.id,
        priority=CasePriority.HIGH.value,
        status=CaseStatus.ACTIVE.value,
        created_by=admin_user.id,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


@pytest.fixture
def sample_review_event(db_session, sample_case):
    svc = ReviewService()
    return svc.create_review_event(
        match_event_id="EVT-TEST-001",
        case_id=sample_case.id,
        case_number=sample_case.case_number,
        category="MISSING",
        similarity_score=0.892,
        candidate_ranking_score=0.915,
        query_quality_score=0.88,
        rank=1,
        decision_state="POSSIBLE_MATCH",
        camera_id=1,
        camera_location="Terminal 2 Concourse",
        track_id="TRK-9021",
        model_name="FaceNet-InceptionResnetV1",
        model_version="v2.1",
        db=db_session,
    )


# ---------------------------------------------------------------------------
# Unit Tests: Review Event Creation & Idempotency
# ---------------------------------------------------------------------------

def test_create_review_event(db_session, sample_case):
    svc = ReviewService()
    event = svc.create_review_event(
        match_event_id="EVT-UNIQ-100",
        case_id=sample_case.id,
        case_number=sample_case.case_number,
        category="MISSING",
        similarity_score=0.825,
        candidate_ranking_score=0.850,
        query_quality_score=0.80,
        rank=1,
        decision_state="POSSIBLE_MATCH",
        camera_id=2,
        camera_location="Gate 4",
        track_id="TRK-100",
        model_name="FaceNet",
        model_version="v2",
        db=db_session,
    )

    assert event.id is not None
    assert event.match_event_id == "EVT-UNIQ-100"
    assert event.status == ReviewStatus.PENDING_REVIEW.value
    assert event.similarity_score == 0.825
    assert event.assigned_to is None
    assert event.decision is None
    assert not event.module9_notified


def test_create_review_event_idempotency(db_session, sample_case):
    svc = ReviewService()
    evt1 = svc.create_review_event(
        match_event_id="EVT-DUP-001",
        case_id=sample_case.id,
        case_number=sample_case.case_number,
        category="MISSING",
        similarity_score=0.85,
        candidate_ranking_score=0.87,
        query_quality_score=0.81,
        rank=1,
        decision_state="POSSIBLE_MATCH",
        camera_id=1,
        camera_location="North Exit",
        track_id="TRK-1",
        model_name="FaceNet",
        model_version="v2",
        db=db_session,
    )

    evt2 = svc.create_review_event(
        match_event_id="EVT-DUP-001",
        case_id=sample_case.id,
        case_number=sample_case.case_number,
        category="MISSING",
        similarity_score=0.85,
        candidate_ranking_score=0.87,
        query_quality_score=0.81,
        rank=1,
        decision_state="POSSIBLE_MATCH",
        camera_id=1,
        camera_location="North Exit",
        track_id="TRK-1",
        model_name="FaceNet",
        model_version="v2",
        db=db_session,
    )

    assert evt1.id == evt2.id


# ---------------------------------------------------------------------------
# Unit Tests: Querying & Filtering
# ---------------------------------------------------------------------------

def test_list_events_and_filtering(db_session, sample_case, examiner_user):
    svc = ReviewService()
    # Create missing event
    e1 = svc.create_review_event(
        match_event_id="EVT-L1",
        case_id=sample_case.id,
        case_number=sample_case.case_number,
        category="MISSING",
        similarity_score=0.88,
        candidate_ranking_score=0.90,
        query_quality_score=0.85,
        rank=1,
        decision_state="POSSIBLE_MATCH",
        camera_id=1,
        camera_location="Loc A",
        track_id="T1",
        model_name="FaceNet",
        model_version="v1",
        db=db_session,
    )
    # Create wanted event
    e2 = svc.create_review_event(
        match_event_id="EVT-L2",
        case_id=sample_case.id,
        case_number=sample_case.case_number,
        category="WANTED",
        similarity_score=0.92,
        candidate_ranking_score=0.94,
        query_quality_score=0.90,
        rank=1,
        decision_state="HIGH_PRIORITY_REVIEW",
        camera_id=2,
        camera_location="Loc B",
        track_id="T2",
        model_name="FaceNet",
        model_version="v1",
        db=db_session,
    )

    # Filter by category
    missing_events = svc.list_events(db=db_session, category="MISSING")
    assert any(e.id == e1.id for e in missing_events)
    assert not any(e.id == e2.id for e in missing_events)

    wanted_events = svc.list_events(db=db_session, category="WANTED")
    assert any(e.id == e2.id for e in wanted_events)
    assert not any(e.id == e1.id for e in wanted_events)

    # Filter by status
    pending_events = svc.list_events(db=db_session, status="PENDING_REVIEW")
    assert len(pending_events) >= 2


def test_get_event_by_id_and_match_id(db_session, sample_review_event):
    svc = ReviewService()
    by_id = svc.get_event(sample_review_event.id, db_session)
    assert by_id is not None
    assert by_id.match_event_id == sample_review_event.match_event_id

    by_match = svc.get_event_by_match_id(sample_review_event.match_event_id, db_session)
    assert by_match is not None
    assert by_match.id == sample_review_event.id


# ---------------------------------------------------------------------------
# Unit Tests: Review State Transitions & Lifecycle Guards
# ---------------------------------------------------------------------------

def test_start_review_transitions_to_under_review(db_session, sample_review_event, examiner_user):
    svc = ReviewService()
    req = StartReviewRequest(notes="Starting manual video verification")
    updated = svc.start_review(
        review_event_id=sample_review_event.id,
        examiner=examiner_user,
        payload=req,
        db=db_session,
        ip_address="192.168.1.50",
    )

    assert updated.status == ReviewStatus.UNDER_REVIEW.value
    assert updated.assigned_to == examiner_user.id
    assert updated.review_started_at is not None

    # Check audit log
    history = svc.get_history(sample_review_event.id, db_session)
    assert len(history.entries) == 1
    entry = history.entries[0]
    assert entry.action == "START_REVIEW"
    assert entry.actor_id == examiner_user.id
    assert entry.actor_username == examiner_user.username
    assert entry.previous_status == ReviewStatus.PENDING_REVIEW.value
    assert entry.new_status == ReviewStatus.UNDER_REVIEW.value
    assert entry.notes == "Starting manual video verification"
    assert entry.ip_address == "192.168.1.50"


def test_invalid_transition_directly_to_decision_fails(db_session, sample_review_event, examiner_user):
    svc = ReviewService()
    dec_req = ReviewDecisionRequest(
        decision=ReviewDecision.CONFIRM_FOR_ACTION,
        notes="Attempting direct decision without starting review",
    )
    # Event is still PENDING_REVIEW; cannot jump straight to CONFIRM_FOR_ACTION
    with pytest.raises(HTTPException) as exc_info:
        svc.submit_decision(
            review_event_id=sample_review_event.id,
            examiner=examiner_user,
            payload=dec_req,
            db=db_session,
        )
    assert exc_info.value.status_code == 409
    assert "Invalid status transition" in exc_info.value.detail


def test_submit_decision_confirm_for_action(db_session, sample_review_event, examiner_user):
    svc = ReviewService()
    # 1. Start review
    svc.start_review(
        review_event_id=sample_review_event.id,
        examiner=examiner_user,
        payload=StartReviewRequest(notes="Starting review"),
        db=db_session,
    )

    # 2. Submit CONFIRM_FOR_ACTION
    dec_req = ReviewDecisionRequest(
        decision=ReviewDecision.CONFIRM_FOR_ACTION,
        notes="Subject facial features align closely with missing person gallery; dispatching team.",
    )
    updated, module9_payload = svc.submit_decision(
        review_event_id=sample_review_event.id,
        examiner=examiner_user,
        payload=dec_req,
        db=db_session,
        ip_address="10.0.0.1",
    )

    assert updated.status == ReviewStatus.CONFIRMED_FOR_ACTION.value
    assert updated.decision == ReviewDecision.CONFIRM_FOR_ACTION.value
    assert updated.decision_at is not None
    assert bool(updated.module9_notified) is True

    # Validate Module 9 payload
    assert module9_payload is not None
    assert module9_payload.review_event_id == sample_review_event.id
    assert module9_payload.examiner_confirmed_for_action is True
    assert module9_payload.examiner_user_id == examiner_user.id
    assert "algorithmic similarity signal" in module9_payload.similarity_score_disclaimer

    # Audit history should contain 2 entries
    history = svc.get_history(sample_review_event.id, db_session)
    assert len(history.entries) == 2
    assert history.entries[1].action == ReviewDecision.CONFIRM_FOR_ACTION.value


def test_submit_decision_rejected(db_session, sample_review_event, examiner_user):
    svc = ReviewService()
    svc.start_review(
        review_event_id=sample_review_event.id,
        examiner=examiner_user,
        payload=StartReviewRequest(),
        db=db_session,
    )

    dec_req = ReviewDecisionRequest(
        decision=ReviewDecision.REJECTED,
        notes="False positive: ear shape and eye spacing mismatch upon examiner inspection.",
    )
    updated, module9_payload = svc.submit_decision(
        review_event_id=sample_review_event.id,
        examiner=examiner_user,
        payload=dec_req,
        db=db_session,
    )

    assert updated.status == ReviewStatus.REJECTED.value
    assert updated.decision == ReviewDecision.REJECTED.value
    assert module9_payload is None  # No notification dispatched for rejection


def test_submit_decision_need_more_evidence_and_resume(db_session, sample_review_event, examiner_user):
    svc = ReviewService()
    svc.start_review(
        review_event_id=sample_review_event.id,
        examiner=examiner_user,
        payload=StartReviewRequest(),
        db=db_session,
    )

    dec_req = ReviewDecisionRequest(
        decision=ReviewDecision.NEED_MORE_EVIDENCE,
        notes="Resolution on CCTV camera 1 is suboptimal; request higher-resolution still.",
    )
    updated, module9_payload = svc.submit_decision(
        review_event_id=sample_review_event.id,
        examiner=examiner_user,
        payload=dec_req,
        db=db_session,
    )

    assert updated.status == ReviewStatus.NEED_MORE_EVIDENCE.value
    assert module9_payload is None

    # Should be allowed to resume review from NEED_MORE_EVIDENCE
    resumed = svc.start_review(
        review_event_id=sample_review_event.id,
        examiner=examiner_user,
        payload=StartReviewRequest(notes="Additional evidence received; resuming review."),
        db=db_session,
    )
    assert resumed.status == ReviewStatus.UNDER_REVIEW.value


def test_terminal_states_prevent_further_transitions(db_session, sample_review_event, examiner_user):
    svc = ReviewService()
    svc.start_review(
        review_event_id=sample_review_event.id,
        examiner=examiner_user,
        payload=StartReviewRequest(),
        db=db_session,
    )
    svc.submit_decision(
        review_event_id=sample_review_event.id,
        examiner=examiner_user,
        payload=ReviewDecisionRequest(
            decision=ReviewDecision.CONFIRM_FOR_ACTION,
            notes="Action approved",
        ),
        db=db_session,
    )

    # Attempting to start review or change decision on terminal state must raise 409 Conflict
    with pytest.raises(HTTPException) as exc_start:
        svc.start_review(
            review_event_id=sample_review_event.id,
            examiner=examiner_user,
            payload=StartReviewRequest(),
            db=db_session,
        )
    assert exc_start.value.status_code == 409

    with pytest.raises(HTTPException) as exc_dec:
        svc.submit_decision(
            review_event_id=sample_review_event.id,
            examiner=examiner_user,
            payload=ReviewDecisionRequest(
                decision=ReviewDecision.REJECTED,
                notes="Attempting post-confirmation rejection",
            ),
            db=db_session,
        )
    assert exc_dec.value.status_code == 409


# ---------------------------------------------------------------------------
# Unit Tests: Evidence Requests & Examiner Reassignment
# ---------------------------------------------------------------------------

def test_request_more_evidence_endpoint_method(db_session, sample_review_event, examiner_user):
    svc = ReviewService()
    svc.start_review(
        review_event_id=sample_review_event.id,
        examiner=examiner_user,
        payload=StartReviewRequest(),
        db=db_session,
    )

    req = EvidenceRequestRequest(notes="Need angle from adjacent overhead camera.")
    updated = svc.request_evidence(
        review_event_id=sample_review_event.id,
        examiner=examiner_user,
        payload=req,
        db=db_session,
    )
    assert updated.status == ReviewStatus.NEED_MORE_EVIDENCE.value
    assert updated.evidence_request_notes == "Need angle from adjacent overhead camera."


def test_assign_review_examiner(db_session, sample_review_event, admin_user, second_examiner):
    svc = ReviewService()
    assign_req = AssignRequest(examiner_user_id=second_examiner.id, notes="Assigned to lead investigator")
    updated = svc.assign_event(
        review_event_id=sample_review_event.id,
        assigner=admin_user,
        payload=assign_req,
        db=db_session,
    )

    assert updated.assigned_to == second_examiner.id
    history = svc.get_history(sample_review_event.id, db_session)
    assert any(e.action == "ASSIGN" and e.notes == "Assigned to lead investigator" for e in history.entries)


# ---------------------------------------------------------------------------
# Unit Tests: Investigation Task Management
# ---------------------------------------------------------------------------

def test_cannot_create_task_before_confirmation(db_session, sample_review_event, examiner_user):
    svc = ReviewService()
    # Event is PENDING_REVIEW; creating investigation task should be blocked
    task_payload = InvestigationTaskCreate(
        review_event_id=sample_review_event.id,
        title="Field verification check",
        description="Check bus terminal area",
        priority=TaskPriority.HIGH,
    )
    with pytest.raises(HTTPException) as exc_info:
        svc.create_task(payload=task_payload, creator=examiner_user, db=db_session)
    assert exc_info.value.status_code == 409
    assert "CONFIRM_FOR_ACTION" in exc_info.value.detail


def test_investigation_task_lifecycle(db_session, sample_review_event, examiner_user, second_examiner):
    svc = ReviewService()
    # 1. Bring event to CONFIRMED_FOR_ACTION
    svc.start_review(
        review_event_id=sample_review_event.id,
        examiner=examiner_user,
        payload=StartReviewRequest(),
        db=db_session,
    )
    svc.submit_decision(
        review_event_id=sample_review_event.id,
        examiner=examiner_user,
        payload=ReviewDecisionRequest(
            decision=ReviewDecision.CONFIRM_FOR_ACTION,
            notes="Confirmed for investigation team",
        ),
        db=db_session,
    )

    # 2. Create task
    task_payload = InvestigationTaskCreate(
        review_event_id=sample_review_event.id,
        title="Deploy Field Team to Platform 3",
        description="Locate person matching query candidate at Platform 3",
        priority=TaskPriority.URGENT,
        assigned_to=second_examiner.id,
    )
    task = svc.create_task(payload=task_payload, creator=examiner_user, db=db_session)

    assert task.id is not None
    assert task.status == TaskStatus.OPEN.value
    assert task.priority == TaskPriority.URGENT.value
    assert task.assigned_to == second_examiner.id
    assert task.created_by == examiner_user.id

    # 3. List tasks
    tasks = svc.list_tasks(db=db_session, case_id=sample_review_event.case_id)
    assert len(tasks) == 1
    assert tasks[0].id == task.id

    # 4. Update task to IN_PROGRESS
    updated_task = svc.update_task(
        task_id=task.id,
        payload=TaskUpdateRequest(status=TaskStatus.IN_PROGRESS),
        actor=second_examiner,
        db=db_session,
    )
    assert updated_task.status == TaskStatus.IN_PROGRESS.value

    # 5. Complete task
    completed_task = svc.update_task(
        task_id=task.id,
        payload=TaskUpdateRequest(
            status=TaskStatus.COMPLETED,
            resolution_notes="Officer conducted on-site field inquiry. Subject verified safely.",
        ),
        actor=second_examiner,
        db=db_session,
    )
    assert completed_task.status == TaskStatus.COMPLETED.value
    assert completed_task.completed_at is not None
    assert "verified safely" in completed_task.resolution_notes


# ---------------------------------------------------------------------------
# Unit Tests: Dashboard Analytics & AI Safety Invariants
# ---------------------------------------------------------------------------

def test_get_dashboard_stats(db_session, sample_case, examiner_user):
    svc = ReviewService()
    # Initially create 1 missing event
    e_missing = svc.create_review_event(
        match_event_id="EVT-STAT-1",
        case_id=sample_case.id,
        case_number=sample_case.case_number,
        category="MISSING",
        similarity_score=0.88,
        candidate_ranking_score=0.90,
        query_quality_score=0.85,
        rank=1,
        decision_state="POSSIBLE_MATCH",
        camera_id=1,
        camera_location="Loc",
        track_id="T1",
        model_name="FaceNet",
        model_version="v1",
        db=db_session,
    )
    # Create 1 wanted event
    e_wanted = svc.create_review_event(
        match_event_id="EVT-STAT-2",
        case_id=sample_case.id,
        case_number=sample_case.case_number,
        category="WANTED",
        similarity_score=0.93,
        candidate_ranking_score=0.95,
        query_quality_score=0.90,
        rank=1,
        decision_state="HIGH_PRIORITY_REVIEW",
        camera_id=2,
        camera_location="Loc",
        track_id="T2",
        model_name="FaceNet",
        model_version="v1",
        db=db_session,
    )

    stats = svc.get_dashboard_stats(db=db_session)
    assert stats.total_events == 2
    assert stats.pending_review == 2
    assert stats.missing_category_count == 1
    assert stats.wanted_category_count == 1
    assert stats.open_tasks == 0
    assert "algorithmic similarity signal" in stats.similarity_score_disclaimer

    # Confirm one event and check updated stats
    svc.start_review(
        review_event_id=e_missing.id,
        examiner=examiner_user,
        payload=StartReviewRequest(),
        db=db_session,
    )
    svc.submit_decision(
        review_event_id=e_missing.id,
        examiner=examiner_user,
        payload=ReviewDecisionRequest(
            decision=ReviewDecision.CONFIRM_FOR_ACTION,
            notes="Proceed with action",
        ),
        db=db_session,
    )

    updated_stats = svc.get_dashboard_stats(db=db_session)
    assert updated_stats.total_events == 2
    assert updated_stats.pending_review == 1
    assert updated_stats.confirmed_for_action == 1


def test_ai_safety_invariants_enums_and_disclaimers():
    # 1. Verify that ReviewDecision NEVER contains autonomous identity affirmation terms
    forbidden_terms = [
        "IDENTITY_CONFIRMED",
        "PERSON_CONFIRMED",
        "AUTOMATIC_MATCH",
        "CONFIRMED_IDENTITY",
    ]
    for decision in ReviewDecision:
        for term in forbidden_terms:
            assert term != decision.value, f"Forbidden term {term} found in ReviewDecision enum!"

    # 2. Verify that ReviewStatus NEVER contains identity confirmation terms
    for status_val in ReviewStatus:
        for term in forbidden_terms:
            assert term != status_val.value, f"Forbidden term {term} found in ReviewStatus enum!"

    # 3. Mandatory disclaimer text must be present
    assert "algorithmic similarity signal" in SIMILARITY_DISCLAIMER
    assert "not independently establish identity" in SIMILARITY_DISCLAIMER
