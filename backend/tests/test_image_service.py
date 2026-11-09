from io import BytesIO
from pathlib import Path
import sys
from pathlib import Path as _Path

# Ensure backend package is importable when running this test file directly
ROOT = _Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.case import Case
from app.models.department import Department
from app.models.user import User, UserRole
from app.services.image_service import ImageService
from app.utils.storage_manager import remove_stored_file
from PIL import Image


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


class DummyUpload:
    def __init__(self, content: bytes, filename: str, content_type: str):
        self.file = BytesIO(content)
        self.filename = filename
        self.content_type = content_type


def make_test_jpeg(width=10, height=10, color=(255, 0, 0)):
    buf = BytesIO()
    image = Image.new("RGB", (width, height), color)
    image.save(buf, format="JPEG")
    return buf.getvalue()


def test_upload_assigns_to_missing_dataset(tmp_path):
    db = setup_in_memory_db()
    dept, admin, police, other = create_demo_user_and_department(db)

    case = Case(case_number="MP-2026-0001", category="MISSING", title="T", person_identifier="p", description="d", department_id=dept.id, created_by=police.id, status="ACTIVE", priority="MEDIUM")
    db.add(case)
    db.commit()
    db.refresh(case)

    content = make_test_jpeg()
    upload = DummyUpload(content, "photo.jpg", "image/jpeg")

    images = ImageService.upload(db, police, case, [upload])
    assert len(images) == 1
    img = images[0]
    # verify database fields
    assert img.case_id == case.id
    assert img.file_type == "image/jpeg"
    assert img.file_size == len(content)
    # file should exist
    path = Path(img.file_path)
    assert path.is_file()

    # cleanup
    remove_stored_file(str(path))


def test_upload_assigns_to_wanted_dataset_and_dataset_separation(tmp_path):
    db = setup_in_memory_db()
    dept, admin, police, other = create_demo_user_and_department(db)

    case = Case(case_number="WP-2026-0001", category="WANTED", title="T", person_identifier="p", description="d", department_id=dept.id, created_by=police.id, status="ACTIVE", priority="MEDIUM")
    db.add(case)
    db.commit()
    db.refresh(case)

    content = make_test_jpeg()
    upload = DummyUpload(content, "photo.jpg", "image/jpeg")

    images = ImageService.upload(db, police, case, [upload])
    assert len(images) == 1
    img = images[0]
    assert "wanted_persons" in img.file_path
    assert img.case_id == case.id

    # cleanup
    remove_stored_file(img.file_path)


def test_validation_rejects_bad_mime(tmp_path):
    db = setup_in_memory_db()
    dept, admin, police, other = create_demo_user_and_department(db)

    case = Case(case_number="MP-2026-0002", category="MISSING", title="T", person_identifier="p", description="d", department_id=dept.id, created_by=police.id, status="ACTIVE", priority="MEDIUM")
    db.add(case)
    db.commit()
    db.refresh(case)

    content = b"not-an-image"
    upload = DummyUpload(content, "bad.txt", "text/plain")

    with pytest.raises(ValueError):
        ImageService.upload(db, police, case, [upload])


def test_unauthorized_user_cannot_upload(tmp_path):
    db = setup_in_memory_db()
    dept, admin, police, other = create_demo_user_and_department(db)

    # case belongs to dept, created by police
    case = Case(case_number="MP-2026-0003", category="MISSING", title="T", person_identifier="p", description="d", department_id=dept.id, created_by=police.id, status="ACTIVE", priority="MEDIUM")
    db.add(case)
    db.commit()
    db.refresh(case)

    # 'other' has no department and did not create case
    content = make_test_jpeg()
    upload = DummyUpload(content, "photo.jpg", "image/jpeg")

    # In the real API the case access is validated before calling upload. Ensure access check blocks the operation:
    with pytest.raises(PermissionError):
        ImageService.get_case(db, other, case.id)
