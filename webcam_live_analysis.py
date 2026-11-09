#!/usr/bin/env python3
"""
Sentinex – Live Webcam Analysis
=================================
Connects to the laptop webcam and runs the Sentinex identification pipeline
in real-time to detect whether any Missing or Wanted person from the enrolled
gallery appears in front of the camera.

Pipeline:
  1. Webcam capture  →  YuNet face detection (OpenCV 5)
  2. Face crop        →  AnalyticalFaceEmbeddingModel (512-dim, no torch)
  3. Embedding        →  Vector similarity search against 200 enrolled gallery faces
  4. Top matches      →  Decision threshold gating (HIGH_PRIORITY / POSSIBLE_MATCH)
  5. Annotated live display window + terminal alerts

Usage:
    python webcam_live_analysis.py [--camera 0] [--threshold 0.55] [--fps 2]

Controls:
    q  – quit
    r  – reload vector index from DB
    f  – freeze / resume frame
    +  – raise threshold
    -  – lower threshold
"""

from __future__ import annotations

import argparse
import sys
import os
import time
import textwrap
from datetime import datetime
from pathlib import Path
from collections import deque
from typing import Optional

import numpy as np
import cv2

# ---------------------------------------------------------------------------
# Bootstrap Sentinex backend on PYTHONPATH
# ---------------------------------------------------------------------------
SENTINEX_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SENTINEX_ROOT / "backend"))

try:
    import app.main  # registers all ORM models
    from app.database.session import SessionLocal
    from app.ai_engine.matching.models.embedding_model import AnalyticalFaceEmbeddingModel
    from app.ai_engine.matching.vector_search import VectorSearchIndex
    from app.ai_engine.schemas.matching import ReferenceEmbeddingRecord, SearchMode
    from app.models.face_embedding import FaceEmbeddingDB
    from app.models.reference_image import ReferenceImage
    from app.models.case import Case
except ImportError as e:
    print(f"[FATAL] Could not import Sentinex backend: {e}")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
YUNET_MODEL = str(SENTINEX_ROOT / "backend" / "face_detection_yunet_2023mar.onnx")
HIGH_PRIORITY_THRESHOLD = 0.85
POSSIBLE_MATCH_THRESHOLD = 0.70
MATCH_COOLDOWN_FRAMES = 30        # Skip re-reporting same case for N frames

# Colour palette (BGR)
COLOR_HIGH   = (0,   0,   255)    # Red  – HIGH PRIORITY
COLOR_MATCH  = (0, 140,   255)    # Orange – POSSIBLE MATCH
COLOR_SAFE   = (0, 200,     0)    # Green – no match
COLOR_PANEL  = (20,  20,   20)    # Dark sidebar background
COLOR_TEXT   = (220, 220, 220)
COLOR_YELLOW = (0,  215,   255)
COLOR_WHITE  = (255, 255, 255)

FONT       = cv2.FONT_HERSHEY_SIMPLEX
FONT_SMALL = 0.45
FONT_MED   = 0.55
FONT_LARGE = 0.72
LINE       = cv2.LINE_AA


# ---------------------------------------------------------------------------
# Vector Index Loader
# ---------------------------------------------------------------------------

def build_index() -> tuple[VectorSearchIndex, int]:
    """Load all active face embeddings from the DB into a fresh in-memory index."""
    print("[Index] Loading gallery embeddings from database…")
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
            ref  = db.query(ReferenceImage).filter(ReferenceImage.id == emb.reference_image_id).first()
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
        print(f"[Index] Loaded {loaded} reference embeddings "
              f"({idx.count_active(SearchMode.MISSING)} missing, "
              f"{idx.count_active(SearchMode.WANTED)} wanted)")
        return idx, loaded
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Face Detector (YuNet – pure OpenCV 5, no torch required)
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

    def detect(self, frame: np.ndarray) -> list[tuple[int, int, int, int, float]]:
        """Return list of (x, y, w, h, confidence) face boxes."""
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
            # Clip to frame
            x = max(0, x); y = max(0, y)
            fw = min(fw, w - x); fh = min(fh, h - y)
            if fw > 20 and fh > 20:
                results.append((x, y, fw, fh, conf))
        return results


# ---------------------------------------------------------------------------
# Sidebar Renderer
# ---------------------------------------------------------------------------

