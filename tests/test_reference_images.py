import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.case import Case, CaseCategory, CasePriority, CaseStatus
from app.models.department import Department
from app.models.reference_image import ReferenceImage
from app.models.user import User, UserRole
from app.services.auth_service import create_access_token, hash_password
from app.services.image_service import ImageService
from app.storage.file_manager import default_file_manager


def create_test_image_bytes(format="JPEG", size=(64, 64), color=(255, 0, 0)) -> bytes:
    """Generate in-memory test image bytes."""
    buf = io.BytesIO()
    img = Image.new("RGB", size, color)
    img.save(buf, format=format)
    return buf.getvalue()


@pytest.fixture
def image_test_env(tmp_path):
    """Set up an isolated SQLite database and test dataset directory for tests."""
    db_path = tmp_path / "sentinex_img_test.db"
    settings.DATABASE_URL = f"sqlite:///{db_path}"
    test_datasets_root = tmp_path / "test_datasets"
    test_datasets_root.mkdir(parents=True, exist_ok=True)
    settings.DATASET_ROOT = str(test_datasets_root)

    # Re-initialize local backend with tmp path
    default_file_manager.backend.root_dir = test_datasets_root.resolve()

    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Seed departments and users
    db = TestingSession()
    dept_alpha = Department(department_name="Alpha Precinct", department_type="POLICE", location="Downtown")
    dept_beta = Department(department_name="Beta Precinct", department_type="POLICE", location="Uptown")
    db.add_all([dept_alpha, dept_beta])
    db.commit()
    db.refresh(dept_alpha)
    db.refresh(dept_beta)

    admin_user = User(
        username="admin_officer",
        email="admin@sentinex.gov",
        password_hash=hash_password("Secr3tP@ss!"),
        role=UserRole.ADMIN.value,
        department_id=None,
        is_active=True,
    )
    alpha_officer = User(
        username="alpha_detective",
        email="alpha@sentinex.gov",
        password_hash=hash_password("Secr3tP@ss!"),
        role=UserRole.POLICE.value,
        department_id=dept_alpha.id,
        is_active=True,
    )
    beta_officer = User(
        username="beta_detective",
        email="beta@sentinex.gov",
        password_hash=hash_password("Secr3tP@ss!"),
        role=UserRole.POLICE.value,
        department_id=dept_beta.id,
        is_active=True,
    )
    db.add_all([admin_user, alpha_officer, beta_officer])
    db.commit()
    db.refresh(admin_user)
    db.refresh(alpha_officer)
    db.refresh(beta_officer)

    # Seed cases
    missing_case = Case(
        case_number="MP-2026-0101",
        category=CaseCategory.MISSING.value,
        title="Missing Person Alpha Case",
        person_identifier="ID-MP-101",
        description="Missing juvenile from downtown area.",
        department_id=dept_alpha.id,
        created_by=alpha_officer.id,
        status=CaseStatus.ACTIVE.value,
        priority=CasePriority.HIGH.value,
        is_active=True,
    )
    wanted_case = Case(
        case_number="WP-2026-0202",
        category=CaseCategory.WANTED.value,
        title="Wanted Suspect Beta Case",
        person_identifier="ID-WP-202",
        description="Wanted suspect in grand theft investigation.",
        department_id=dept_beta.id,
        created_by=beta_officer.id,
        status=CaseStatus.ACTIVE.value,
        priority=CasePriority.CRITICAL.value,
        is_active=True,
    )
    db.add_all([missing_case, wanted_case])
    db.commit()
    db.refresh(missing_case)
    db.refresh(wanted_case)

    # Extract required fields before closing session to prevent DetachedInstanceError
    admin_id = admin_user.id
    admin_name = admin_user.username
    admin_role = admin_user.role

    alpha_id = alpha_officer.id
    alpha_name = alpha_officer.username
    alpha_role = alpha_officer.role

    beta_id = beta_officer.id
    beta_name = beta_officer.username
    beta_role = beta_officer.role

    missing_case_id = missing_case.id
    missing_case_number = missing_case.case_number
    wanted_case_id = wanted_case.id
    wanted_case_number = wanted_case.case_number

    db.close()

    admin_token = create_access_token({"sub": admin_name, "user_id": admin_id, "role": admin_role})
    alpha_token = create_access_token({"sub": alpha_name, "user_id": alpha_id, "role": alpha_role})
    beta_token = create_access_token({"sub": beta_name, "user_id": beta_id, "role": beta_role})

    with TestClient(app) as client:
        yield {
            "client": client,
            "engine": engine,
            "Session": TestingSession,
            "admin_token": admin_token,
            "alpha_token": alpha_token,
            "beta_token": beta_token,
            "missing_case_id": missing_case_id,
            "missing_case_number": missing_case_number,
            "wanted_case_id": wanted_case_id,
            "wanted_case_number": wanted_case_number,
            "datasets_root": test_datasets_root,
        }

    app.dependency_overrides.clear()
    engine.dispose()


