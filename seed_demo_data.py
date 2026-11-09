"""
Sentinex Demo Data Seeder
=========================
Populates realistic, fully-interconnected demo data into sentinex.db:
- Departments (Central Command, Cyber Crime, Missing Persons, Transit Security)
- Demo Users with distinct roles (admin, reviewer, officer, analyst)
- CCTV Cameras (Active/Online and Offline streams)
- Missing & Wanted Cases linked to existing match & review events
- Operational Alerts (Dispatched, Acknowledged, In-Progress)
- Investigation Tasks (Assigned, In-Progress)
- Evidence Items with SHA-256 integrity hashes & Chain of Custody
- AI Model Registry, Benchmark Datasets & Scientific Evaluation Results
"""

import os
import sys
import hashlib
import secrets
from datetime import datetime, timedelta

# Ensure backend is on PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

import app.main  # registers all ORM models into SQLAlchemy registry

from app.database.session import SessionLocal, init_db
from app.core.security import hash_password

# Models
from app.models.user import User, UserRole
from app.models.department import Department
from app.models.camera import Camera, CameraStatus
from app.models.case import Case, CaseCategory, CasePriority, CaseStatus
from app.models.review_event import ReviewEventDB, ReviewDecision, ReviewStatus, InvestigationTaskDB, TaskStatus, TaskPriority, ReviewAuditLogDB
from app.models.alert import AlertDB, AlertStatus, AlertPriority, DeliveryChannel, RecipientType
from app.models.evidence import EvidenceItemDB, EvidenceType, EvidenceStatus
from app.models.analytics import ModelRegistryDB, DatasetRegistryDB, EvaluationRunDB, EvaluationResultDB
from app.models.system_config import SystemConfigDB
from app.services.config_service import config_service


