"""
Module 6 – Face Quality Assessment API Router
===============================================
Exposes endpoints for face quality evaluation, multi-frame best-observation
ranking, candidate quality retrieval, and research telemetry.

Security & Safety:
- Protected via Module 1 authentication (JWT) and RBAC.
- Quality score represents image usability, never person identity probability.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_police
from app.database.session import get_db
from app.models.face_quality_result import FaceQualityResultDB
from app.ai_engine.schemas.quality import (
    FaceQualityResult,
    MultiFrameAssessRequest,
    MultiFrameAssessResponse,
    QualityAssessRequest,
    QualityClassification,
    QualityTelemetryResponse,
    RejectionReason,
)
from app.services.quality_service import quality_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/face-quality", tags=["Module 6 – Face Quality Assessment"])


@router.post(
    "/assess",
    response_model=FaceQualityResult,
    summary="Assess Face Quality for a Candidate",
    description=(
        "Evaluates whether a detected face observation from Module 5 meets the "
        "quality criteria (sharpness, lighting, resolution, pose, occlusion) "
        "required to enter Module 7 candidate matching. Does NOT perform identity matching."
    ),
)
async def assess_candidate_face_quality(
    payload: QualityAssessRequest,
    current_user: Any = Depends(require_police),
    db: Session = Depends(get_db),
) -> FaceQualityResult:
    image_input = payload.face_image_base64 or payload.face_image_reference
    result = quality_service.assess_face_quality(
        image=image_input,
        candidate_id=payload.candidate_id,
        track_id=payload.track_id,
        camera_id=payload.camera_id,
        timestamp=payload.timestamp,
        frame_reference=payload.frame_reference,
        face_bbox=payload.face_bbox,
        face_detection_confidence=payload.face_detection_confidence,
        camera_location=payload.camera_location,
        department_id=payload.department_id,
        landmark_points=payload.landmark_points,
        frame_width=payload.frame_width,
        frame_height=payload.frame_height,
        db=db,
    )
    return result


@router.post(
    "/assess-multi-frame",
    response_model=MultiFrameAssessResponse,
    summary="Evaluate Multi-Frame Track & Select Best Observation",
    description=(
        "Takes multiple candidate observations belonging to the same person track, "
        "filters out sub-threshold frames, ranks usable observations, and selects "
        "the best candidate for Module 7 candidate matching."
    ),
)
async def assess_multi_frame_candidates(
    payload: MultiFrameAssessRequest,
    current_user: Any = Depends(require_police),
    db: Session = Depends(get_db),
) -> MultiFrameAssessResponse:
    """Assess and rank multiple frames for a person track."""
    evaluated_results: list[FaceQualityResult] = []

    for req in payload.candidates:
        img_source = req.face_image_base64 or req.face_image_reference
        res = quality_service.assess_face_quality(
            image=img_source,
            candidate_id=req.candidate_id,
            track_id=payload.track_id,
            camera_id=req.camera_id,
            timestamp=req.timestamp,
            frame_reference=req.frame_reference,
            face_bbox=req.face_bbox,
            face_detection_confidence=req.face_detection_confidence,
            camera_location=req.camera_location,
            department_id=req.department_id,
            landmark_points=req.landmark_points,
            frame_width=req.frame_width,
            frame_height=req.frame_height,
            db=db,
        )
        evaluated_results.append(res)

    response = quality_service.evaluate_multi_frame_track(
        track_id=payload.track_id,
        observations=evaluated_results,
    )
    return response


@router.get(
    "/metrics/telemetry",
    response_model=QualityTelemetryResponse,
    summary="Get Face Quality Telemetry Metrics",
    description="Returns aggregate quality assessment rates, latencies, and pass/rejection metrics for research evaluation.",
)
async def get_quality_telemetry(
    current_user: Any = Depends(get_current_user),
) -> QualityTelemetryResponse:
    """Fetch live operational and research telemetry metrics."""
    return quality_service.get_telemetry_snapshot()


@router.get(
    "/{candidate_id}",
    response_model=FaceQualityResult,
    summary="Get Quality Assessment by Candidate ID",
    description="Retrieves a stored face quality assessment record from the database.",
)
async def get_candidate_quality(
    candidate_id: str,
    current_user: Any = Depends(require_police),
    db: Session = Depends(get_db),
) -> FaceQualityResult:
    """Retrieve quality result for a candidate from DB."""
    db_result = quality_service.get_result_by_candidate(candidate_id, db)
    if not db_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quality assessment for candidate '{candidate_id}' not found.",
        )

    return FaceQualityResult(
        candidate_id=db_result.candidate_id,
        track_id=db_result.track_id,
        camera_id=db_result.camera_id,
        timestamp=db_result.timestamp,
        sharpness_score=db_result.sharpness_score,
        brightness_score=db_result.brightness_score,
        contrast_score=db_result.contrast_score,
        face_size_score=db_result.face_size_score,
        pose_score=db_result.pose_score,
        occlusion_score=db_result.occlusion_score,
        detection_confidence=db_result.detection_confidence,
        quality_score=db_result.quality_score,
        quality_status=QualityClassification(db_result.quality_status),
        is_match_ready=db_result.is_match_ready,
        reason=(
            "Observation is suitable for candidate matching."
            if db_result.is_match_ready
            else f"Rejected: {db_result.rejection_reason}"
        ),
        rejection_reason=RejectionReason(db_result.rejection_reason or "NONE"),
        best_frame_reference=db_result.best_frame_reference or "",
        created_at=db_result.created_at,
    )


@router.get(
    "/{candidate_id}/history",
    response_model=list[FaceQualityResult],
    summary="Get Quality History for Associated Track",
    description="Retrieves chronological quality assessment records for the person track associated with this candidate.",
)
async def get_candidate_track_history(
    candidate_id: str,
    current_user: Any = Depends(require_police),
    db: Session = Depends(get_db),
) -> list[FaceQualityResult]:
    """Retrieve quality history for the track of a given candidate."""
    db_result = quality_service.get_result_by_candidate(candidate_id, db)
    if not db_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate '{candidate_id}' not found.",
        )

    history_rows = quality_service.get_history_by_track(db_result.track_id, db)
    return [
        FaceQualityResult(
            candidate_id=row.candidate_id,
            track_id=row.track_id,
            camera_id=row.camera_id,
            timestamp=row.timestamp,
            sharpness_score=row.sharpness_score,
            brightness_score=row.brightness_score,
            contrast_score=row.contrast_score,
            face_size_score=row.face_size_score,
            pose_score=row.pose_score,
            occlusion_score=row.occlusion_score,
            detection_confidence=row.detection_confidence,
            quality_score=row.quality_score,
            quality_status=QualityClassification(row.quality_status),
            is_match_ready=row.is_match_ready,
            reason=(
                "Observation is suitable for candidate matching."
                if row.is_match_ready
                else f"Rejected: {row.rejection_reason}"
            ),
            rejection_reason=RejectionReason(row.rejection_reason or "NONE"),
            best_frame_reference=row.best_frame_reference or "",
            created_at=row.created_at,
        )
        for row in history_rows
    ]