def test_upload_missing_dataset_routing_and_metadata(image_test_env):
    """Verify multiple image uploads route to missing_persons and extract metadata."""
    client = image_test_env["client"]
    token = image_test_env["alpha_token"]
    case_id = image_test_env["missing_case_id"]

    img1 = create_test_image_bytes("JPEG", size=(100, 150))
    img2 = create_test_image_bytes("PNG", size=(200, 250))

    files = [
        ("files", ("front_face.jpg", io.BytesIO(img1), "image/jpeg")),
        ("files", ("side_profile.png", io.BytesIO(img2), "image/png")),
    ]

    response = client.post(
        f"/cases/{case_id}/images",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )
    assert response.status_code == 201, response.text
    records = response.json()
    assert len(records) == 2

    # Check first record metadata and storage
    rec1 = records[0]
    assert rec1["case_id"] == case_id
    assert rec1["mime_type"] == "image/jpeg"
    assert rec1["file_type"] == "image/jpeg"
    assert rec1["image_width"] == 100
    assert rec1["image_height"] == 150
    assert rec1["is_primary"] is True  # First active image becomes primary
    assert rec1["is_active"] is True
    assert rec1["storage_type"] == "LOCAL"
    assert "missing_persons" in rec1["file_path"]
    assert Path(rec1["file_path"]).exists()

    # Check second record
    rec2 = records[1]
    assert rec2["mime_type"] == "image/png"
    assert rec2["image_width"] == 200
    assert rec2["image_height"] == 250
    assert rec2["is_primary"] is False
    assert "missing_persons" in rec2["file_path"]
    assert Path(rec2["file_path"]).exists()


def test_upload_wanted_dataset_routing(image_test_env):
    """Verify uploads for WANTED category are routed into wanted_persons directory."""
    client = image_test_env["client"]
    token = image_test_env["beta_token"]
    case_id = image_test_env["wanted_case_id"]

    img = create_test_image_bytes("JPEG", size=(120, 120))
    files = [("files", ("suspect.jpg", io.BytesIO(img), "image/jpeg"))]

    response = client.post(
        f"/cases/{case_id}/images",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )
    assert response.status_code == 201
    record = response.json()[0]
    assert "wanted_persons" in record["file_path"]
    assert Path(record["file_path"]).exists()


def test_validation_rejects_unsupported_mimes_and_mismatches(image_test_env):
    """Verify unsupported MIME types and mismatching binary content are rejected."""
    client = image_test_env["client"]
    token = image_test_env["alpha_token"]
    case_id = image_test_env["missing_case_id"]

    # 1. Plain text / non-image
    res_text = client.post(
        f"/cases/{case_id}/images",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("document.txt", io.BytesIO(b"Hello world"), "text/plain"))],
    )
    assert res_text.status_code == 400
    assert "Unsupported image format" in res_text.json()["detail"]

    # 2. Fake image (content is text but mime is image/jpeg)
    res_fake = client.post(
        f"/cases/{case_id}/images",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("fake.jpg", io.BytesIO(b"corrupted-not-an-image"), "image/jpeg"))],
    )
    assert res_fake.status_code == 400
    assert "not a valid" in res_fake.json()["detail"].lower()

    # 3. MIME mismatch (actual PNG declared as image/jpeg)
    png_bytes = create_test_image_bytes("PNG")
    res_mismatch = client.post(
        f"/cases/{case_id}/images",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("mismatch.jpg", io.BytesIO(png_bytes), "image/jpeg"))],
    )
    assert res_mismatch.status_code == 400
    assert "does not match actual" in res_mismatch.json()["detail"]


def test_path_traversal_prevention_in_filename(image_test_env):
    """Verify directory traversal in filenames is neutralized."""
    client = image_test_env["client"]
    token = image_test_env["alpha_token"]
    case_id = image_test_env["missing_case_id"]
    case_number = image_test_env["missing_case_number"]

    img_bytes = create_test_image_bytes("JPEG")
    malicious_filename = "../../../../../etc/passwd.jpg"

    res = client.post(
        f"/cases/{case_id}/images",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", (malicious_filename, io.BytesIO(img_bytes), "image/jpeg"))],
    )
    assert res.status_code == 201
    record = res.json()[0]
    # Sanitized filename should not contain relative traversal paths
    assert ".." not in record["original_file_name"]
    assert record["original_file_name"] == "passwd.jpg"
    # Stored file must be located inside the safe case directory
    stored_path = Path(record["file_path"])
    assert stored_path.exists()
    assert stored_path.parent.name == case_number


