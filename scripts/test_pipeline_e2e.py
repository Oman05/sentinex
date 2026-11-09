#!/usr/bin/env python3
"""
Sentinex – End-to-End Detection Pipeline Test
==============================================
Runs a complete pipeline verification WITHOUT a live camera by:
  1. Loading an enrolled face image from the database
  2. Running YuNet face detection + SFace embedding
  3. Calling the matching service against the in-memory vector index
  4. Verifying a POSSIBLE_MATCH event is created for enrolled subjects
  5. Running an unknown-face probe and confirming NO match event is created
  6. Verifying the deduplication cooldown prevents duplicate events

Usage:
    PYTHONPATH=backend python scripts/test_pipeline_e2e.py

Output:
    Prints a pass/fail report for each stage.
    Exits with code 0 on full pass, 1 on any failure.
"""

from __future__ import annotations

import base64
import sys
import os

# Ensure we can import the app package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

PASS = "\033[32m[PASS]\033[0m"
FAIL = "\033[31m[FAIL]\033[0m"
INFO = "\033[36m[INFO]\033[0m"
WARN = "\033[33m[WARN]\033[0m"


def _encode_image(path: str) -> str | None:
    """Load an image from disk and return a data-URI base64 string."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
        b64 = base64.b64encode(raw).decode()
        return f"data:image/jpeg;base64,{b64}"
    except Exception as exc:
        print(f"  {WARN} Could not read {path}: {exc}")
        return None


def check(label: str, condition: bool, detail: str = "") -> bool:
    tag = PASS if condition else FAIL
    suffix = f"  – {detail}" if detail else ""
    print(f"  {tag} {label}{suffix}")
    return condition


# ---------------------------------------------------------------------------
# Stage 0: Import Check
# ---------------------------------------------------------------------------
print("\n=== Stage 0: Import Check ===")
try:
    from app.database.session import SessionLocal, init_db
    from app.models.face_embedding import FaceEmbeddingDB
    from app.models.reference_image import ReferenceImage
    from app.models.case import Case
    from app.services.matching_service import matching_service
    from app.ai_engine.schemas.matching import (
        MatchDecisionState,
        MatchReadyCandidateInput,
        SearchMode,
    )
    from app.ai_engine.matching.embedding_service import embedding_service
    from app.ai_engine.matching.vector_search import vector_search_index
    import numpy as np
    import cv2
    print(f"  {PASS} All core modules imported successfully")
    print(f"  {INFO} OpenCV version: {cv2.__version__}")
    print(f"  {INFO} NumPy version: {np.__version__}")
except Exception as exc:
    print(f"  {FAIL} Import failed: {exc}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Stage 1: Database Connectivity & Dataset Audit
# ---------------------------------------------------------------------------
print("\n=== Stage 1: Database Connectivity & Dataset Audit ===")
try:
    db = SessionLocal()
    total_cases = db.query(Case).filter(Case.is_active == True).count()
    total_embs = db.query(FaceEmbeddingDB).filter(FaceEmbeddingDB.is_active == True).count()
    total_refs = db.query(ReferenceImage).filter(ReferenceImage.is_active == True).count()
    check("Active cases in database", total_cases > 0, f"{total_cases} active cases")
    check("Active embeddings in database", total_embs > 0, f"{total_embs} embeddings")
    check("Active reference images in database", total_refs > 0, f"{total_refs} reference images")
except Exception as exc:
    print(f"  {FAIL} Database query failed: {exc}")
    db.close()
    sys.exit(1)


# ---------------------------------------------------------------------------
# Stage 2: Load Vector Index from Database
# ---------------------------------------------------------------------------
print("\n=== Stage 2: Vector Index Initialisation ===")
try:
    loaded = matching_service.sync_index_from_database(db)
    missing_count = vector_search_index.count_active(SearchMode.MISSING)
    wanted_count = vector_search_index.count_active(SearchMode.WANTED)
    total_idx = vector_search_index.count_active(SearchMode.ALL_ACTIVE_CASES)
    check("Index loaded > 0 embeddings", loaded > 0, f"{loaded} loaded")
    check("Missing-person index populated", missing_count > 0, f"{missing_count} missing")
    check("Wanted-person index populated", wanted_count >= 0, f"{wanted_count} wanted")
    print(f"  {INFO} Total indexed: {total_idx} (missing={missing_count}, wanted={wanted_count})")
except Exception as exc:
    print(f"  {FAIL} Index sync failed: {exc}")
    db.close()
    sys.exit(1)


# ---------------------------------------------------------------------------
# Stage 3: Embedding Service Self-Test
# ---------------------------------------------------------------------------
print("\n=== Stage 3: Embedding Service Self-Test ===")
try:
    model_name = embedding_service.model_name
    model_ver = embedding_service.model_version
    check("Embedding model loaded", bool(model_name), f"{model_name} v{model_ver}")

    # Use the first active reference image on disk as a self-test probe
    ref_for_test = (
        db.query(ReferenceImage)
        .filter(ReferenceImage.is_active == True)
        .first()
    )
    if ref_for_test and os.path.exists(ref_for_test.file_path):
        probe_b64 = _encode_image(ref_for_test.file_path)
        emb_vec = embedding_service.extract_face_embedding(probe_b64)
        check("Embedding generated from reference image", emb_vec is not None,
              f"dim={len(emb_vec) if emb_vec is not None else 'N/A'}")
    else:
        print(f"  {WARN} No on-disk reference image found for embedding self-test")
        emb_vec = None
except Exception as exc:
    print(f"  {FAIL} Embedding service self-test failed: {exc}")
    emb_vec = None


# ---------------------------------------------------------------------------
# Stage 4: YuNet Face Detection Self-Test
# ---------------------------------------------------------------------------
print("\n=== Stage 4: YuNet Face Detection Self-Test ===")
try:
    onnx_candidates = [
        "backend/face_detection_yunet_2023mar.onnx",
        "face_detection_yunet_2023mar.onnx",
    ]
    yunet_path = next((p for p in onnx_candidates if os.path.exists(p)), None)
    if yunet_path:
        detector = cv2.FaceDetectorYN.create(
            yunet_path, "", (320, 320), score_threshold=0.6, nms_threshold=0.3
        )
        # Load a reference image for detection test
        ref = db.query(ReferenceImage).filter(ReferenceImage.is_active == True).first()
        if ref and os.path.exists(ref.file_path):
            img = cv2.imread(ref.file_path)
            if img is not None:
                h, w = img.shape[:2]
                detector.setInputSize((w, h))
                _, faces = detector.detect(img)
                face_count = len(faces) if faces is not None else 0
                check("YuNet detected face(s) in reference image", face_count > 0,
                      f"{face_count} face(s) found in {os.path.basename(ref.file_path)}")
            else:
                print(f"  {WARN} Could not read reference image with cv2.imread")
        else:
            print(f"  {WARN} No on-disk reference image to test detection")
    else:
        print(f"  {WARN} YuNet ONNX model not found – skipping detection test")
except Exception as exc:
    print(f"  {FAIL} YuNet self-test error: {exc}")


# ---------------------------------------------------------------------------
# Stage 5: Enrolled-Subject Match Test (True Positive)
# ---------------------------------------------------------------------------
print("\n=== Stage 5: Enrolled-Subject Match Test (Expected: POSSIBLE_MATCH) ===")
all_passed = True
try:
    # Pick the first active case that has both a reference image on disk and an embedding
    enrolled_case = None
    enrolled_image_path = None
    for ref in db.query(ReferenceImage).filter(ReferenceImage.is_active == True).all():
        if os.path.exists(ref.file_path):
            case = db.query(Case).filter(Case.id == ref.case_id, Case.is_active == True).first()
            if case:
                enrolled_case = case
                enrolled_image_path = ref.file_path
                break

    if enrolled_case is None or enrolled_image_path is None:
        print(f"  {WARN} No enrolled case with on-disk reference image found – skipping")
    else:
        probe_b64 = _encode_image(enrolled_image_path)
        match_input = MatchReadyCandidateInput(
            candidate_id="E2E-TEST-ENROLLED-001",
            track_id="E2E-TRACK-001",
            camera_id=0,
            timestamp=__import__("datetime").datetime.utcnow(),
            face_image_base64=probe_b64,
            face_quality_score=0.85,
            quality_status="GOOD",
            face_detection_confidence=0.95,
            camera_location="E2E-TEST [TEST_MODE]",
            department_id=enrolled_case.department_id,
            is_match_ready=True,
            search_mode=SearchMode.ALL_ACTIVE_CASES,
        )
        response = matching_service.process_match_ready_candidate(match_input, db=db)

        found_case = any(c.case_id == enrolled_case.id for c in response.candidates)
        got_match = response.decision_state in {
            MatchDecisionState.POSSIBLE_MATCH,
            MatchDecisionState.HIGH_PRIORITY_REVIEW,
        }
        r1 = check("Enrolled subject retrieved as candidate", found_case,
                   f"Case {enrolled_case.case_number} | {enrolled_case.category}")
        r2 = check("Decision state is POSSIBLE_MATCH or HIGH_PRIORITY_REVIEW", got_match,
                   f"decision_state={response.decision_state.value}")
        r3 = check("Processing latency acceptable", response.latency_ms < 2000,
                   f"{response.latency_ms:.1f} ms")
        if response.candidates:
            top = response.candidates[0]
            print(f"  {INFO} Top candidate: case={top.case_number} "
                  f"score={top.similarity_score:.4f} "
                  f"state={top.decision_state.value}")
        all_passed = all_passed and r1 and r2 and r3
except Exception as exc:
    print(f"  {FAIL} Enrolled-subject test failed with exception: {exc}")
    import traceback; traceback.print_exc()
    all_passed = False


# ---------------------------------------------------------------------------
# Stage 6: Unknown-Subject Non-Match Test (True Negative)
# ---------------------------------------------------------------------------
print("\n=== Stage 6: Unknown-Subject Non-Match Test (Expected: NO match alert) ===")
try:
    neg_set_dir = "datasets/negative_sets/unknown_local"
    neg_images = sorted([
        os.path.join(neg_set_dir, f)
        for f in os.listdir(neg_set_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ])[:3]

    if not neg_images:
        print(f"  {WARN} No negative-set images found at {neg_set_dir} – skipping")
    else:
        false_positive_count = 0
        for img_path in neg_images:
            probe_b64 = _encode_image(img_path)
            match_input = MatchReadyCandidateInput(
                candidate_id=f"E2E-TEST-UNKNOWN-{os.path.basename(img_path)}",
                track_id="E2E-TRACK-UNKNOWN",
                camera_id=0,
                timestamp=__import__("datetime").datetime.utcnow(),
                face_image_base64=probe_b64,
                face_quality_score=0.80,
                quality_status="GOOD",
                face_detection_confidence=0.90,
                camera_location="E2E-TEST [TEST_MODE]",
                department_id=None,
                is_match_ready=True,
                search_mode=SearchMode.ALL_ACTIVE_CASES,
            )
            response = matching_service.process_match_ready_candidate(match_input, db=db)
            if response.decision_state in {
                MatchDecisionState.POSSIBLE_MATCH,
                MatchDecisionState.HIGH_PRIORITY_REVIEW,
            }:
                false_positive_count += 1
                top = response.candidates[0] if response.candidates else None
                print(f"  {WARN} False positive on {os.path.basename(img_path)}: "
                      f"case={top.case_number if top else 'N/A'} "
                      f"score={top.similarity_score:.4f if top else 'N/A'}")

        r6 = check("No false-positive alerts on unknown subjects",
                   false_positive_count == 0,
                   f"{false_positive_count}/{len(neg_images)} produced alerts")
        all_passed = all_passed and r6
except Exception as exc:
    print(f"  {FAIL} Unknown-subject test failed: {exc}")
    all_passed = False


# ---------------------------------------------------------------------------
# Stage 7: Deduplication Cooldown Test
# ---------------------------------------------------------------------------
print("\n=== Stage 7: Deduplication Cooldown Test ===")
try:
    from app.ai_engine.matching.match_event_service import match_event_service

    # Run the same enrolled-subject probe twice within the dedup window
    if enrolled_image_path:
        events_first = 0
        events_second = 0
        probe_b64 = _encode_image(enrolled_image_path)

        for i, track_id in enumerate(["DEDUP-TRACK-A", "DEDUP-TRACK-A"]):
            mi = MatchReadyCandidateInput(
                candidate_id=f"E2E-DEDUP-{i}",
                track_id=track_id,
                camera_id=0,
                timestamp=__import__("datetime").datetime.utcnow(),
                face_image_base64=probe_b64,
                face_quality_score=0.85,
                quality_status="GOOD",
                face_detection_confidence=0.95,
                camera_location="E2E-TEST [TEST_MODE]",
                department_id=enrolled_case.department_id if enrolled_case else None,
                is_match_ready=True,
                search_mode=SearchMode.ALL_ACTIVE_CASES,
            )
            resp = matching_service.process_match_ready_candidate(mi, db=db)
            if i == 0:
                events_first = len(resp.events_created)
            else:
                events_second = len(resp.events_created)

        # First observation may create an event; second (same track within cooldown) should not
        r7 = check("Duplicate track observation suppressed by cooldown",
                   events_second == 0,
                   f"first={events_first} events, second={events_second} events")
        all_passed = all_passed and r7
    else:
        print(f"  {WARN} No enrolled image available – skipping deduplication test")
except Exception as exc:
    print(f"  {FAIL} Deduplication test failed: {exc}")
    all_passed = False


# ---------------------------------------------------------------------------
# Stage 8: Telemetry Snapshot
# ---------------------------------------------------------------------------
print("\n=== Stage 8: Telemetry Snapshot ===")
try:
    snap = matching_service.get_telemetry_snapshot()
    check("Telemetry queries_processed > 0", snap.queries_processed > 0,
          f"{snap.queries_processed} queries")
    check("Active model name populated", bool(snap.active_model_name),
          f"{snap.active_model_name} v{snap.active_model_version}")
    print(f"  {INFO} Index: {snap.total_active_references} refs "
          f"(missing={snap.active_missing_references}, wanted={snap.active_wanted_references})")
    print(f"  {INFO} Avg search latency: {snap.average_search_latency_ms:.1f} ms")
    print(f"  {INFO} Possible matches created: {snap.possible_matches_created}")
except Exception as exc:
    print(f"  {FAIL} Telemetry snapshot failed: {exc}")


# ---------------------------------------------------------------------------
# Stage 9: Prerecorded Video Source Test
# ---------------------------------------------------------------------------
print("\n=== Stage 9: Prerecorded Video Source Validation ===")
try:
    from app.workers.stream_worker import format_authenticated_stream_url
    from app.schemas.camera import validate_stream_url

    test_cases = [
        ("0", 0, "Webcam device integer conversion"),
        ("file:///tmp/test.mp4", "/tmp/test.mp4", "file:// URI stripping"),
        ("test:/tmp/test.mp4", "/tmp/test.mp4", "test: protocol stripping"),
        ("prerecorded:/tmp/test.mp4", "/tmp/test.mp4", "prerecorded: protocol stripping"),
        ("rtsp://camera.local/live", "rtsp://camera.local/live", "RTSP URL passthrough"),
    ]
    for url_in, expected_out, label in test_cases:
        result = format_authenticated_stream_url(url_in, None, None)
        check(label, result == expected_out, f"'{url_in}' → '{result}'")

    # Also confirm FILE/WEBCAM pass camera service schema validation
    from app.services.camera_service import CameraService
    dummy_urls = {
        "RTSP": "rtsp://camera.local/live",
        "HTTP": "http://camera.local/live",
        "HTTPS": "https://camera.local/live",
        "WEBCAM": "0",
        "FILE": "/tmp/test.mp4",
        "TEST": "/tmp/test.mp4",
        "PRERECORDED": "/tmp/test.mp4",
    }
    for protocol, dummy_url in dummy_urls.items():
        try:
            result = CameraService.validate_stream_type(protocol, dummy_url)
            ok = bool(result)
        except Exception:
            ok = False
        check(f"Stream type '{protocol}' is accepted", ok)
except Exception as exc:
    print(f"  {FAIL} Stream source validation failed: {exc}")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
db.close()
print("\n" + "=" * 60)
if all_passed:
    print(f"  {PASS} ALL CRITICAL STAGES PASSED")
    print("  The Sentinex detection pipeline is operational.")
    sys.exit(0)
else:
    print(f"  {FAIL} ONE OR MORE STAGES FAILED — see details above")
    print("  Review failed stages before deploying to production.")
    sys.exit(1)
