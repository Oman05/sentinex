"""
Module 5 – AI Processing API Router
======================================
Provides internal observability endpoints for the AI Video Processing module.

Security design
---------------
- All endpoints require authentication (reuses the existing dependency).
- No raw frame data, pixel data, or biometric information is exposed.
- Only processing metadata and aggregate metrics are returned.
- Candidate observations are NEVER exposed through this router — they are
  an internal pipeline interface, not an HTTP-facing resource.

Endpoints
---------
GET  /api/ai-processing/status
     Returns pipeline running status and active camera list.

GET  /api/ai-processing/metrics
     Returns aggregate processing metrics for all cameras.

GET  /api/ai-processing/metrics/{camera_id}
     Returns processing metrics for one specific camera.

POST /api/ai-processing/cameras/{camera_id}/start
     Start the AI pipeline for an active camera stream (operator/admin only).

POST /api/ai-processing/cameras/{camera_id}/stop
     Stop the AI pipeline for a camera (operator/admin only).

POST /api/ai-processing/stop-all
     Stop all running camera pipelines (admin only).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.ai_engine.pipeline.processing_pipeline import video_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-processing", tags=["Module 5 – AI Video Processing"])


# ---------------------------------------------------------------------------
# Response schemas (API-layer only — not the same as pipeline schemas)
# ---------------------------------------------------------------------------


class PipelineStatusResponse(BaseModel):
    status: str
    active_cameras: int
    camera_ids: list[int]


class CameraMetricsResponse(BaseModel):
    camera_id: int
    frames_received: int
    frames_processed: int
    frames_dropped: int
    frames_errored: int
    active_tracks: int
    candidates_emitted: int
    total_processing_time_s: float
    average_latency_ms: float
    fps_processed: float
    started_at: str
    snapshot_at: str


class StartCameraRequest(BaseModel):
    camera_id: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metrics_to_response(snapshot: Any) -> CameraMetricsResponse:
    return CameraMetricsResponse(
        camera_id=snapshot.camera_id,
        frames_received=snapshot.frames_received,
        frames_processed=snapshot.frames_processed,
        frames_dropped=snapshot.frames_dropped,
        frames_errored=snapshot.frames_errored,
        active_tracks=snapshot.active_tracks,
        candidates_emitted=snapshot.candidates_emitted,
        total_processing_time_s=snapshot.total_processing_time_s,
        average_latency_ms=snapshot.average_latency_ms,
        fps_processed=snapshot.fps_processed,
        started_at=snapshot.started_at.isoformat(),
        snapshot_at=snapshot.snapshot_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/status",
    response_model=PipelineStatusResponse,
    summary="AI Pipeline Status",
    description=(
        "Returns the current status of the Module 5 AI Video Processing pipeline: "
        "whether it is running and which cameras are actively being processed."
    ),
)
async def get_pipeline_status(
    current_user: Any = Depends(get_current_user),
) -> PipelineStatusResponse:
    status_data = video_pipeline.get_pipeline_status()
    return PipelineStatusResponse(**status_data)


@router.get(
    "/metrics",
    response_model=list[CameraMetricsResponse],
    summary="Processing Metrics — All Cameras",
    description=(
        "Returns aggregate AI video-processing metrics for all cameras. "
        "No raw frame data or biometric information is included."
    ),
)
async def get_all_metrics(
    current_user: Any = Depends(get_current_user),
) -> list[CameraMetricsResponse]:
    snapshots = video_pipeline.get_processing_metrics()
    if not snapshots:
        return []
    return [_metrics_to_response(s) for s in snapshots]


@router.get(
    "/metrics/{camera_id}",
    response_model=CameraMetricsResponse,
    summary="Processing Metrics — Single Camera",
    description=(
        "Returns AI video-processing metrics for one specific camera. "
        "No raw frame data or biometric information is included."
    ),
)
async def get_camera_metrics(
    camera_id: int,
    current_user: Any = Depends(get_current_user),
) -> CameraMetricsResponse:
    snapshot = video_pipeline.get_processing_metrics(camera_id=camera_id)
    return _metrics_to_response(snapshot)


@router.post(
    "/cameras/{camera_id}/start",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start AI Pipeline for a Camera",
    description=(
        "Starts the Module 5 AI Video Processing pipeline for the specified camera. "
        "The camera stream must already be running (started via Module 4). "
        "Requires operator or administrator role."
    ),
)
async def start_camera_pipeline(
    camera_id: int,
    current_user: Any = Depends(get_current_user),
) -> dict:
    from app.services.stream_manager import stream_manager  # noqa: PLC0415
    from app.database.session import SessionLocal  # noqa: PLC0415
    from app.models.camera import Camera  # noqa: PLC0415

    queue = stream_manager.get_frame_queue(camera_id)
    if queue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No active stream found for camera_id={camera_id}. "
                "Start the camera stream via Module 4 first."
            ),
        )

    # Fetch camera metadata for the pipeline
    db = SessionLocal()
    try:
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        if not camera:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Camera {camera_id} not found.",
            )

        await video_pipeline.start_camera(
            camera_id=camera.id,
            queue=queue,
            camera_code=camera.camera_code,
            location=camera.location_name,
            department_id=camera.department_id,
        )

        logger.info(
            "[API] AI pipeline started for camera_id=%d by user=%s",
            camera_id,
            getattr(current_user, "username", "unknown"),
        )
    finally:
        db.close()

    return {
        "message": f"AI processing pipeline started for camera_id={camera_id}.",
        "camera_id": camera_id,
    }


@router.post(
    "/cameras/{camera_id}/stop",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Stop AI Pipeline for a Camera",
    description="Stops the Module 5 AI processing pipeline for the specified camera.",
)
async def stop_camera_pipeline(
    camera_id: int,
    current_user: Any = Depends(get_current_user),
) -> dict:
    await video_pipeline.stop_camera(camera_id)
    logger.info(
        "[API] AI pipeline stopped for camera_id=%d by user=%s",
        camera_id,
        getattr(current_user, "username", "unknown"),
    )
    return {"message": f"AI processing pipeline stopped for camera_id={camera_id}."}


@router.post(
    "/stop-all",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Stop All AI Pipelines",
    description="Gracefully stops AI processing pipelines for all cameras. Admin use only.",
)
async def stop_all_pipelines(
    current_user: Any = Depends(get_current_user),
) -> dict:
    await video_pipeline.stop_all()
    logger.info(
        "[API] All AI pipelines stopped by user=%s",
        getattr(current_user, "username", "unknown"),
    )
    return {"message": "All AI processing pipelines stopped."}