def render_sidebar(sidebar: np.ndarray, alerts: list[dict], index_size: int,
                   fps: float, threshold: float, frame_count: int) -> None:
    """Draw the right-hand info panel in-place."""
    sidebar[:] = COLOR_PANEL
    W = sidebar.shape[1]
    y = 18

    def text(msg, yy, color=COLOR_TEXT, scale=FONT_SMALL, bold=False):
        thickness = 2 if bold else 1
        cv2.putText(sidebar, msg, (8, yy), FONT, scale, color, thickness, LINE)

    # Header
    cv2.rectangle(sidebar, (0, 0), (W, 35), (40, 40, 40), -1)
    text("SENTINEX LIVE", y, COLOR_YELLOW, FONT_MED, bold=True)
    y += 30

    text(f"Gallery: {index_size} enrolled", y); y += 18
    text(f"Threshold: {threshold:.2f}", y); y += 18
    text(f"FPS: {fps:.1f}", y); y += 18
    text(f"Frame: {frame_count}", y); y += 24

    # Divider
    cv2.line(sidebar, (4, y), (W-4, y), (80, 80, 80), 1)
    y += 12

    text("RECENT ALERTS", y, COLOR_YELLOW, FONT_SMALL, bold=True); y += 20

    if not alerts:
        text("No alerts yet", y, (100, 100, 100)); y += 18
    else:
        for a in alerts[-8:]:
            state_color = COLOR_HIGH if a["state"] == "HIGH_PRIORITY" else COLOR_MATCH
            cat_icon = "M" if a["category"] == "MISSING" else "W"
            text(f"[{cat_icon}] {a['case_number']}", y, state_color, FONT_SMALL, bold=True); y += 16
            text(f"     score={a['score']:.3f}", y, COLOR_TEXT); y += 16
            text(f"     {a['ts']}", y, (120, 120, 120), 0.38); y += 20
            if y > sidebar.shape[0] - 30:
                break

    # Legend
    legy = sidebar.shape[0] - 75
    cv2.line(sidebar, (4, legy - 5), (W-4, legy - 5), (80, 80, 80), 1)
    cv2.rectangle(sidebar, (8, legy + 2), (22, legy + 14), COLOR_HIGH, -1)
    text("HIGH PRIORITY", legy + 14, COLOR_HIGH, 0.38); legy += 20
    cv2.rectangle(sidebar, (8, legy + 2), (22, legy + 14), COLOR_MATCH, -1)
    text("POSSIBLE MATCH", legy + 14, COLOR_MATCH, 0.38); legy += 20
    cv2.rectangle(sidebar, (8, legy + 2), (22, legy + 14), COLOR_SAFE, -1)
    text("No Match", legy + 14, COLOR_SAFE, 0.38)


# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------

