from __future__ import annotations

import asyncio
import logging
import time

import cv2
import numpy as np

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.database.session import get_db
from app.dependencies.auth import require_admin, require_police
from app.models.camera import Camera, CameraStatus
from app.models.user import User
from app.schemas.camera import (
    CameraCreateRequest,
    CameraHealthResponse,
    CameraHealthSummaryResponse,
    CameraResponse,
    CameraStatusUpdateRequest,
    CameraUpdateRequest,
)
from app.services.camera_service import CameraService
from app.services.stream_manager import stream_manager

router = APIRouter(prefix="/cameras", tags=["cameras"])


def get_camera_or_404(db: Session, camera_id: int) -> Camera:
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


def verify_camera_access(db: Session, user: User, camera: Camera) -> None:
    if not CameraService.can_access(user, camera):
        CameraService.log(
            db,
            user_id=user.id,
            action="UNAUTHORIZED_ACCESS_ATTEMPT",
            camera_id=camera.id,
            details=f"User {user.username} unauthorized access to camera {camera.id}",
        )
        raise HTTPException(status_code=403, detail="You do not have access to this camera")


# ---------------------------------------------------------------------------
# Camera Management Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=CameraResponse,
    status_code=201,
    summary="Register a new authorized camera",
)
def register_camera(
    payload: CameraCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """
    Register a new authorized CCTV/IP camera.
    Validates stream URL format (RTSP, HTTP, HTTPS) and prevents embedded credentials.
    Passwords are encrypted securely before storage and never returned in responses.
    """
    try:
        return CameraService.create(db, user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "",
    response_model=list[CameraResponse],
    summary="List all authorized cameras with filtering and pagination",
)
def list_cameras(
    department_id: int | None = Query(None, description="Filter by department ID"),
    status: str | None = Query(None, description="Filter by camera status"),
    search: str | None = Query(None, description="Search by camera name or location"),
    active_only: bool = Query(False, description="Filter active cameras only"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=200, description="Page size"),
    skip: int | None = Query(None, ge=0, description="Offset (alternative to page)"),
    limit: int | None = Query(None, ge=1, le=200, description="Limit (alternative to size)"),
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    """
    Retrieve registered cameras.
    Admins can view all cameras across departments.
    Department officers are strictly limited to cameras in their authorized jurisdiction.
    """
    query = db.query(Camera)

    if user.role != "ADMIN":
        query = query.filter(Camera.department_id == user.department_id)
    elif department_id is not None:
        query = query.filter(Camera.department_id == department_id)

    if status:
        query = query.filter(Camera.status == status.upper())

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            (Camera.camera_name.ilike(term))
            | (Camera.camera_code.ilike(term))
            | (Camera.location_name.ilike(term))
        )

    if active_only:
        query = query.filter(Camera.is_active.is_(True))

    offset_val = skip if skip is not None else (page - 1) * size
    limit_val = limit if limit is not None else size

    return query.order_by(Camera.id.asc()).offset(offset_val).limit(limit_val).all()


@router.get(
    "/health/summary",
    response_model=CameraHealthSummaryResponse,
    summary="Get aggregated health summary across all registered camera streams",
)
def get_health_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    """Return overview counts of cameras in ONLINE, CONNECTING, ERROR, and OFFLINE states."""
    if user.role == "ADMIN":
        cameras = db.query(Camera).all()
    else:
        cameras = db.query(Camera).filter(Camera.department_id == user.department_id).all()

    camera_ids = [c.id for c in cameras]
    summary = stream_manager.health.get_summary(camera_ids)
    return summary


@router.get(
    "/{camera_id}/health",
    response_model=CameraHealthResponse,
    summary="Get real-time health telemetry for a specific camera stream",
)
def get_camera_health(
    camera_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    """
    Return connection status, last seen timestamp, failure count, and last error
    for a specific authorized camera.
    """
    camera = get_camera_or_404(db, camera_id)
    verify_camera_access(db, user, camera)

    current = stream_manager.health.get(camera.id)
    last_seen = current.last_seen_at or camera.last_seen_at
    last_err = current.last_error or camera.last_error

    return {
        "camera_id": camera.id,
        "camera_code": camera.camera_code,
        "status": current.status,
        "connection_status": current.status,
        "current_state": current.status,
        "last_seen_at": last_seen,
        "failures": current.failures,
        "error_state": last_err,
        "last_error": last_err,
    }


@router.get(
    "/{camera_id}",
    response_model=CameraResponse,
    summary="Get camera details (credentials excluded)",
)
def get_camera_details(
    camera_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    """Return camera metadata without exposing sensitive credentials."""
    camera = get_camera_or_404(db, camera_id)
    verify_camera_access(db, user, camera)
    return camera


@router.put(
    "/{camera_id}",
    response_model=CameraResponse,
    summary="Update camera configuration",
)
def update_camera(
    camera_id: int,
    payload: CameraUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Update camera metadata, stream details, or location information."""
    camera = get_camera_or_404(db, camera_id)
    try:
        return CameraService.update(db, user, camera, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch(
    "/{camera_id}/status",
    response_model=CameraResponse,
    summary="Activate, deactivate, or update camera status",
)
def update_camera_status(
    camera_id: int,
    payload: CameraStatusUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Update active status of a camera."""
    camera = get_camera_or_404(db, camera_id)
    try:
        target_status = payload.status or (
            CameraStatus.ACTIVE if payload.is_active else CameraStatus.INACTIVE
        )
        return CameraService.set_status(db, user, camera, target_status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/{camera_id}",
    response_model=CameraResponse,
    summary="Soft delete/deactivate a camera",
)
async def delete_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """
    Logically deactivate (soft delete) a camera and stop any active stream worker.
    Historical camera records are preserved.
    """
    camera = get_camera_or_404(db, camera_id)
    await stream_manager.stop(camera.id)
    camera.is_active = False
    camera.status = CameraStatus.INACTIVE.value
    db.commit()
    db.refresh(camera)

    CameraService.log(
        db,
        user.id,
        "CAMERA_DEACTIVATED",
        camera.id,
        f"Camera '{camera.camera_name}' soft deactivated",
    )
    return camera


# ---------------------------------------------------------------------------
# Stream Control Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{camera_id}/start",
    response_model=CameraResponse,
    summary="Start monitoring an authorized camera stream",
)
async def start_camera_stream(
    camera_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """
    Launch an independent background worker to connect to the camera stream,
    monitor connectivity, and begin frame sampling.
    """
    camera = get_camera_or_404(db, camera_id)
    if not camera.is_active:
        raise HTTPException(status_code=400, detail="Inactive camera cannot be started")

    camera.status = CameraStatus.CONNECTING.value
    db.commit()

    decrypted_pwd = None
    if camera.encrypted_password:
        try:
            decrypted_pwd = CameraService.decrypt_password(camera.encrypted_password)
        except Exception:
            pass

    await stream_manager.start(camera, decrypted_password=decrypted_pwd)
    db.refresh(camera)

    CameraService.log(
        db,
        user.id,
        "STREAM_MONITORING_STARTED",
        camera.id,
        f"Started stream monitoring for camera {camera.camera_code}",
    )
    return camera


@router.post(
    "/{camera_id}/stop",
    response_model=CameraResponse,
    summary="Stop monitoring a camera stream",
)
async def stop_camera_stream(
    camera_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Stop active stream worker and mark the camera OFFLINE."""
    camera = get_camera_or_404(db, camera_id)
    await stream_manager.stop(camera.id)

    camera.status = CameraStatus.OFFLINE.value
    db.commit()
    db.refresh(camera)

    CameraService.log(
        db,
        user.id,
        "STREAM_MONITORING_STOPPED",
        camera.id,
        f"Stopped stream monitoring for camera {camera.camera_code}",
    )
    return camera


# ---------------------------------------------------------------------------
# MJPEG Live Stream Endpoint
# ---------------------------------------------------------------------------
# This endpoint streams annotated frames (with face-detection overlays) from
# an active camera directly to the browser as a multipart/x-mixed-replace
# MJPEG stream.  The frontend renders it via a plain <img src="..."> tag.
#
# Face detection uses the same pipeline already running in the AI engine;
# if the pipeline has not yet detected faces in the current frame we fall
# back to a lightweight OpenCV YuNet pass for immediate visual feedback.
# ---------------------------------------------------------------------------

_BOUNDARY = b"frame"
_CONTENT_TYPE = "multipart/x-mixed-replace; boundary=frame"


def _encode_frame(frame: np.ndarray) -> bytes:
    """JPEG-encode a BGR OpenCV frame and wrap it in an MJPEG boundary."""
    ret, buf = cv2.imencode(
        ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75]
    )
    if not ret:
        return b""
    jpg = buf.tobytes()
    header = (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n"
        b"Content-Length: " + str(len(jpg)).encode() + b"\r\n\r\n"
    )
    return header + jpg + b"\r\n"


def _draw_faces(frame: np.ndarray, detections) -> np.ndarray:
    """Draw bounding boxes around every detected face."""
    annotated = frame.copy()
    if detections is None:
        return annotated
    for det in detections:
        x1, y1, x2, y2 = int(det[0]), int(det[1]), int(det[2]), int(det[3])
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 220, 100), 2)
        cv2.putText(
            annotated, "FACE DETECTED", (x1, max(y1 - 8, 12)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 100), 1, cv2.LINE_AA,
        )
    return annotated


async def _mjpeg_generator(camera: Camera, user: User):
    """
    Async generator producing MJPEG frames from the stream_manager queue.

    Priority order for frame source:
      1. Latest frame already in stream_manager queue (zero extra camera opens)
      2. If queue is empty (stream not started yet) — yield a static placeholder

    Face detection annotation runs the existing pipeline overlay; if the full
    pipeline hasn't processed the frame yet, a lightweight YuNet pass runs
    inline for visual feedback only (not used for matching).
    """
    from app.services.stream_manager import stream_manager as sm  # noqa: PLC0415

    # Load YuNet for inline face annotation (reuse model_loader cache)
    try:
        from app.ai_engine.detection.model_loader import load_face_model  # noqa: PLC0415
        face_model = load_face_model("cpu")
    except Exception:
        face_model = None

    camera_id = camera.id
    last_yield = time.monotonic()
    min_interval = 0.1  # 10 fps max to the browser

    while True:
        frame_meta = sm.get_latest_frame(camera_id)

        if frame_meta is None:
            # Stream not started or queue empty — send a placeholder
            placeholder = np.zeros((240, 320, 3), dtype=np.uint8)
            cv2.putText(
                placeholder, "Camera stream not active", (20, 120),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (100, 100, 100), 1,
            )
            cv2.putText(
                placeholder, "Start the camera first", (20, 145),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 80, 80), 1,
            )
            chunk = _encode_frame(placeholder)
            if chunk:
                yield chunk
            await asyncio.sleep(1.0)
            continue

        now = time.monotonic()
        if now - last_yield < min_interval:
            await asyncio.sleep(min_interval - (now - last_yield))
            continue
        last_yield = time.monotonic()

        frame = frame_meta.frame
        if frame is None:
            await asyncio.sleep(0.1)
            continue

        # Annotate with face detections
        annotated = frame.copy()
        try:
            if face_model is not None:
                boxes, probs, _ = face_model.detect(frame, landmarks=False)
                if boxes is not None and len(boxes):
                    detections = []
                    for b, p in zip(boxes, (probs if probs is not None else [])):
                        if p >= 0.50:
                            detections.append(b)
                    annotated = _draw_faces(annotated, detections)
        except Exception as exc:
            logger.debug("[MJPEG] Face annotation error: %s", exc)

        # Overlay camera info
        ts = frame_meta.captured_at.strftime("%H:%M:%S") if frame_meta.captured_at else ""
        cv2.putText(
            annotated,
            f"SENTINEX LIVE | {camera.camera_name} | {ts}",
            (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA,
        )
        cv2.putText(
            annotated,
            f"SENTINEX LIVE | {camera.camera_name} | {ts}",
            (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA,
        )

        chunk = _encode_frame(annotated)
        if chunk:
            yield chunk


@router.get(
    "/{camera_id}/stream",
    summary="MJPEG live stream with face-detection overlays",
    response_class=StreamingResponse,
    tags=["cameras"],
)
async def stream_camera_mjpeg(
    camera_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    """
    Stream an annotated MJPEG feed from an active camera.

    Use as a plain ``<img>`` src in the frontend:
        ``<img src="/api/cameras/{id}/stream" />``

    Requires POLICE or ADMIN role.  Respects department-level access control.
    """
    camera = get_camera_or_404(db, camera_id)
    verify_camera_access(db, user, camera)

    return StreamingResponse(
        _mjpeg_generator(camera, user),
        media_type=_CONTENT_TYPE,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx proxy buffering
        },
    )


@router.get(
    "/{camera_id}/stream-status",
    summary="Get real-time stream and detection status for Live Demo panel",
)
def get_stream_status(
    camera_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_police),
):
    """
    Return JSON status used by the Live Camera Demo panel:
    stream health, latest frame timestamp, whether the pipeline is active.
    """
    from app.services.stream_manager import stream_manager as sm  # noqa: PLC0415
    from app.ai_engine.pipeline.processing_pipeline import video_pipeline  # noqa: PLC0415

    camera = get_camera_or_404(db, camera_id)
    verify_camera_access(db, user, camera)

    health = sm.health.get(camera_id)
    is_pipeline_running = video_pipeline.is_running(camera_id)

    frame_meta = sm.get_latest_frame(camera_id)
    last_frame_at = (
        frame_meta.captured_at.isoformat() if frame_meta and frame_meta.captured_at else None
    )

    return {
        "camera_id": camera_id,
        "camera_name": camera.camera_name,
        "stream_type": camera.stream_type,
        "stream_url": camera.stream_url,  # Only the URL scheme, not credentials
        "db_status": camera.status,
        "live_status": health.status,
        "is_streaming": sm.is_running(camera_id),
        "is_pipeline_active": is_pipeline_running,
        "last_frame_at": last_frame_at,
        "last_error": health.last_error,
        "failures": health.failures,
    }
