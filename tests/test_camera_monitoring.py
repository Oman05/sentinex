import asyncio
from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.camera import Camera, CameraStatus
from app.models.department import Department
from app.models.user import User, UserRole
from app.services.auth_service import create_access_token, hash_password
from app.services.camera_service import CameraService
from app.services.stream_manager import stream_manager
from app.utils.frame_queue import BoundedFrameQueue, FrameMetadata
from app.workers.stream_worker import StreamWorker


@pytest.fixture
def camera_test_env(tmp_path):
    """Set up an isolated SQLite database and test environment for camera streaming."""
    db_path = tmp_path / "sentinex_cam_test.db"
    settings.DATABASE_URL = f"sqlite:///{db_path}"

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

    db = TestingSession()
    dept1 = Department(department_name="North District CCTV", department_type="SURVEILLANCE", location="North Sector")
    dept2 = Department(department_name="South District CCTV", department_type="SURVEILLANCE", location="South Sector")
    db.add_all([dept1, dept2])
    db.commit()
    db.refresh(dept1)
    db.refresh(dept2)

    admin = User(
        username="cctv_admin",
        email="cctv_admin@sentinex.gov",
        password_hash=hash_password("Secr3tP@ss!"),
        role=UserRole.ADMIN.value,
        department_id=None,
        is_active=True,
    )
    north_officer = User(
        username="north_operator",
        email="north@sentinex.gov",
        password_hash=hash_password("Secr3tP@ss!"),
        role=UserRole.POLICE.value,
        department_id=dept1.id,
        is_active=True,
    )
    south_officer = User(
        username="south_operator",
        email="south@sentinex.gov",
        password_hash=hash_password("Secr3tP@ss!"),
        role=UserRole.POLICE.value,
        department_id=dept2.id,
        is_active=True,
    )
    db.add_all([admin, north_officer, south_officer])
    db.commit()
    db.refresh(admin)
    db.refresh(north_officer)
    db.refresh(south_officer)

    # Pre-register a camera in North Sector
    camera_north = Camera(
        camera_code="CAM-NORTH-001",
        camera_name="North Station Main Gate",
        department_id=dept1.id,
        location_name="Station Gate A",
        latitude=40.7128,
        longitude=-74.0060,
        jurisdiction="North District",
        stream_url="rtsp://192.168.1.101/live",
        stream_type="RTSP",
        username_reference="operator",
        encrypted_password=CameraService.encrypt_password("NorthPass123"),
        status=CameraStatus.INACTIVE.value,
        is_active=True,
        sample_fps=2.0,
        queue_size=10,
        retry_limit=3,
    )
    db.add(camera_north)
    db.commit()
    db.refresh(camera_north)

    # Save IDs and tokens before closing session
    dept1_id = dept1.id
    dept2_id = dept2.id
    admin_id = admin.id
    admin_name = admin.username
    admin_role = admin.role
    north_id = north_officer.id
    north_name = north_officer.username
    north_role = north_officer.role
    south_id = south_officer.id
    south_name = south_officer.username
    south_role = south_officer.role
    camera_north_id = camera_north.id
    camera_north_code = camera_north.camera_code

    db.close()

    admin_token = create_access_token({"sub": admin_name, "user_id": admin_id, "role": admin_role})
    north_token = create_access_token({"sub": north_name, "user_id": north_id, "role": north_role})
    south_token = create_access_token({"sub": south_name, "user_id": south_id, "role": south_role})

    with TestClient(app) as client:
        yield {
            "client": client,
            "engine": engine,
            "Session": TestingSession,
            "admin_token": admin_token,
            "north_token": north_token,
            "south_token": south_token,
            "dept1_id": dept1_id,
            "dept2_id": dept2_id,
            "camera_north_id": camera_north_id,
            "camera_north_code": camera_north_code,
        }

    app.dependency_overrides.clear()
    engine.dispose()