def seed_demo_data():
    init_db()
    db = SessionLocal()

    print("🚀 Initializing Sentinex Demo Data...")

    # Ensure system configs initialized
    config_service.initialize_defaults(db)

    # -------------------------------------------------------------------------
    # 1. DEPARTMENTS
    # -------------------------------------------------------------------------
    print("🏢 Seeding Departments...")
    depts = [
        {
            "department_code": "DEPT-CENTRAL",
            "department_name": "Metropolitan Police - Central Command",
            "department_type": "POLICE",
            "jurisdiction": "Metro Central District",
            "location": "HQ Building, 100 Civic Center Plaza",
            "latitude": 40.7128,
            "longitude": -74.0060,
            "contact_email": "central.command@police.gov.local",
            "contact_phone": "+1-555-0100",
            "is_central": True,
            "is_active": True,
        },
        {
            "department_code": "DEPT-MISSING",
            "department_name": "Missing Persons Investigation Bureau",
            "department_type": "INVESTIGATION",
            "jurisdiction": "Statewide Specialized Unit",
            "location": "Regional Justice Center, Wing B",
            "latitude": 40.7150,
            "longitude": -74.0020,
            "contact_email": "missing.persons@justice.gov.local",
            "contact_phone": "+1-555-0120",
            "is_central": False,
            "is_active": True,
        },
        {
            "department_code": "DEPT-TRANSIT",
            "department_name": "Metro Transit Security & Rapid Response",
            "department_type": "EMERGENCY",
            "jurisdiction": "Public Transit & Rail Network",
            "location": "Transit Hub Central Station, Level 2",
            "latitude": 40.7200,
            "longitude": -73.9950,
            "contact_email": "transit.security@metrotransit.local",
            "contact_phone": "+1-555-0155",
            "is_central": False,
            "is_active": True,
        },
        {
            "department_code": "DEPT-CYBER",
            "department_name": "Digital Forensics & AI Oversight Unit",
            "department_type": "INVESTIGATION",
            "jurisdiction": "Specialized Technical Division",
            "location": "Tech Campus Annex, Suite 400",
            "latitude": 40.7280,
            "longitude": -73.9900,
            "contact_email": "ai.oversight@police.gov.local",
            "contact_phone": "+1-555-0188",
            "is_central": False,
            "is_active": True,
        },
    ]

    dept_map = {}
    for d_data in depts:
        dept = db.query(Department).filter(Department.department_code == d_data["department_code"]).first()
        if not dept:
            dept = Department(**d_data)
            db.add(dept)
            db.flush()
        dept_map[d_data["department_code"]] = dept
    db.commit()

    # -------------------------------------------------------------------------
    # 2. USERS
    # -------------------------------------------------------------------------
    print("👤 Seeding Users...")
    users_data = [
        {
            "username": "admin",
            "email": "admin@sentinex.local",
            "role": UserRole.ADMIN.value,
            "department_id": dept_map["DEPT-CENTRAL"].id,
        },
        {
            "username": "police",
            "email": "officer.smith@police.gov.local",
            "role": UserRole.POLICE.value,
            "department_id": dept_map["DEPT-CENTRAL"].id,
        },
        {
            "username": "reviewer_jane",
            "email": "jane.doe@sentinex.local",
            "role": "REVIEWER",
            "department_id": dept_map["DEPT-MISSING"].id,
        },
        {
            "username": "officer_bob",
            "email": "bob.jones@transit.local",
            "role": "OFFICER",
            "department_id": dept_map["DEPT-TRANSIT"].id,
        },
        {
            "username": "analyst_carol",
            "email": "carol.ai@sentinex.local",
            "role": "ANALYST",
            "department_id": dept_map["DEPT-CYBER"].id,
        },
    ]

    user_map = {}
    initial_credentials = []
    for u in users_data:
        user = db.query(User).filter(User.username == u["username"]).first()
        if not user:
            initial_password = secrets.token_urlsafe(24)
            user = User(
                username=u["username"],
                email=u["email"],
                password_hash=hash_password(initial_password),
                role=u["role"],
                is_active=True,
                department_id=u["department_id"],
            )
            db.add(user)
            db.flush()
            initial_credentials.append((u["username"], initial_password))
        user_map[u["username"]] = user
    db.commit()
    if initial_credentials:
        print("Generated initial passwords for newly created demo users:")
        for username, password in initial_credentials:
            print(f"  {username}: {password}")

    # -------------------------------------------------------------------------
    # 3. CAMERAS
    # -------------------------------------------------------------------------
    print("📹 Seeding Cameras...")
    cameras_data = [
        {
            "camera_code": "CAM-TERM-01",
            "camera_name": "Main Terminal Concourse Gate A",
            "department_id": dept_map["DEPT-TRANSIT"].id,
            "location_name": "Transit Hub Central Station, Concourse East",
            "latitude": 40.7202,
            "longitude": -73.9952,
            "jurisdiction": "Metro Transit",
            "stream_url": "rtsp://192.168.1.101:554/live/stream1",
            "stream_type": "RTSP",
            "status": CameraStatus.ONLINE.value,
            "is_active": True,
            "processing_enabled": True,
            "sample_fps": 1.0,
            "sampling_interval": 1.0,
        },
        {
            "camera_code": "CAM-PLAT-02",
            "camera_name": "North Metro Platform - Track 2",
            "department_id": dept_map["DEPT-TRANSIT"].id,
            "location_name": "North Platform Passenger Boarding Area",
            "latitude": 40.7210,
            "longitude": -73.9940,
            "jurisdiction": "Metro Transit",
            "stream_url": "rtsp://192.168.1.102:554/live/stream1",
            "stream_type": "RTSP",
            "status": CameraStatus.ONLINE.value,
            "is_active": True,
            "processing_enabled": True,
            "sample_fps": 1.0,
            "sampling_interval": 1.0,
        },
        {
            "camera_code": "CAM-TURN-03",
            "camera_name": "West Transit Turnstile Exit",
            "department_id": dept_map["DEPT-TRANSIT"].id,
            "location_name": "Fare Gate & Western Pedestrian Turnstiles",
            "latitude": 40.7198,
            "longitude": -73.9960,
            "jurisdiction": "Metro Transit",
            "stream_url": "rtsp://192.168.1.103:554/live/stream1",
            "stream_type": "RTSP",
            "status": CameraStatus.ONLINE.value,
            "is_active": True,
            "processing_enabled": True,
            "sample_fps": 1.0,
            "sampling_interval": 1.0,
        },
        {
            "camera_code": "CAM-BAGG-04",
            "camera_name": "Baggage Claim Hall East",
            "department_id": dept_map["DEPT-CENTRAL"].id,
            "location_name": "Arrivals Hall Carousel 1-4",
            "latitude": 40.7180,
            "longitude": -73.9980,
            "jurisdiction": "Metro Central",
            "stream_url": "rtsp://192.168.1.104:554/live/stream1",
            "stream_type": "RTSP",
            "status": CameraStatus.OFFLINE.value,
            "is_active": True,
            "processing_enabled": False,
            "sample_fps": 0.5,
            "sampling_interval": 2.0,
        },
    ]

    camera_map = {}
    for c_data in cameras_data:
        cam = db.query(Camera).filter(Camera.camera_code == c_data["camera_code"]).first()
        if not cam:
            cam = Camera(**c_data)
            db.add(cam)
            db.flush()
        camera_map[c_data["camera_code"]] = cam
    db.commit()

    # -------------------------------------------------------------------------
    # 4. CASES
    # -------------------------------------------------------------------------
    print("📁 Seeding Cases...")
    cases_data = [
        {
            "case_number": "MP-2026-0001",
            "title": "Missing Person: Sarah Jenkins (Student, Age 21)",
            "category": CaseCategory.MISSING.value,
            "priority": CasePriority.HIGH.value,
            "status": CaseStatus.ACTIVE.value,
            "person_identifier": "PID-MP-2026-0001",
            "description": "Last seen near University Metro station on Friday evening wearing navy jacket and gray backpack.",
            "department_id": dept_map["DEPT-MISSING"].id,
            "created_by": user_map["admin"].id,
            "last_known_location": "University Metro Station Concourse",
        },
        {
            "case_number": "MP-2026-0002",
            "title": "Silver Alert: Michael Chang (Elderly, Dementia, Age 74)",
            "category": CaseCategory.MISSING.value,
            "priority": CasePriority.CRITICAL.value,
            "status": CaseStatus.ACTIVE.value,
            "person_identifier": "PID-MP-2026-0002",
            "description": "Requires medication. Wandered from residential care facility near Transit Hub.",
            "department_id": dept_map["DEPT-MISSING"].id,
            "created_by": user_map["police"].id,
            "last_known_location": "Transit Hub Plaza",
        },
        {
            "case_number": "MP-2026-0003",
            "title": "Missing Juvenile: Lucas Miller (Age 15)",
            "category": CaseCategory.MISSING.value,
            "priority": CasePriority.MEDIUM.value,
            "status": CaseStatus.ACTIVE.value,
            "person_identifier": "PID-MP-2026-0003",
            "description": "Reported missing after school extracurricular activities; reference photo enrolled in dataset.",
            "department_id": dept_map["DEPT-MISSING"].id,
            "created_by": user_map["admin"].id,
            "last_known_location": "Sector 9 Community Library",
        },
        {
            "case_number": "WP-2026-0001",
            "title": "Person of Interest: Downtown Credit Fraud Investigation",
            "category": CaseCategory.WANTED.value,
            "priority": CasePriority.HIGH.value,
            "status": CaseStatus.ACTIVE.value,
            "person_identifier": "PID-WP-2026-0001",
            "description": "Active warrant for commercial identity fraud and unauthorized ATM skimming network.",
            "department_id": dept_map["DEPT-CENTRAL"].id,
            "created_by": user_map["police"].id,
            "last_known_location": "Financial District ATMs",
        },
        {
            "case_number": "WP-2026-0002",
            "title": "Warrant: Organized Transit Pickpocket Ring Leader",
            "category": CaseCategory.WANTED.value,
            "priority": CasePriority.MEDIUM.value,
            "status": CaseStatus.ACTIVE.value,
            "person_identifier": "PID-WP-2026-0002",
            "description": "Target of joint transit taskforce; multi-camera observation correlation in progress.",
            "department_id": dept_map["DEPT-TRANSIT"].id,
            "created_by": user_map["officer_bob"].id,
            "last_known_location": "Platform Turnstiles",
        },
    ]

    case_map = {}
    for c_data in cases_data:
        case = db.query(Case).filter(Case.case_number == c_data["case_number"]).first()
        if not case:
            case = Case(**c_data)
            db.add(case)
            db.flush()
        case_map[c_data["case_number"]] = case
    db.commit()

    # -------------------------------------------------------------------------
    # 5. CONNECT EXISTING REVIEW EVENTS & UPDATE STATES
    # -------------------------------------------------------------------------
    print("🔍 Linking Review Events to Cases & Cameras...")
    review_events = db.query(ReviewEventDB).all()
    cam_list = list(camera_map.values())

    # Map existing review events to real cases and cameras
    for i, rev in enumerate(review_events):
        target_case_num = f"MP-2026-000{(i % 3) + 1}" if (i % 2 == 0) else f"WP-2026-000{(i % 2) + 1}"
        if target_case_num in case_map:
            rev.case_id = case_map[target_case_num].id
            rev.case_number = target_case_num
            rev.category = case_map[target_case_num].category

        assigned_cam = cam_list[i % len(cam_list)]
        rev.camera_id = assigned_cam.id
        rev.camera_location = assigned_cam.location_name
        rev.model_name = "FaceNet-InceptionResnetV1"
        rev.model_version = "2.6.0"

    # Set up some confirmed events to trigger alerts & demonstrate workflow
    if len(review_events) >= 3:
        # Event 1: CONFIRMED_FOR_ACTION
        ev1 = review_events[0]
        ev1.status = ReviewStatus.CONFIRMED_FOR_ACTION.value
        ev1.decision = ReviewDecision.CONFIRM_FOR_ACTION.value
        ev1.decision_notes = "Verified facial landmarks (interpupillary distance, nose bridge, ear morphology) match reference photo MP-2026-0001."
        ev1.assigned_to = user_map["reviewer_jane"].id
        ev1.decision_at = datetime.utcnow() - timedelta(hours=2)
        ev1.review_started_at = datetime.utcnow() - timedelta(hours=2, minutes=15)
        ev1.review_completed_at = datetime.utcnow() - timedelta(hours=2)

        # Event 2: CONFIRMED_FOR_ACTION
        ev2 = review_events[1]
        ev2.status = ReviewStatus.CONFIRMED_FOR_ACTION.value
        ev2.decision = ReviewDecision.CONFIRM_FOR_ACTION.value
        ev2.decision_notes = "Distinctive facial scar and jawline match confirmed against warrant profile WP-2026-0001."
        ev2.assigned_to = user_map["reviewer_jane"].id
        ev2.decision_at = datetime.utcnow() - timedelta(hours=1)
        ev2.review_started_at = datetime.utcnow() - timedelta(hours=1, minutes=10)
        ev2.review_completed_at = datetime.utcnow() - timedelta(hours=1)

        # Event 3: UNDER_REVIEW
        ev3 = review_events[2]
        ev3.status = ReviewStatus.UNDER_REVIEW.value
        ev3.assigned_to = user_map["reviewer_jane"].id
        ev3.review_started_at = datetime.utcnow() - timedelta(minutes=20)

    db.commit()

    # -------------------------------------------------------------------------
    # 6. OPERATIONAL ALERTS
    # -------------------------------------------------------------------------
    print("🚨 Seeding Operational Alerts...")
    if len(review_events) >= 2:
        alerts_data = [
            {
                "alert_number": "ALT-2026-000001",
                "match_event_id": review_events[0].match_event_id,
                "review_event_id": review_events[0].id,
                "case_id": review_events[0].case_id,
                "case_number": review_events[0].case_number,
                "category": review_events[0].category or "MISSING",
                "originating_department_id": dept_map["DEPT-MISSING"].id,
                "detected_camera_id": camera_map["CAM-TERM-01"].id,
                "detected_camera_code": "CAM-TERM-01",
                "detected_location": camera_map["CAM-TERM-01"].location_name,
                "nearest_department_id": dept_map["DEPT-TRANSIT"].id,
                "routing_reason": "Nearest authorized transit security unit (0.2 km from detection gate).",
                "distance_km": 0.2,
                "priority": AlertPriority.HIGH.value,
                "status": AlertStatus.SENT.value,
                "created_at": datetime.utcnow() - timedelta(hours=2),
            },
            {
                "alert_number": "ALT-2026-000002",
                "match_event_id": review_events[1].match_event_id,
                "review_event_id": review_events[1].id,
                "case_id": review_events[1].case_id,
                "case_number": review_events[1].case_number,
                "category": review_events[1].category or "WANTED",
                "originating_department_id": dept_map["DEPT-CENTRAL"].id,
                "detected_camera_id": camera_map["CAM-TURN-03"].id,
                "detected_camera_code": "CAM-TURN-03",
                "detected_location": camera_map["CAM-TURN-03"].location_name,
                "nearest_department_id": dept_map["DEPT-TRANSIT"].id,
                "routing_reason": "Jurisdiction coverage over Western Pedestrian Exit.",
                "distance_km": 0.4,
                "priority": AlertPriority.NORMAL.value,
                "status": AlertStatus.ACKNOWLEDGED.value,
                "acknowledged_at": datetime.utcnow() - timedelta(minutes=45),
                "acknowledged_by": user_map["officer_bob"].id,
                "created_at": datetime.utcnow() - timedelta(hours=1),
            },
            {
                "alert_number": "ALT-2026-000003",
                "match_event_id": "EVT-MOCK-ALERT3",
                "review_event_id": review_events[0].id,
                "case_id": case_map["MP-2026-0002"].id,
                "case_number": "MP-2026-0002",
                "category": "MISSING",
                "originating_department_id": dept_map["DEPT-MISSING"].id,
                "detected_camera_id": camera_map["CAM-PLAT-02"].id,
                "detected_camera_code": "CAM-PLAT-02",
                "detected_location": camera_map["CAM-PLAT-02"].location_name,
                "nearest_department_id": dept_map["DEPT-TRANSIT"].id,
                "routing_reason": "Urgent Silver Alert proximity dispatch to North Platform patrol.",
                "distance_km": 0.1,
                "priority": AlertPriority.CRITICAL.value,
                "status": AlertStatus.IN_PROGRESS.value,
                "acknowledged_at": datetime.utcnow() - timedelta(minutes=15),
                "acknowledged_by": user_map["officer_bob"].id,
                "created_at": datetime.utcnow() - timedelta(minutes=30),
            },
        ]

        for a_data in alerts_data:
            alt = db.query(AlertDB).filter(AlertDB.alert_number == a_data["alert_number"]).first()
            if not alt:
                alt = AlertDB(**a_data)
                db.add(alt)
        db.commit()

    # -------------------------------------------------------------------------
    # 7. INVESTIGATION TASKS
    # -------------------------------------------------------------------------
    print("📋 Seeding Investigation Tasks...")
    if len(review_events) >= 2:
        tasks = [
            {
                "review_event_id": review_events[0].id,
                "case_id": review_events[0].case_id,
                "case_number": review_events[0].case_number,
                "title": "Dispatch Field Unit for Sarah Jenkins Verification",
                "description": "Authorized reviewer confirmed match at Concourse Gate A. Verify physical presence and provide assistance.",
                "priority": TaskPriority.HIGH.value,
                "status": TaskStatus.ASSIGNED.value,
                "assigned_to": user_map["officer_bob"].id,
                "created_by": user_map["reviewer_jane"].id,
                "created_at": datetime.utcnow() - timedelta(hours=2),
            },
            {
                "review_event_id": review_events[1].id,
                "case_id": review_events[1].case_id,
                "case_number": review_events[1].case_number,
                "title": "Preserve Turnstile Video Feed & Identify Travel Direction",
                "description": "Secure 15-minute high-definition video archive around 16:30 for West Turnstile Exit.",
                "priority": TaskPriority.MEDIUM.value,
                "status": TaskStatus.IN_PROGRESS.value,
                "assigned_to": user_map["officer_bob"].id,
                "created_by": user_map["reviewer_jane"].id,
                "created_at": datetime.utcnow() - timedelta(hours=1),
            },
        ]
        for t_data in tasks:
            task = db.query(InvestigationTaskDB).filter(InvestigationTaskDB.title == t_data["title"]).first()
            if not task:
                task = InvestigationTaskDB(**t_data)
                db.add(task)
        db.commit()

    # -------------------------------------------------------------------------
    # 8. EVIDENCE ITEMS & CHAIN OF CUSTODY
    # -------------------------------------------------------------------------
    print("📦 Seeding Evidence Vault...")
    sample_sha256 = hashlib.sha256(b"sentinex-demo-evidence-file-payload").hexdigest()
    if len(review_events) >= 1:
        ev_items = [
            {
                "evidence_id": "EVD-2026-000001",
                "case_id": review_events[0].case_id,
                "case_number": review_events[0].case_number,
                "review_event_id": review_events[0].id,
                "evidence_type": EvidenceType.CCTV_FRAME.value,
                "file_reference": "evidence_store/frames/ev_2026_0001.jpg",
                "file_name": "ev_2026_0001.jpg",
                "original_file_name": "cctv_frame_142211.jpg",
                "file_size": 184520,
                "mime_type": "image/jpeg",
                "file_hash": sample_sha256,
                "status": EvidenceStatus.AVAILABLE.value,
                "storage_backend": "LOCAL",
                "uploaded_by": user_map["admin"].id,
                "created_at": datetime.utcnow() - timedelta(hours=3),
            },
            {
                "evidence_id": "EVD-2026-000002",
                "case_id": review_events[0].case_id,
                "case_number": review_events[0].case_number,
                "review_event_id": review_events[0].id,
                "evidence_type": EvidenceType.REFERENCE_IMAGE.value,
                "file_reference": "datasets/missing_persons/MP-2026-0003/f8ee0c4ac5994dd4b90a6e8a00ea4f30.jpg",
                "file_name": "f8ee0c4ac5994dd4b90a6e8a00ea4f30.jpg",
                "original_file_name": "reference_portrait.jpg",
                "file_size": 94210,
                "mime_type": "image/jpeg",
                "file_hash": hashlib.sha256(b"reference-photo-profile").hexdigest(),
                "status": EvidenceStatus.FINALIZED.value,
                "storage_backend": "LOCAL",
                "uploaded_by": user_map["reviewer_jane"].id,
                "created_at": datetime.utcnow() - timedelta(days=2),
            },
        ]
        for e_data in ev_items:
            ev = db.query(EvidenceItemDB).filter(EvidenceItemDB.evidence_id == e_data["evidence_id"]).first()
            if not ev:
                ev = EvidenceItemDB(**e_data)
                db.add(ev)
        db.commit()

    # -------------------------------------------------------------------------
    # 9. AI MODEL REGISTRY & SCIENTIFIC EVALUATION BENCHMARKS
    # -------------------------------------------------------------------------
    print("🧠 Seeding AI Model Registry & Evaluation Runs...")
    models_data = [
        {
            "model_name": "YOLOv8x-PersonDetector",
            "model_type": "PERSON_DETECTION",
            "version": "8.3.0",
            "framework": "PyTorch 2.1 / Ultralytics",
            "checksum": hashlib.sha256(b"yolov8x-weights-v8.3.0").hexdigest(),
            "status": "ACTIVE",
            "notes": "Primary deep neural network for full-body pedestrian bounding box proposal in CCTV streams.",
        },
        {
            "model_name": "FaceNet-InceptionResnetV1",
            "model_type": "FACE_EMBEDDING",
            "version": "2.6.0",
            "framework": "PyTorch 2.1 / facenet-pytorch",
            "checksum": hashlib.sha256(b"facenet-v1-weights-2.6.0").hexdigest(),
            "status": "ACTIVE",
            "notes": "512-dimensional Euclidean face descriptor generator for candidate similarity retrieval.",
        },
        {
            "model_name": "MTCNN-FaceGate",
            "model_type": "FACE_DETECTION",
            "version": "1.2.0",
            "framework": "PyTorch 2.1",
            "checksum": hashlib.sha256(b"mtcnn-cascade-1.2.0").hexdigest(),
            "status": "ACTIVE",
            "notes": "Facial landmark localization and quality assessment gating stage.",
        },
    ]

    for m_data in models_data:
        m = db.query(ModelRegistryDB).filter(ModelRegistryDB.model_name == m_data["model_name"]).first()
        if not m:
            m = ModelRegistryDB(**m_data)
            db.add(m)
    db.commit()

    # Benchmark dataset
    dataset_data = {
        "dataset_name": "Consented-Synthetic-CCTV-Benchmark-2026",
        "dataset_version": "1.0",
        "category": "TEST",
        "source_type": "SYNTHETIC",
        "sample_count": 1000,
        "notes": "Ethically approved, synthetic/consented reference benchmark for biometric quality & candidate matching accuracy.",
    }
    ds = db.query(DatasetRegistryDB).filter(DatasetRegistryDB.dataset_name == dataset_data["dataset_name"]).first()
    if not ds:
        ds = DatasetRegistryDB(**dataset_data)
        db.add(ds)
        db.flush()
    db.commit()

    # Evaluation Run
    run_id_val = "EVAL-2026-0001"
    run = db.query(EvaluationRunDB).filter(EvaluationRunDB.run_id == run_id_val).first()
    if not run:
        run = EvaluationRunDB(
            run_id=run_id_val,
            run_name="Q4 Model Accuracy & Bias Assessment",
            model_name="FaceNet-InceptionResnetV1",
            model_version="2.6.0",
            dataset_name=dataset_data["dataset_name"],
            dataset_version=dataset_data["dataset_version"],
            status="COMPLETED",
            threshold=0.70,
            justification="Operating point chosen to balance precision while keeping false rejection rate minimal.",
            notes="Formal laboratory benchmark verification on high-variance illumination and low-angle CCTV streams.",
            created_by_user_id=user_map["analyst_carol"].id,
        )
        db.add(run)
        db.flush()

        # Scientific Evaluation Result (Confusion Matrix)
        result = EvaluationResultDB(
            run_id=run_id_val,
            true_positives=94,
            false_positives=2,
            true_negatives=898,
            false_negatives=6,
            precision=0.9792,
            recall=0.9400,
            f1_score=0.9592,
            false_match_rate=0.0022,
            false_non_match_rate=0.0600,
            top1_accuracy=0.9250,
            top5_retrieval_rate=0.9810,
            average_similarity_score=0.784,
            average_latency_ms=18.4,
        )
        db.add(result)
        db.commit()

    print("✅ Sentinex Demo Data Seeding Completed Successfully!")
    db.close()


if __name__ == "__main__":
    seed_demo_data()