def test_rbac_department_isolation_and_audit_log(image_test_env):
    """Verify unauthorized department users cannot access or upload images to other departments' cases."""
    client = image_test_env["client"]
    alpha_token = image_test_env["alpha_token"]
    wanted_case_id = image_test_env["wanted_case_id"]
    Session = image_test_env["Session"]

    img = create_test_image_bytes("JPEG")

    # Alpha detective attempts to upload to Beta precinct's wanted case -> 403 Forbidden
    unauth_upload = client.post(
        f"/cases/{wanted_case_id}/images",
        headers={"Authorization": f"Bearer {alpha_token}"},
        files=[("files", ("infiltrate.jpg", io.BytesIO(img), "image/jpeg"))],
    )
    assert unauth_upload.status_code == 403
    assert "do not have access" in unauth_upload.json()["detail"].lower()

    # Verify UNAUTHORIZED_ACCESS_ATTEMPT was logged in audit_logs table
    db = Session()
    audit_entry = (
        db.query(AuditLog)
        .filter(AuditLog.action == "UNAUTHORIZED_ACCESS_ATTEMPT")
        .order_by(AuditLog.timestamp.desc())
        .first()
    )
    assert audit_entry is not None
    assert audit_entry.resource_type == "REFERENCE_IMAGE"
    assert audit_entry.resource_id == wanted_case_id
    db.close()


def test_image_metadata_update_and_view(image_test_env):
    """Verify viewing image metadata and updating metadata (PUT /images/{id})."""
    client = image_test_env["client"]
    token = image_test_env["alpha_token"]
    case_id = image_test_env["missing_case_id"]

    img = create_test_image_bytes("JPEG")
    upload_res = client.post(
        f"/cases/{case_id}/images",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("cctv_crop.jpg", io.BytesIO(img), "image/jpeg"))],
    )
    image_id = upload_res.json()[0]["id"]

    # 1. Get image metadata (GET /images/{id})
    view_res = client.get(f"/images/{image_id}", headers={"Authorization": f"Bearer {token}"})
    assert view_res.status_code == 200
    assert view_res.json()["id"] == image_id

    # 2. Update metadata (PUT /images/{id})
    update_payload = {
        "description": "High resolution portrait photo taken in 2026",
        "tags": ["portrait", "outdoor", "clear_face"],
        "notes": "Verified by family member on 2026-09-05",
        "image_quality_status": "EXCELLENT",
    }
    update_res = client.put(
        f"/images/{image_id}",
        headers={"Authorization": f"Bearer {token}"},
        json=update_payload,
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["description"] == update_payload["description"]
    assert data["tags"] == update_payload["tags"]
    assert data["notes"] == update_payload["notes"]
    assert data["image_quality_status"] == "EXCELLENT"


def test_replace_image(image_test_env):
    """Verify replacing an image file removes the old file and updates the record."""
    client = image_test_env["client"]
    token = image_test_env["alpha_token"]
    case_id = image_test_env["missing_case_id"]

    # Upload original
    orig_bytes = create_test_image_bytes("JPEG", size=(50, 50))
    upload = client.post(
        f"/cases/{case_id}/images",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("orig.jpg", io.BytesIO(orig_bytes), "image/jpeg"))],
    ).json()[0]

    image_id = upload["id"]
    old_file_path = upload["file_path"]
    assert Path(old_file_path).exists()

    # Replace with higher resolution PNG
    replacement_bytes = create_test_image_bytes("PNG", size=(300, 300))
    replace_res = client.post(
        f"/images/{image_id}/replace",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("higher_quality.png", io.BytesIO(replacement_bytes), "image/png")},
    )
    assert replace_res.status_code == 200
    replaced_data = replace_res.json()

    assert replaced_data["id"] == image_id
    assert replaced_data["mime_type"] == "image/png"
    assert replaced_data["image_width"] == 300
    assert replaced_data["image_height"] == 300
    assert replaced_data["original_file_name"] == "higher_quality.png"

    # Old file must be cleaned up, new file must exist
    assert not Path(old_file_path).exists()
    assert Path(replaced_data["file_path"]).exists()