def run(camera_id: int = 0, fps_target: float = 2.0,
        threshold: float = POSSIBLE_MATCH_THRESHOLD,
        display: bool = True):

    print(f"\n{'='*60}")
    print("  Sentinex – Live Webcam Missing/Wanted Person Detection")
    print(f"{'='*60}")
    print(f"  Camera device : /dev/video{camera_id}")
    print(f"  FPS target    : {fps_target}")
    print(f"  Match threshold: {threshold:.2f}")
    print(f"{'='*60}\n")

    # --- Load vector index ---
    index, index_size = build_index()

    # --- Embedding model ---
    emb_model = AnalyticalFaceEmbeddingModel()
    print(f"[Model] Using: {emb_model.model_name} v{emb_model.model_version} ({emb_model.embedding_dim}-dim)")

    # --- Face detector ---
    detector = YuNetFaceDetector(YUNET_MODEL)
    print("[Detector] YuNet face detector loaded (OpenCV 5 DNN)")

    # --- Camera ---
    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open camera {camera_id}")
        sys.exit(1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    print(f"[Camera] Opened /dev/video{camera_id} at 640×480\n")

    SIDEBAR_W = 250
    alerts: list[dict] = []
    cooldown: dict[int, int] = {}   # case_id → frames_until_rereport
    frame_count = 0
    frozen = False
    frozen_frame: Optional[np.ndarray] = None

    frame_times: deque = deque(maxlen=10)
    interval = 1.0 / fps_target
    last_process = 0.0

    print("Controls: [q] Quit  [r] Reload index  [f] Freeze  [+/-] Threshold\n")

    while True:
        t0 = time.monotonic()

        # --- Capture ---
        if not frozen:
            ret, frame = cap.read()
            if not ret:
                print("[WARN] Frame read failed, retrying…")
                time.sleep(0.1)
                continue
            display_frame = frame.copy()
        else:
            display_frame = frozen_frame.copy() if frozen_frame is not None else np.zeros((480, 640, 3), np.uint8)

        frame_count += 1

        # --- Rate limit processing ---
        do_process = (t0 - last_process) >= interval
        if do_process:
            last_process = t0
            frame_times.append(t0)

        # --- Tick down cooldowns ---
        for cid in list(cooldown):
            cooldown[cid] -= 1
            if cooldown[cid] <= 0:
                del cooldown[cid]

        # --- Detection & Matching (rate-limited) ---
        face_results: list[dict] = []
        if do_process:
            face_boxes = detector.detect(display_frame)
            for (x, y, w, h, conf) in face_boxes:
                face_crop = display_frame[y:y+h, x:x+w]
                if face_crop.size == 0:
                    continue

                # Resize to model input size
                face_resized = cv2.resize(face_crop, (112, 112))
                emb = emb_model.extract_embedding(face_resized)
                if emb is None:
                    continue

                # Search index
                top = index.search(
                    query_vector=emb,
                    top_k=5,
                    mode=SearchMode.ALL_ACTIVE_CASES,
                    metric="cosine",
                )

                best_score = 0.0
                best_case = None
                best_cat = None
                best_case_id = None

                for r in top:
                    if r.similarity_score > threshold and r.similarity_score > best_score:
                        if r.record.case_id not in cooldown:
                            best_score = r.similarity_score
                            best_case = r.record.case_number
                            best_cat = r.record.category
                            best_case_id = r.record.case_id

                state = "SAFE"
                if best_score >= HIGH_PRIORITY_THRESHOLD:
                    state = "HIGH_PRIORITY"
                elif best_score >= threshold:
                    state = "POSSIBLE_MATCH"

                face_results.append(dict(
                    box=(x, y, w, h),
                    conf=conf,
                    state=state,
                    score=best_score,
                    case_number=best_case,
                    category=best_cat,
                    case_id=best_case_id,
                ))

                if state in ("HIGH_PRIORITY", "POSSIBLE_MATCH") and best_case_id:
                    ts = datetime.now().strftime("%H:%M:%S")
                    alert = dict(
                        state=state,
                        case_number=best_case,
                        category=best_cat,
                        score=best_score,
                        ts=ts,
                    )
                    alerts.append(alert)
                    cooldown[best_case_id] = MATCH_COOLDOWN_FRAMES

                    # Terminal output
                    icon = "🔴" if state == "HIGH_PRIORITY" else "🟠"
                    cat_str = f"[{best_cat}]"
                    print(f"{icon} {ts}  {state:<20}  {cat_str:<10}  Case={best_case}  score={best_score:.4f}")

        # --- Draw Annotations ---
        for fr in face_results:
            x, y, w, h = fr["box"]
            state = fr["state"]
            color = COLOR_HIGH if state == "HIGH_PRIORITY" else (COLOR_MATCH if state == "POSSIBLE_MATCH" else COLOR_SAFE)

            cv2.rectangle(display_frame, (x, y), (x+w, y+h), color, 2)

            label_lines = []
            if state != "SAFE" and fr["case_number"]:
                label_lines.append(f"{state}")
                label_lines.append(f"{fr['category']} {fr['case_number']}")
                label_lines.append(f"score={fr['score']:.3f}")
            else:
                label_lines.append(f"face conf={fr['conf']:.2f}")

            lx, ly = x, max(0, y - 10 - 16 * len(label_lines))
            for i, line in enumerate(label_lines):
                lc = color if i == 0 else COLOR_WHITE
                cv2.putText(display_frame, line, (lx, ly + i * 16), FONT, FONT_SMALL, lc, 1, LINE)

        # --- FPS Overlay ---
        fps = (len(frame_times) - 1) / (frame_times[-1] - frame_times[0]) if len(frame_times) > 1 else 0.0
        cv2.putText(display_frame, f"Sentinex Live  {'[FROZEN]' if frozen else ''}",
                    (8, 20), FONT, FONT_SMALL, COLOR_YELLOW, 1, LINE)

        # --- Assemble Canvas ---
        sidebar = np.zeros((display_frame.shape[0], SIDEBAR_W, 3), dtype=np.uint8)
        render_sidebar(sidebar, alerts, index_size, fps, threshold, frame_count)
        canvas = np.hstack([display_frame, sidebar])

        if display:
            cv2.imshow("Sentinex – Live Webcam Analysis", canvas)

        # Headless heartbeat every 30 frames
        if not display and frame_count % 30 == 0:
            n_faces = len(face_results)
            ts_hb = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts_hb}] frame={frame_count:5d}  faces_detected={n_faces}  index={index_size}  threshold={threshold:.2f}")

        # --- Keyboard Handling ---
        key = cv2.waitKey(1) & 0xFF if display else 0xFF
        if key == ord("q"):
            print("\n[Quit] User requested exit.")
            break
        elif key == ord("r"):
            print("\n[Index] Reloading from database…")
            index, index_size = build_index()
        elif key == ord("f"):
            frozen = not frozen
            if frozen and not frozen_frame is not None:
                frozen_frame = display_frame.copy()
            elif frozen:
                frozen_frame = display_frame.copy()
            print(f"[Frame] {'Frozen' if frozen else 'Resumed'}")
        elif key == ord("+") or key == ord("="):
            threshold = min(0.99, threshold + 0.02)
            print(f"[Threshold] → {threshold:.2f}")
        elif key == ord("-") or key == ord("_"):
            threshold = max(0.30, threshold - 0.02)
            print(f"[Threshold] → {threshold:.2f}")

    cap.release()
    cv2.destroyAllWindows()
    print("\n[Done] Webcam session ended.")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sentinex – Live Webcam Missing/Wanted Person Detection")
    parser.add_argument("--camera",    type=int,   default=0,    help="Camera device index (default: 0)")
    parser.add_argument("--fps",       type=float, default=2.0,  help="Processing frames per second (default: 2.0)")
    parser.add_argument("--threshold", type=float, default=POSSIBLE_MATCH_THRESHOLD,
                        help=f"Similarity match threshold (default: {POSSIBLE_MATCH_THRESHOLD})")
    parser.add_argument("--no-display", action="store_true",
                        help="Run headless (no GUI window, terminal output only)")
    args = parser.parse_args()

    run(
        camera_id=args.camera,
        fps_target=args.fps,
        threshold=args.threshold,
        display=not args.no_display,
    )
