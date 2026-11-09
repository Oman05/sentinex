"""
Module 10 Unit & Integration Tests – Evidence Lifecycle, Immutability & Provenance
===================================================================================
Tests Section 1, 4, 5, 7, 8, 10, 11, 24:
- Evidence record creation (metadata and file attachment).
- Finalization immutability (finalized evidence cannot be modified; requires versioning).
- Versioning chain (original record preserved, derived version created).
- CCTV clip evidence creation with configurable time window (±10s).
- Evidence relationship mapping ("Why does this evidence exist, and which event generated it?").
- Archival workflow preserving discoverability.
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.main import app
from app.models.case import Case, CaseCategory, CasePriority, CaseStatus
from app.models.department import Department
from app.models.evidence import (
    EvidenceClassification,
    EvidenceItemDB,
    EvidenceStatus,
    EvidenceType,
    IntegrityStatus,
)
from app.models.user import User, UserRole
from app.schemas.evidence import (
    CCTVClipCreateRequest,
    EvidenceCreateRequest,
    EvidenceFinalizeRequest,
    EvidenceRelationshipCreate,
    EvidenceUpdateRequest,
)
from app.services.evidence_service import evidence_service


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_setup(db_session: Session):
    dept = Department(
        department_name="Central Police HQ",
        department_code="HQ-01",
        department_type="POLICE",
        is_active=True,
    )
    db_session.add(dept)
    db_session.flush()

    admin = User(
        username="admin_officer",
        email="admin@sentinex.gov",
        password_hash="hashed_pw",
        role=UserRole.ADMIN.value,
        department_id=dept.id,
        is_active=True,
    )
    officer = User(
        username="officer_smith",
        email="smith@sentinex.gov",
        password_hash="hashed_pw",
        role=UserRole.POLICE.value,
        department_id=dept.id,
        is_active=True,
    )
    db_session.add_all([admin, officer])
    db_session.flush()

    case = Case(
        case_number="WP-2026-0001",
        title="Wanted Person Alpha",
        category=CaseCategory.WANTED.value,
        priority=CasePriority.HIGH.value,
        status=CaseStatus.ACTIVE.value,
        person_identifier="SUSPECT-001",
        description="Test case for evidence management module.",
        department_id=dept.id,
        created_by=admin.id,
    )
    db_session.add(case)
    db_session.commit()

    admin_token = create_access_token({"sub": admin.username})
    officer_token = create_access_token({"sub": officer.username})

    return {
        "admin": admin,
        "officer": officer,
        "dept": dept,
        "case": case,
        "admin_token": admin_token,
        "officer_token": officer_token,
    }


def test_create_and_retrieve_evidence_metadata(db_session: Session, test_setup: dict):
    officer = test_setup["officer"]
    case = test_setup["case"]

    req = EvidenceCreateRequest(
        evidence_type=EvidenceType.CCTV_FRAME.value,
        case_id=case.id,
        camera_id=4,
        classification=EvidenceClassification.RESTRICTED.value,
        description="Relevant CCTV frame from North Terminal",
        track_id="TRACK-00127",
    )

    # Valid PNG image bytes (with proper magic bytes \x89PNG\r\n\x1a\n)
    valid_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"

    res = evidence_service.create_evidence(
        db_session,
        req,
        officer,
        file_content=valid_png,
        original_filename="frame_001.png",
        declared_mime="image/png",
    )

    assert res.evidence_id.startswith("EVD-")
    assert res.status == EvidenceStatus.AVAILABLE.value
    assert res.integrity_status == IntegrityStatus.VERIFIED.value
    assert res.file_hash is not None
    assert res.version_number == 1

    # Retrieve
    retrieved = evidence_service.get_evidence(db_session, res.evidence_id, officer)
    assert retrieved.evidence_id == res.evidence_id
    assert retrieved.case_id == case.id


def test_immutability_finalized_evidence_cannot_be_modified(db_session: Session, test_setup: dict):
    officer = test_setup["officer"]
    case = test_setup["case"]

    req = EvidenceCreateRequest(
        evidence_type=EvidenceType.REVIEW_RECORD.value,
        case_id=case.id,
        classification=EvidenceClassification.RESTRICTED.value,
        description="Initial human review note",
    )
    res = evidence_service.create_evidence(db_session, req, officer)

    # Update while available is permitted
    updated = evidence_service.update_evidence(
        db_session,
        res.evidence_id,
        EvidenceUpdateRequest(description="Updated review note before finalization"),
        officer,
    )
    assert updated.description == "Updated review note before finalization"

    # Finalize the evidence item
    finalized = evidence_service.finalize_evidence(
        db_session,
        res.evidence_id,
        officer,
        EvidenceFinalizeRequest(reason="Official supervisory approval signed"),
    )
    assert finalized.status == EvidenceStatus.FINALIZED.value

    # Subsequent update MUST be rejected with error
    with pytest.raises(ValueError, match="FINALIZED and immutable"):
        evidence_service.update_evidence(
            db_session,
            res.evidence_id,
            EvidenceUpdateRequest(description="Attempted silent modification"),
            officer,
        )


def test_versioning_preserves_original_and_links_derived(db_session: Session, test_setup: dict):
    officer = test_setup["officer"]
    case = test_setup["case"]

    # 1. Original evidence
    valid_jpg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00"
    v1_req = EvidenceCreateRequest(
        evidence_type=EvidenceType.CCTV_FRAME.value,
        case_id=case.id,
        description="Original CCTV surveillance frame",
    )
    v1 = evidence_service.create_evidence(
        db_session, v1_req, officer, file_content=valid_jpg, original_filename="original.jpg", declared_mime="image/jpeg"
    )
    assert v1.version_number == 1

    # 2. Finalize original
    evidence_service.finalize_evidence(
        db_session, v1.evidence_id, officer, EvidenceFinalizeRequest(reason="Lock original baseline")
    )

    # 3. Create derived version 2 (e.g. face crop / enhanced image)
    crop_jpg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x01"
    v2 = evidence_service.create_evidence_version(
        db_session,
        v1.evidence_id,
        officer,
        file_content=crop_jpg,
        original_filename="crop_v2.jpg",
        declared_mime="image/jpeg",
        version_notes="Enhanced face crop bounding box extracted from v1",
    )

    assert v2.version_number == 2
    assert v2.parent_evidence_id == v1.id
    assert v2.evidence_id != v1.evidence_id

    # Verify original v1 record is unchanged and finalized
    orig_check = evidence_service.get_evidence(db_session, v1.evidence_id, officer)
    assert orig_check.status == EvidenceStatus.FINALIZED.value
    assert orig_check.version_number == 1


def test_create_cctv_clip_evidence_time_window(db_session: Session, test_setup: dict):
    officer = test_setup["officer"]
    case = test_setup["case"]

    event_time = datetime(2026, 9, 27, 10, 32, 41)
    req = CCTVClipCreateRequest(
        case_id=case.id,
        camera_id=4,
        stream_id="STREAM-CCTV-004",
        event_time=event_time,
        window_seconds_before=10.0,
        window_seconds_after=10.0,
        match_event_id=101,
        clip_generation_method="AUTO_WINDOW_±10s",
        description="Authorized CCTV clip covering 10:32:31 -> 10:32:51",
    )

    valid_mp4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom\x00\x00\x00\x08free"

    clip = evidence_service.create_cctv_clip_evidence(
        db_session,
        req,
        officer,
        file_content=valid_mp4,
        original_filename="clip_event_101.mp4",
        declared_mime="video/mp4",
    )

    assert clip.evidence_type == EvidenceType.CCTV_CLIP.value
    assert clip.camera_id == 4
    assert clip.clip_start_time == datetime(2026, 9, 27, 10, 32, 31)
    assert clip.clip_end_time == datetime(2026, 9, 27, 10, 32, 51)
    assert clip.clip_duration_seconds == 20.0
    assert clip.clip_generation_method == "AUTO_WINDOW_±10s"


def test_evidence_relationship_and_provenance_trace(db_session: Session, test_setup: dict):
    officer = test_setup["officer"]
    case = test_setup["case"]

    # Frame evidence
    frame = evidence_service.create_evidence(
        db_session,
        EvidenceCreateRequest(
            evidence_type=EvidenceType.CCTV_FRAME.value,
            case_id=case.id,
            camera_id=4,
            track_id="TRACK-00127",
            match_event_id=91,
            description="Surveillance CCTV frame",
        ),
        officer,
    )

    # Face crop derived evidence
    crop = evidence_service.create_evidence(
        db_session,
        EvidenceCreateRequest(
            evidence_type=EvidenceType.FACE_CROP.value,
            case_id=case.id,
            parent_evidence_id=frame.id,
            description="Extracted face crop",
        ),
        officer,
    )

    # Link in relationship
    rel = evidence_service.create_evidence_relationship(
        db_session,
        EvidenceRelationshipCreate(
            source_evidence_id=frame.id,
            target_evidence_id=crop.id,
            relationship_type="DERIVED_FACE_CROP",
            description="AI detection extracted crop from frame",
        ),
        officer,
    )
    assert rel.relationship_type == "DERIVED_FACE_CROP"

    # Query relationships
    rels = evidence_service.get_evidence_relationships(db_session, frame.evidence_id, officer)
    assert len(rels) >= 1

    # Provenance trace (Section 5 & 40)
    prov = evidence_service.get_evidence_provenance(db_session, frame.evidence_id, officer)
    assert prov.evidence_id == frame.evidence_id
    stages = [s.stage for s in prov.chain_of_events]
    assert "CASE" in stages
    assert "CCTV_STREAM" in stages
    assert "VIDEO_OBSERVATION" in stages
    assert "EVIDENCE" in stages


def test_archive_evidence(db_session: Session, test_setup: dict):
    officer = test_setup["officer"]
    case = test_setup["case"]

    item = evidence_service.create_evidence(
        db_session,
        EvidenceCreateRequest(
            evidence_type=EvidenceType.CASE_DOCUMENT.value,
            case_id=case.id,
            description="Initial case docket",
        ),
        officer,
    )
    archived = evidence_service.archive_evidence(
        db_session, item.evidence_id, officer, "Case WP-2026-0001 investigations concluded"
    )
    assert archived.status == EvidenceStatus.ARCHIVED.value