def test_register_camera_validates_and_encrypts_password(camera_test_env):
    """Verify camera registration encrypts credentials and excludes them from response."""
    client = camera_test_env["client"]
    token = camera_test_env["admin_token"]
    dept_id = camera_test_env["dept1_id"]

    payload = {
        "camera_code": "CAM-REG-001",
        "camera_name": "Traffic Junction 4",
        "department_id": dept_id,
        "location_name": "5th Avenue Junction",
        "latitude": 40.7306,
        "longitude": -73.9352,
        "jurisdiction": "Central Traffic",
        "stream_url": "rtsp://camera-junction4.local/stream1",
        "stream_type": "RTSP",
        "username_reference": "admin_cam",
        "password": "SuperSecretPassword!",
        "sample_fps": 2.5,
        "queue_size": 16,
        "retry_limit": 5,
    }

    response = client.post("/cameras", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert response.status_code == 201, response.text
    data = response.json()

    assert data["camera_code"] == payload["camera_code"]
    assert data["camera_name"] == payload["camera_name"]
    assert data["department_id"] == dept_id
    assert data["sample_fps"] == 2.5
    assert data["queue_size"] == 16
    assert data["retry_limit"] == 5
    # Credentials must NEVER be present in the response
    assert "password" not in data
    assert "encrypted_password" not in data


def test_register_camera_rejects_embedded_credentials_and_bad_protocol(camera_test_env):
    """Verify stream URL validation rejects embedded @ credentials and unknown schemes."""
    client = camera_test_env["client"]
    token = camera_test_env["admin_token"]
    dept_id = camera_test_env["dept1_id"]

    # 1. Embedded credentials in stream_url
    bad_url_payload = {
        "camera_name": "Illegal Credential Cam",
        "department_id": dept_id,
        "stream_url": "rtsp://admin:secret123@192.168.1.50/live",
    }
    res1 = client.post("/cameras", headers={"Authorization": f"Bearer {token}"}, json=bad_url_payload)
    assert res1.status_code in {400, 422}
    assert "embedded credentials" in str(res1.json()).lower()

    # 2. Unsupported protocol (e.g. FTP)
    bad_protocol_payload = {
        "camera_name": "FTP Cam",
        "department_id": dept_id,
        "stream_url": "ftp://192.168.1.50/live.mp4",
    }
    res2 = client.post("/cameras", headers={"Authorization": f"Bearer {token}"}, json=bad_protocol_payload)
    assert res2.status_code in {400, 422}
    assert "rtsp, http, or https" in str(res2.json()).lower()


def test_rbac_department_isolation_and_unauthorized_audit(camera_test_env):
    """Verify department officer cannot access or modify other department's cameras."""
    client = camera_test_env["client"]
    north_token = camera_test_env["north_token"]
    south_token = camera_test_env["south_token"]
    camera_id = camera_test_env["camera_north_id"]
    Session = camera_test_env["Session"]

    # 1. North operator CAN view North camera
    res_north = client.get(f"/cameras/{camera_id}", headers={"Authorization": f"Bearer {north_token}"})
    assert res_north.status_code == 200
    assert res_north.json()["id"] == camera_id

    # 2. South operator CANNOT view North camera -> 403 Forbidden
    res_south = client.get(f"/cameras/{camera_id}", headers={"Authorization": f"Bearer {south_token}"})
    assert res_south.status_code == 403

    # 3. Verify UNAUTHORIZED_ACCESS_ATTEMPT was logged
    db = Session()
    audit_entry = (
        db.query(AuditLog)
        .filter(AuditLog.action == "UNAUTHORIZED_ACCESS_ATTEMPT")
        .order_by(AuditLog.timestamp.desc())
        .first()
    )
    assert audit_entry is not None
    assert audit_entry.resource_type == "CAMERA"
    assert audit_entry.resource_id == camera_id
    db.close()


def test_camera_update_and_status_patch(camera_test_env):
    """Verify camera configuration update and status patching."""
    client = camera_test_env["client"]
    token = camera_test_env["admin_token"]
    camera_id = camera_test_env["camera_north_id"]

    # 1. Update camera metadata
    update_res = client.put(
        f"/cameras/{camera_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "camera_name": "Updated North Gate Surveillance",
            "location_name": "Station Gate A - Primary Entry",
            "sample_fps": 3.0,
        },
    )
    assert update_res.status_code == 200
    assert update_res.json()["camera_name"] == "Updated North Gate Surveillance"
    assert update_res.json()["sample_fps"] == 3.0

    # 2. Patch status to ACTIVE
    status_res = client.patch(
        f"/cameras/{camera_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "ACTIVE"},
    )
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "ACTIVE"
    assert status_res.json()["is_active"] is True