def test_soft_deletion_and_status_toggle(image_test_env):
    """Verify DELETE /images/{id} soft-deactivates the image without deleting the file."""
    client = image_test_env["client"]
    token = image_test_env["alpha_token"]
    case_id = image_test_env["missing_case_id"]

    img_bytes = create_test_image_bytes("JPEG")
    image_record = client.post(
        f"/cases/{case_id}/images",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("active_record.jpg", io.BytesIO(img_bytes), "image/jpeg"))],
    ).json()[0]
    image_id = image_record["id"]
    file_path = image_record["file_path"]

    # 1. Soft delete
    del_res = client.delete(f"/images/{image_id}", headers={"Authorization": f"Bearer {token}"})
    assert del_res.status_code == 200
    assert del_res.json()["is_active"] is False

    # Physical file remains intact
    assert Path(file_path).exists()

    # Inactive image is no longer returned in default case image list
    case_list = client.get(f"/cases/{case_id}/images", headers={"Authorization": f"Bearer {token}"}).json()
    assert not any(img["id"] == image_id for img in case_list)

    # 2. Reactivate using status endpoint
    patch_res = client.patch(
        f"/images/{image_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "ACTIVE"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["is_active"] is True


def test_dataset_retrieval_endpoints(image_test_env):
    """Verify /datasets/missing, /datasets/wanted, and /datasets/{category}/cases."""
    client = image_test_env["client"]
    admin_token = image_test_env["admin_token"]
    alpha_token = image_test_env["alpha_token"]
    missing_case_id = image_test_env["missing_case_id"]
    missing_case_number = image_test_env["missing_case_number"]
    wanted_case_id = image_test_env["wanted_case_id"]

    # Upload 1 image to missing case and 1 to wanted case
    img = create_test_image_bytes("JPEG")
    client.post(
        f"/cases/{missing_case_id}/images",
        headers={"Authorization": f"Bearer {alpha_token}"},
        files=[("files", ("missing_photo.jpg", io.BytesIO(img), "image/jpeg"))],
    )
    client.post(
        f"/cases/{wanted_case_id}/images",
        headers={"Authorization": f"Bearer {admin_token}"},
        files=[("files", ("wanted_photo.jpg", io.BytesIO(img), "image/jpeg"))],
    )

    # 1. GET /datasets/missing
    missing_res = client.get("/datasets/missing", headers={"Authorization": f"Bearer {admin_token}"})
    assert missing_res.status_code == 200
    missing_data = missing_res.json()
    assert missing_data["total"] >= 1
    assert all("missing_persons" in item["file_path"] for item in missing_data["items"])

    # 2. GET /datasets/wanted
    wanted_res = client.get("/datasets/wanted", headers={"Authorization": f"Bearer {admin_token}"})
    assert wanted_res.status_code == 200
    wanted_data = wanted_res.json()
    assert wanted_data["total"] >= 1
    assert all("wanted_persons" in item["file_path"] for item in wanted_data["items"])

    # 3. GET /datasets/{category}/cases (active cases with active reference images)
    cases_with_imgs_res = client.get(
        "/datasets/MISSING/cases",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert cases_with_imgs_res.status_code == 200
    cat_cases_data = cases_with_imgs_res.json()
    assert cat_cases_data["total"] >= 1
    first_case = cat_cases_data["items"][0]
    assert first_case["case_number"] == missing_case_number
    assert len(first_case["reference_images"]) >= 1
    assert first_case["reference_images"][0]["case_id"] == missing_case_id


def test_ai_internal_service_interface(image_test_env):
    """Verify internal ImageService methods designed for future AI processing modules."""
    client = image_test_env["client"]
    alpha_token = image_test_env["alpha_token"]
    missing_case_id = image_test_env["missing_case_id"]
    missing_case_number = image_test_env["missing_case_number"]
    Session = image_test_env["Session"]

    # Upload an image first
    img = create_test_image_bytes("JPEG")
    client.post(
        f"/cases/{missing_case_id}/images",
        headers={"Authorization": f"Bearer {alpha_token}"},
        files=[("files", ("ai_sample.jpg", io.BytesIO(img), "image/jpeg"))],
    )

    db = Session()
    # Test internal service call for AI candidate matching
    active_missing_images = ImageService.get_active_images_for_ai(db, category="MISSING")
    assert len(active_missing_images) >= 1
    for img in active_missing_images:
        assert img.is_active is True

    # Test case-specific reference images for candidate ranking
    case_images = ImageService.get_case_images_for_ai(db, case_number=missing_case_number)
    assert len(case_images) >= 1
    db.close()
