#!/usr/bin/env python3
"""
Sentinex – Live Wanted/Missing Person Scanner & Alerting Runtime
================================================================
Continuously scans a camera feed. Every detected face is converted to a
512-dim embedding and compared against the enrolled gallery of Missing and
Wanted persons.

  * If a face MATCHES an enrolled Missing/Wanted person (similarity >= the
    operational threshold) the system raises an ALERT and persists it with
    the TIMESTAMP and the LOCATION (camera + coordinates + department).

  * If a face does NOT match any enrolled person it is IGNORED — no alert,
    no match-event, nothing is written for that face.

Pipeline
--------
  1. Frame capture            (webcam / video file / image folder)
  2. YuNet face detection      (OpenCV DNN, no torch required)
  3. Face crop → embedding     (configured pretrained face recognizer, 512-dim)
  4. Cosine search vs gallery  (live embeddings loaded from the database)
  5. Threshold gating:
        score >= HIGH_PRIORITY_THRESHOLD   → CRITICAL alert
        score >= MATCH_THRESHOLD           → HIGH alert
        otherwise                          → IGNORED (no record)
  6. Persist match event + alert with time & location
  7. Annotated live window + terminal alert log

Usage
-----
    # Laptop webcam against a named camera location
    python live_scan_alert.py --camera 0 --location "Central Station - Gate A"

    # Use one of the seeded DB cameras (fills location + GPS + department)
    python live_scan_alert.py --camera 0 --db-camera CAM-TERM-01

    # Scan a folder of images instead of a live device
    python live_scan_alert.py --images "/path/to/folder"

    # Headless (no GUI) — useful for servers / testing
    python live_scan_alert.py --camera 0 --db-camera CAM-TERM-01 --no-display

Controls (GUI mode)
-------------------
    q – quit         r – reload gallery index      f – freeze frame
    + / - – raise / lower threshold                s – dump session alert summary
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

import numpy as np
import cv2

# ---------------------------------------------------------------------------
# Bootstrap Sentinex backend on PYTHONPATH
# ---------------------------------------------------------------------------
SENTINEX_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SENTINEX_ROOT / "backend"))

try:
    import app.main  # noqa: F401  (registers all ORM models)
    from app.database.session import SessionLocal
    from app.ai_engine.matching.models.embedding_model import get_embedding_model
    from app.ai_engine.matching.vector_search import VectorSearchIndex
    from app.ai_engine.schemas.matching import ReferenceEmbeddingRecord, SearchMode
    from app.models.face_embedding import FaceEmbeddingDB
    from app.models.reference_image import ReferenceImage
    from app.models.case import Case
    from app.models.camera import Camera
    from app.models.department import Department
    from app.models.match_event import MatchEventDB
    from app.models.alert import AlertDB, AlertPriority, AlertStatus
except ImportError as exc:  # pragma: no cover
    print(f"[FATAL] Could not import Sentinex backend: {exc}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
YUNET_MODEL = str(SENTINEX_ROOT / "backend" / "face_detection_yunet_2023mar.onnx")

# Decision thresholds (mirror matching_settings / Module 7 policy)
HIGH_PRIORITY_THRESHOLD = 0.85   # → CRITICAL alert
MATCH_THRESHOLD = 0.45           # held-out benchmark: zero FP, 98.97% enrolled recall
DEFAULT_THRESHOLD = MATCH_THRESHOLD
DEFAULT_FALLBACK_DEPARTMENT_ID = 1

# Re-alert suppression: don't re-alert the same case within this many seconds
ALERT_COOLDOWN_SECONDS = 30.0

# Colours (BGR)
COLOR_HIGH = (0, 0, 255)       # Red
COLOR_MATCH = (0, 140, 255)    # Orange
COLOR_SAFE = (0, 200, 0)       # Green
COLOR_PANEL = (20, 20, 20)
COLOR_TEXT = (220, 220, 220)
COLOR_YELLOW = (0, 215, 255)
COLOR_WHITE = (255, 255, 255)
COLOR_GREY = (120, 120, 120)

FONT = cv2.FONT_HERSHEY_SIMPLEX
LINE = cv2.LINE_AA


# ---------------------------------------------------------------------------
# Camera location resolution
# ---------------------------------------------------------------------------

class CameraContext:
    """Resolves the physical location metadata attached to every alert."""

    def __init__(
        self,
        db,
        db_camera_code: str | None = None,
        location_override: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
    ) -> None:
        self.camera_id: int | None = None
        self.camera_code: str | None = None
        self.location_name: str | None = location_override
        self.latitude: float | None = lat
        self.longitude: float | None = lon
        self.department_id: int = DEFAULT_FALLBACK_DEPARTMENT_ID

        if db_camera_code:
            cam = (
                db.query(Camera)
                .filter(Camera.camera_code == db_camera_code)
                .first()
            )
            if not cam:
                raise SystemExit(
                    f"[FATAL] Camera code '{db_camera_code}' not found in the database."
                )
            self.camera_id = cam.id
            self.camera_code = cam.camera_code
            # Explicit override wins over DB value
            self.location_name = location_override or cam.location_name or cam.camera_name
            self.latitude = lat if lat is not None else cam.latitude
            self.longitude = lon if lon is not None else cam.longitude
            self.department_id = cam.department_id
        elif location_override:
            self.location_name = location_override
        else:
            self.location_name = "Laptop Webcam (unregistered location)"

    def describe(self) -> str:
        parts = [self.location_name or "Unknown location"]
        if self.latitude is not None and self.longitude is not None:
            parts.append(f"({self.latitude:.5f}, {self.longitude:.5f})")
        if self.camera_code:
            parts.append(f"[{self.camera_code}]")
        return " ".join(parts)


# ---------------------------------------------------------------------------
# Gallery index
# ---------------------------------------------------------------------------

def build_index():
    """Load all active enrolled embeddings from the DB into a fresh index."""
    print("[Index] Loading enrolled gallery from database…")
    db = SessionLocal()
    try:
        embeddings = (
            db.query(FaceEmbeddingDB)
            .filter(FaceEmbeddingDB.is_active == True)  # noqa: E712
            .all()
        )
        idx = VectorSearchIndex()
        loaded = 0
        for emb in embeddings:
            ref = db.query(ReferenceImage).filter(ReferenceImage.id == emb.reference_image_id).first()
            case = db.query(Case).filter(Case.id == emb.case_id).first()
            if ref and case and case.is_active and ref.is_active:
                vec = np.frombuffer(emb.vector_bytes, dtype=np.float32)
                rec = ReferenceEmbeddingRecord(
                    embedding_id=emb.embedding_reference,
                    image_id=ref.id,
                    case_id=case.id,
                    case_number=case.case_number,
                    category=case.category,
                    department_id=case.department_id,
                    model_name=emb.model_name,
                    model_version=emb.model_version,
                    embedding_dim=emb.embedding_dim,
                )
                idx.add_embedding(vector=vec, record=rec)
                loaded += 1
        print(
            f"[Index] Loaded {loaded} embeddings "
            f"({idx.count_active(SearchMode.MISSING)} missing, "
            f"{idx.count_active(SearchMode.WANTED)} wanted)"
        )
        return idx, loaded
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Face detector (YuNet, pure OpenCV)
# ---------------------------------------------------------------------------

class YuNetFaceDetector:
    def __init__(self, model_path: str, input_size=(640, 480),
                 conf_threshold=0.60, nms_threshold=0.30, top_k=20):
        if not Path(model_path).exists():
            raise FileNotFoundError(f"YuNet ONNX model not found: {model_path}")
        self._detector = cv2.FaceDetectorYN.create(
            model_path, "", input_size, conf_threshold, nms_threshold, top_k
        )
        self._current_size = input_size

    def detect(self, frame: np.ndarray):
        """Return list of (x, y, w, h, confidence)."""
        h, w = frame.shape[:2]
        if (w, h) != self._current_size:
            self._detector.setInputSize((w, h))
            self._current_size = (w, h)
        count, faces = self._detector.detect(frame)
        if faces is None or count == 0:
            return []
        results = []
        for face in faces:
            x, y, fw, fh, conf = int(face[0]), int(face[1]), int(face[2]), int(face[3]), float(face[14])
            x, y = max(0, x), max(0, y)
            fw = min(fw, w - x)
            fh = min(fh, h - y)
            if fw > 20 and fh > 20:
                results.append((x, y, fw, fh, conf))
        return results


# ---------------------------------------------------------------------------
# Alert persistence (time + location)
# ---------------------------------------------------------------------------

class AlertWriter:
    """Persists match events and alerts with timestamp and location metadata."""

    def __init__(self, ctx: CameraContext, model_name: str, model_version: str):
        self.ctx = ctx
        self.model_name = model_name
        self.model_version = model_version
        self._db = SessionLocal()

    def close(self) -> None:
        try:
            self._db.close()
        except Exception:
            pass

    def _next_alert_number(self) -> str:
        # ALT-<year>-<6 digits>, derived from the current max for this year
        year = datetime.now().year
        prefix = f"ALT-{year}-"
        last = (
            self._db.query(AlertDB)
            .filter(AlertDB.alert_number.like(f"{prefix}%"))
            .order_by(AlertDB.id.desc())
            .first()
        )
        n = 1
        if last:
            m = re.search(r"(\d+)$", last.alert_number)
            if m:
                n = int(m.group(1)) + 1
        return f"{prefix}{n:06d}"

    def record_alert(
        self,
        case: Case,
        score: float,
        state: str,
        face_box: tuple[int, int, int, int],
    ) -> dict:
        """
        Writes a MatchEventDB + AlertDB row for a confirmed gallery match and
        returns a dict describing the alert (for the UI/terminal).
        """
        now = datetime.utcnow()
        category = case.category
        camera_id = self.ctx.camera_id if self.ctx.camera_id is not None else 0
        priority = (
            AlertPriority.CRITICAL.value
            if state == "HIGH_PRIORITY"
            else AlertPriority.HIGH.value
        )
        event_id = f"EVT-{uuid4().hex[:12].upper()}"

        result = {
            "state": state,
            "case_number": case.case_number,
            "category": category,
            "score": score,
            "priority": priority,
            "camera_code": self.ctx.camera_code,
            "location": self.ctx.location_name,
            "latitude": self.ctx.latitude,
            "longitude": self.ctx.longitude,
            "time_utc": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "time_local": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "alert_number": None,
            "event_id": event_id,
        }

        try:
            # 1. Match event (Module 7 record)
            self._db.add(
                MatchEventDB(
                    event_id=event_id,
                    candidate_id=f"LIVE-{uuid4().hex[:8].upper()}",
                    track_id=f"TRK-{uuid4().hex[:8].upper()}",
                    camera_id=camera_id,
                    case_id=case.id,
                    case_number=case.case_number,
                    category=category,
                    similarity_score=float(score),
                    query_quality_score=0.85,
                    candidate_ranking_score=float(score),
                    rank=1,
                    decision_state=state,
                    status="PENDING_REVIEW",
                    model_name=self.model_name,
                    model_version=self.model_version,
                    camera_location=self.ctx.location_name,
                )
            )

            # 2. Alert row — timestamp + location are the core of this record
            alert_number = self._next_alert_number()
            self._db.add(
                AlertDB(
                    alert_number=alert_number,
                    # Legacy alerts table requires a review_event_id; live scanner
                    # alerts are un-reviewed detections, so we link the match event
                    # and use 0 to denote "no human review event yet".
                    match_event_id=event_id,
                    review_event_id=0,
                    case_id=case.id,
                    case_number=case.case_number,
                    category=category,
                    originating_department_id=case.department_id,
                    detected_camera_id=self.ctx.camera_id,
                    detected_camera_code=self.ctx.camera_code,
                    detected_location=self.ctx.location_name,
                    nearest_department_id=self.ctx.department_id,
                    routing_reason="Live scanner alert routed to the department responsible for the camera location",
                    priority=priority,
                    status=AlertStatus.CREATED.value,
                    observation_count=1,
                    last_observation_at=now,
                )
            )
            self._db.commit()
            result["alert_number"] = alert_number
            result["persisted"] = True
        except Exception as exc:  # pragma: no cover
            self._db.rollback()
            print(f"[DB ERROR] Could not persist alert: {exc}")
            result["persisted"] = False

        return result


# ---------------------------------------------------------------------------
# Sidebar rendering
# ---------------------------------------------------------------------------

def render_sidebar(sidebar, alerts, index_size, fps, threshold, frame_count, ctx_str):
    sidebar[:] = COLOR_PANEL
    W = sidebar.shape[1]
    y = 18

    def text(msg, yy, color=COLOR_TEXT, scale=0.45, bold=False):
        cv2.putText(sidebar, msg, (8, yy), FONT, scale, color, 2 if bold else 1, LINE)

    cv2.rectangle(sidebar, (0, 0), (W, 35), (40, 40, 40), -1)
    text("SENTINEX LIVE SCAN", y, COLOR_YELLOW, 0.55, bold=True)
    y += 30

    text(f"Gallery: {index_size} enrolled", y); y += 17
    text(f"Threshold: {threshold:.2f}", y); y += 17
    text(f"FPS: {fps:.1f}", y); y += 17
    text(f"Frame: {frame_count}", y); y += 17
    # Wrap the location string across the panel width
    loc = ctx_str
    while loc:
        text(loc[:34], y, COLOR_GREY, 0.38); y += 13
        loc = loc[34:]
    y += 8

    cv2.line(sidebar, (4, y), (W - 4, y), (80, 80, 80), 1)
    y += 12
    text("ALERTS (match only)", y, COLOR_YELLOW, 0.45, bold=True); y += 18

    if not alerts:
        text("No matches — all faces ignored", y, (100, 100, 100), 0.38); y += 16
    else:
        for a in alerts[-7:]:
            color = COLOR_HIGH if a["state"] == "HIGH_PRIORITY" else COLOR_MATCH
            icon = "M" if a["category"] == "MISSING" else "W"
            text(f"[{icon}] {a['case_number']}", y, color, 0.42, bold=True); y += 15
            text(f"score={a['score']:.3f}", y, COLOR_TEXT, 0.40); y += 14
            text(f"{a['time_local']}", y, COLOR_GREY, 0.36); y += 13
            if a.get("location"):
                text(f"{str(a['location'])[:32]}", y, COLOR_GREY, 0.34); y += 13
            y += 5
            if y > sidebar.shape[0] - 40:
                break

    legy = sidebar.shape[0] - 62
    cv2.line(sidebar, (4, legy - 6), (W - 4, legy - 6), (80, 80, 80), 1)
    cv2.rectangle(sidebar, (8, legy + 1), (22, legy + 13), COLOR_HIGH, -1)
    text("CRITICAL (>=0.85)", legy + 13, COLOR_HIGH, 0.36); legy += 18
    cv2.rectangle(sidebar, (8, legy + 1), (22, legy + 13), COLOR_MATCH, -1)
    text("ALERT (>=thresh)", legy + 13, COLOR_MATCH, 0.36); legy += 18
    cv2.rectangle(sidebar, (8, legy + 1), (22, legy + 13), COLOR_SAFE, -1)
    text("IGNORED (no match)", legy + 13, COLOR_SAFE, 0.36)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def _process_frame(frame, detector, emb_model, index, threshold, writer,
                   ctx, alerts, cooldown, db_case_cache):
    """Detect faces, match them, alert on matches, ignore everything else."""
    face_results = []
    boxes = detector.detect(frame)

    for (x, y, w, h, conf) in boxes:
        face_crop = frame[y:y + h, x:x + w]
        if face_crop.size == 0:
            continue

        emb = emb_model.extract_embedding(face_crop)
        if emb is None or not np.isfinite(emb).all() or np.linalg.norm(emb) < 1e-8:
            continue

        top = index.search(query_vector=emb, top_k=5,
                           mode=SearchMode.ALL_ACTIVE_CASES, metric="cosine")

        best_score = 0.0
        best_rec = None
        for r in top:
            if r.similarity_score > best_score:
                best_score = r.similarity_score
                best_rec = r.record

        # ---- Threshold gate -------------------------------------------------
        if best_rec is None or best_score < threshold:
            # NOT a match → IGNORE. No DB write, no alert.
            face_results.append(dict(box=(x, y, w, h), conf=conf,
                                     state="SAFE", score=best_score,
                                     case_number=None, category=None, case_id=None))
            continue

        # ---- Confirmed match → alert ---------------------------------------
        state = "HIGH_PRIORITY" if best_score >= HIGH_PRIORITY_THRESHOLD else "POSSIBLE_MATCH"
        case_id = best_rec.case_id

        # Cooldown suppression: same case not re-alerted within the window
        now = time.time()
        if now - cooldown.get(case_id, 0.0) < ALERT_COOLDOWN_SECONDS:
            face_results.append(dict(box=(x, y, w, h), conf=conf, state=state,
                                     score=best_score, case_number=best_rec.case_number,
                                     category=best_rec.category, case_id=case_id,
                                     suppressed=True))
            continue

        case = db_case_cache.get(case_id)
        if case is None:
            _db = SessionLocal()
            try:
                case = _db.query(Case).filter(Case.id == case_id).first()
            finally:
                _db.close()
            db_case_cache[case_id] = case
        if case is None:
            continue

        alert = writer.record_alert(case, best_score, state, (x, y, w, h))
        cooldown[case_id] = now
        alerts.append(alert)

        face_results.append(dict(box=(x, y, w, h), conf=conf, state=state,
                                 score=best_score, case_number=best_rec.case_number,
                                 category=best_rec.category, case_id=case_id))

        # Terminal alert line — time + location + identity
        icon = "🔴" if state == "HIGH_PRIORITY" else "🟠"
        print(
            f"{icon} ALERT {alert['alert_number']}  "
            f"[{best_rec.category}] {best_rec.case_number}  "
            f"score={best_score:.4f}  "
            f"time={alert['time_local']}  "
            f"loc={alert['location']}"
            + (f"  GPS=({alert['latitude']:.5f},{alert['longitude']:.5f})"
               if alert['latitude'] is not None and alert['longitude'] is not None else "")
        )

    return face_results


def run(camera_id: int = 0, fps_target: float = 2.0,
        threshold: float = DEFAULT_THRESHOLD, display: bool = True,
        db_camera_code: str | None = None, location: str | None = None,
        images_dir: str | None = None, lat: float | None = None, lon: float | None = None):

    print(f"\n{'=' * 66}")
    print("  Sentinex – Live Wanted/Missing Person Scanner")
    print(f"{'=' * 66}")

    # --- Location context ---
    db = SessionLocal()
    try:
        ctx = CameraContext(db, db_camera_code=db_camera_code,
                            location_override=location, lat=lat, lon=lon)
    finally:
        db.close()
    ctx_str = ctx.describe()
    print(f"  Location      : {ctx_str}")
    print(f"  Source        : {images_dir if images_dir else f'/dev/video{camera_id}'}")
    print(f"  Threshold     : {threshold:.2f} (>= {HIGH_PRIORITY_THRESHOLD:.2f} = CRITICAL)")
    print(f"  Cooldown      : {ALERT_COOLDOWN_SECONDS:.0f}s per case")
    print(f"{'=' * 66}\n")

    # --- Load components ---
    index, index_size = build_index()
    emb_model = get_embedding_model()
    print(f"[Model] {emb_model.model_name} v{emb_model.model_version} ({emb_model.embedding_dim}-dim)")
    detector = YuNetFaceDetector(YUNET_MODEL)
    print("[Detector] YuNet loaded")
    writer = AlertWriter(ctx, emb_model.model_name, emb_model.model_version)
    print("[Alerts] Persistence enabled (match_events + alerts)\n")

    alerts: list[dict] = []
    cooldown: dict[int, float] = {}
    db_case_cache: dict[int, Case] = {}
    frame_count = 0

    try:
        # ---------- Image-folder mode ----------
        if images_dir:
            folder = Path(images_dir)
            if not folder.is_dir():
                raise SystemExit(f"[FATAL] Not a directory: {folder}")
            files = sorted(p for p in folder.iterdir()
                           if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"})
            print(f"[Scan] Processing {len(files)} images from {folder}\n")
            matched = ignored = 0
            for i, fp in enumerate(files, 1):
                frame = cv2.imread(str(fp), cv2.IMREAD_COLOR)
                if frame is None:
                    continue
                frame_count += 1
                results = _process_frame(frame, detector, emb_model, index, threshold,
                                         writer, ctx, alerts, cooldown, db_case_cache)
                hit = any(r["state"] != "SAFE" for r in results)
                if hit:
                    matched += 1
                else:
                    ignored += 1
                # Annotate
                for fr in results:
                    x, y, w, h = fr["box"]
                    color = (COLOR_HIGH if fr["state"] == "HIGH_PRIORITY"
                             else COLOR_MATCH if fr["state"] == "POSSIBLE_MATCH" else COLOR_SAFE)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                    label = (f"{fr['state']} {fr['category']} {fr['case_number']}"
                             if fr["state"] != "SAFE" else "IGNORED")
                    cv2.putText(frame, label, (x, max(15, y - 6)), FONT, 0.5, color, 1, LINE)
                out = SENTINEX_ROOT / "evidence_store" / "live_scan" / fp.name
                out.parent.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(out), frame)
                status = "MATCH" if hit else "ignored"
                print(f"  [{i:3d}/{len(files)}] {fp.name:<28} faces={len(results)}  -> {status}")

            print(f"\n[Summary] images={len(files)} matched={matched} ignored={ignored} alerts={len(alerts)}")
            return

        # ---------- Live capture mode ----------
        src = int(camera_id)
        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            raise SystemExit(f"[FATAL] Cannot open video source {src}")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        print(f"[Capture] Opened /dev/video{camera_id} @640x480")
        print("Controls: [q]uit  [r]eload  [f]reeze  [+/-]threshold  [s]ummary\n")

        SIDEBAR_W = 260
        frame_times: deque = deque(maxlen=10)
        interval = 1.0 / fps_target
        last_process = 0.0
        frozen = False
        frozen_frame: Optional[np.ndarray] = None
        face_results: list[dict] = []

        while True:
            t0 = time.monotonic()

            if not frozen:
                ret, frame = cap.read()
                if not ret:
                    print("[WARN] Frame read failed, retrying…")
                    time.sleep(0.1)
                    continue
                display_frame = frame.copy()
            else:
                display_frame = frozen_frame.copy() if frozen_frame is not None \
                    else np.zeros((480, 640, 3), np.uint8)

            frame_count += 1
            do_process = (t0 - last_process) >= interval
            if do_process:
                last_process = t0
                frame_times.append(t0)
                face_results = _process_frame(display_frame, detector, emb_model, index,
                                              threshold, writer, ctx, alerts, cooldown,
                                              db_case_cache)

            # Draw annotations
            for fr in face_results:
                x, y, w, h = fr["box"]
                state = fr["state"]
                color = (COLOR_HIGH if state == "HIGH_PRIORITY"
                         else COLOR_MATCH if state == "POSSIBLE_MATCH" else COLOR_SAFE)
                cv2.rectangle(display_frame, (x, y), (x + w, y + h), color, 2)
                if state != "SAFE" and fr["case_number"]:
                    lines = [f"{state}", f"{fr['category']} {fr['case_number']}",
                             f"score={fr['score']:.3f}"]
                else:
                    lines = [f"IGNORED (conf={fr['conf']:.2f})"]
                ly = max(0, y - 8 - 15 * len(lines))
                for i, ln in enumerate(lines):
                    cv2.putText(display_frame, ln, (x, ly + i * 15), FONT, 0.45,
                                color if i == 0 else COLOR_WHITE, 1, LINE)

            fps = (len(frame_times) - 1) / (frame_times[-1] - frame_times[0]) \
                if len(frame_times) > 1 else 0.0
            cv2.putText(display_frame, f"Sentinex Live Scan {'[FROZEN]' if frozen else ''}",
                        (8, 20), FONT, 0.5, COLOR_YELLOW, 1, LINE)

            if display:
                sidebar = np.zeros((display_frame.shape[0], SIDEBAR_W, 3), dtype=np.uint8)
                render_sidebar(sidebar, alerts, index_size, fps, threshold, frame_count, ctx_str)
                cv2.imshow("Sentinex – Live Scan & Alert", np.hstack([display_frame, sidebar]))
            elif frame_count % 30 == 0:
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"[{ts}] frame={frame_count:5d} faces={len(face_results)} "
                      f"alerts={len(alerts)} index={index_size}")

            key = cv2.waitKey(1) & 0xFF if display else 0xFF
            if key == ord("q"):
                break
            elif key == ord("r"):
                index, index_size = build_index()
                cooldown.clear()
                db_case_cache.clear()
            elif key == ord("f"):
                frozen = not frozen
                if frozen:
                    frozen_frame = display_frame.copy()
            elif key in (ord("+"), ord("=")):
                threshold = min(0.99, threshold + 0.02)
                print(f"[Threshold] -> {threshold:.2f}")
            elif key in (ord("-"), ord("_")):
                threshold = max(0.30, threshold - 0.02)
                print(f"[Threshold] -> {threshold:.2f}")
            elif key == ord("s"):
                print(f"\n[Session] frames={frame_count} alerts={len(alerts)}")
                for a in alerts:
                    print(f"   {a['alert_number']}  {a['case_number']}  "
                          f"{a['score']:.3f}  {a['time_local']}  {a['location']}")

        cap.release()
        cv2.destroyAllWindows()

    finally:
        writer.close()

    print(f"\n[Done] frames={frame_count}  alerts raised={len(alerts)}")
    if alerts:
        print("Alerts persisted with timestamp + location:")
        for a in alerts:
            print(f"   {a['alert_number']}  {a['category']} {a['case_number']}  "
                  f"score={a['score']:.4f}  {a['time_utc']}  {a['location']}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Sentinex – Live Wanted/Missing Person Scanner & Alerting"
    )
    parser.add_argument("--camera", type=int, default=0, help="Camera device index (default: 0)")
    parser.add_argument("--fps", type=float, default=2.0, help="Processing FPS (default: 2.0)")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help=f"Match threshold (default: {DEFAULT_THRESHOLD})")
    parser.add_argument("--db-camera", dest="db_camera", default=None,
                        help="DB camera_code to inherit location/GPS/department (e.g. CAM-TERM-01)")
    parser.add_argument("--location", default=None,
                        help="Free-text location label (used if no --db-camera)")
    parser.add_argument("--images", default=None,
                        help="Scan a folder of images instead of a live camera")
    parser.add_argument("--lat", type=float, default=None, help="Latitude override")
    parser.add_argument("--lon", type=float, default=None, help="Longitude override")
    parser.add_argument("--no-display", action="store_true", help="Headless mode")
    args = parser.parse_args()

    run(
        camera_id=args.camera,
        fps_target=args.fps,
        threshold=args.threshold,
        display=not args.no_display,
        db_camera_code=args.db_camera,
        location=args.location,
        images_dir=args.images,
        lat=args.lat,
        lon=args.lon,
    )