def test_camera_soft_deletion(camera_test_env):
    """Verify DELETE /cameras/{id} soft-deactivates the camera without permanent removal."""
    client = camera_test_env["client"]
    token = camera_test_env["admin_token"]
    camera_id = camera_test_env["camera_north_id"]
    Session = camera_test_env["Session"]

    del_res = client.delete(f"/cameras/{camera_id}", headers={"Authorization": f"Bearer {token}"})
    assert del_res.status_code == 200
    assert del_res.json()["is_active"] is False
    assert del_res.json()["status"] == "INACTIVE"

    # Verify record still exists in the database
    db = Session()
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    assert cam is not None
    assert cam.is_active is False
    db.close()


@pytest.mark.anyio
async def test_stream_worker_mock_frame_sampling_and_metadata():
    """Verify stream worker frame queue buffering, sampling, and complete metadata generation."""
    worker = StreamWorker(
        camera_id=99,
        stream_url="test://virtual-camera",
        sample_fps=10.0,
        queue_size=4,
        retry_limit=2,
        camera_code="CAM-TEST-099",
        location_name="AI Test Lab",
        department_id=1,
    )

    dummy_frame = b"\x00" * (100 * 100 * 3)

    # Simulate pushing 6 frames into a queue of size 4
    for seq in range(1, 7):
        meta = FrameMetadata(
            camera_id=worker.camera_id,
            captured_at=datetime.utcnow(),
            frame=dummy_frame,
            sequence=seq,
            camera_code=worker.camera_code,
            location_name=worker.location_name,
            department_id=worker.department_id,
        )
        worker.queue.put_nowait(meta)

    # Queue should be bounded to 4 and have dropped 2 frames
    assert worker.queue.qsize() == 4
    assert worker.queue.dropped_frames == 2

    latest = worker.queue.get_latest()
    assert latest is not None
    assert latest.sequence == 6
    assert latest.camera_code == "CAM-TEST-099"
    assert latest.location_name == "AI Test Lab"
    assert latest.department_id == 1
    assert latest.frame_reference.startswith("CAM-TEST-099-000006-")
    assert latest.timestamp is not None


@pytest.mark.anyio
async def test_multi_camera_failure_isolation():
    """Verify that a failure in one camera stream does not affect other streams."""
    # Worker 1: Simulated online stream
    worker_healthy = StreamWorker(
        camera_id=101,
        stream_url="test://healthy",
        sample_fps=1.0,
        camera_code="CAM-HEALTHY",
    )

    # Worker 2: Faulty stream
    worker_faulty = StreamWorker(
        camera_id=102,
        stream_url="test://invalid-host:9999/none",
        sample_fps=1.0,
        retry_limit=1,
        camera_code="CAM-FAULTY",
    )

    # Push dummy frame to healthy worker
    dummy_frame = b"\x00" * (50 * 50 * 3)
    worker_healthy.queue.put_nowait(
        FrameMetadata(101, datetime.utcnow(), dummy_frame, 1, camera_code="CAM-HEALTHY")
    )

    stream_manager._workers[101] = worker_healthy
    stream_manager._workers[102] = worker_faulty

    # Healthy worker remains accessible even when faulty worker encounters errors
    assert stream_manager.get_frame_queue(101) is not None
    assert stream_manager.get_latest_frame(101) is not None
    assert stream_manager.get_latest_frame(101).camera_code == "CAM-HEALTHY"

    # Cleanup
    await stream_manager.stop(101)
    await stream_manager.stop(102)


def test_camera_health_telemetry_and_summary(camera_test_env):
    """Verify individual camera health and fleet-wide health summary endpoints."""
    client = camera_test_env["client"]
    admin_token = camera_test_env["admin_token"]
    camera_id = camera_test_env["camera_north_id"]

    # Simulate health telemetry
    stream_manager.health.record_frame(camera_id, datetime.utcnow())

    # 1. GET /cameras/{id}/health
    health_res = client.get(f"/cameras/{camera_id}/health", headers={"Authorization": f"Bearer {admin_token}"})
    assert health_res.status_code == 200
    h_data = health_res.json()
    assert h_data["camera_id"] == camera_id
    assert h_data["connection_status"] == "ONLINE"
    assert h_data["failures"] == 0

    # 2. GET /cameras/health/summary
    summary_res = client.get("/cameras/health/summary", headers={"Authorization": f"Bearer {admin_token}"})
    assert summary_res.status_code == 200
    s_data = summary_res.json()
    assert s_data["total"] >= 1
    assert s_data["online"] >= 1
