"""
Module 6 – Face Quality Service
=================================
High-level service managing face quality evaluations, research telemetry,
database persistence, and multi-frame best-observation selection.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy.orm import Session

from app.ai_engine.config.quality_settings import quality_settings
from app.ai_engine.quality.best_frame_selector import (
    BestFrameSelector,
    best_frame_selector,
)
from app.ai_engine.quality.blur_analyzer import BlurAnalysisResult, BlurAnalyzer
from app.ai_engine.quality.face_size_analyzer import (
    FaceSizeAnalysisResult,
    FaceSizeAnalyzer,
)
from app.ai_engine.quality.lighting_analyzer import (
    LightingAnalysisResult,
    LightingAnalyzer,
)
from app.ai_engine.quality.occlusion_analyzer import (
    OcclusionAnalysisResult,
    OcclusionAnalyzer,
)
from app.ai_engine.quality.pose_estimator import (
    PoseEstimationResult,
    PoseEstimator,
)
from app.ai_engine.quality.quality_assessor import (
    FaceQualityAssessor,
    face_quality_assessor,
)
from app.ai_engine.schemas.observations import BoundingBox, CandidateObservation
from app.ai_engine.schemas.quality import (
    FaceQualityResult,
    MultiFrameAssessResponse,
    QualityTelemetryResponse,
)
from app.database.session import SessionLocal
from app.models.case import Case  # noqa: F401
from app.models.face_quality_result import FaceQualityResultDB
from app.models.reference_image import ReferenceImage  # noqa: F401

logger = logging.getLogger(__name__)


class _QualityTelemetryTracker:
    """Thread-safe telemetry accumulator for research evaluation (Section 19)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.faces_received: int = 0
        self.faces_assessed: int = 0
        self.faces_rejected: int = 0
        self.faces_passed: int = 0
        self.total_quality_score: float = 0.0
        self.total_latency_s: float = 0.0
        self.active_cameras: set[int] = set()
        self.camera_stats: dict[int, dict[str, Any]] = {}

    def record_assessment(
        self,
        camera_id: int,
        is_match_ready: bool,
        quality_score: float,
        latency_s: float,
    ) -> None:
        with self._lock:
            self.faces_received += 1
            self.faces_assessed += 1
            if is_match_ready:
                self.faces_passed += 1
            else:
                self.faces_rejected += 1
            self.total_quality_score += quality_score
            self.total_latency_s += latency_s
            self.active_cameras.add(camera_id)

            if camera_id not in self.camera_stats:
                self.camera_stats[camera_id] = {
                    "camera_id": camera_id,
                    "faces_received": 0,
                    "faces_assessed": 0,
                    "faces_passed": 0,
                    "faces_rejected": 0,
                    "total_score": 0.0,
                }
            cam = self.camera_stats[camera_id]
            cam["faces_received"] += 1
            cam["faces_assessed"] += 1
            if is_match_ready:
                cam["faces_passed"] += 1
            else:
                cam["faces_rejected"] += 1
            cam["total_score"] += quality_score

    def snapshot(self) -> QualityTelemetryResponse:
        with self._lock:
            assessed = self.faces_assessed
            pass_rate = (self.faces_passed / assessed) if assessed > 0 else 0.0
            rejection_rate = (self.faces_rejected / assessed) if assessed > 0 else 0.0
            avg_score = (self.total_quality_score / assessed) if assessed > 0 else 0.0
            avg_latency_s = (self.total_latency_s / assessed) if assessed > 0 else 0.0
            avg_latency_ms = avg_latency_s * 1000.0

            cam_dict: dict[str, Any] = {}
            for cid, stat in self.camera_stats.items():
                c_assessed = stat["faces_assessed"]
                cam_dict[str(cid)] = {
                    "camera_id": cid,
                    "faces_received": stat["faces_received"],
                    "faces_assessed": c_assessed,
                    "faces_passed": stat["faces_passed"],
                    "faces_rejected": stat["faces_rejected"],
                    "average_quality_score": round(stat["total_score"] / c_assessed, 4) if c_assessed > 0 else 0.0,
                }

            return QualityTelemetryResponse(
                faces_received=self.faces_received,
                faces_assessed=self.faces_assessed,
                faces_rejected=self.faces_rejected,
                faces_passed=self.faces_passed,
                pass_rate=round(pass_rate, 4),
                rejection_rate=round(rejection_rate, 4),
                average_quality_score=round(avg_score, 4),
                average_quality_processing_time=round(avg_latency_s, 4),
                average_processing_latency_ms=round(avg_latency_ms, 2),
                active_camera_count=len(self.active_cameras),
                camera_telemetry=cam_dict,
                snapshot_at=datetime.now(timezone.utc).isoformat(),
            )

    def reset(self) -> None:
        with self._lock:
            self.faces_received = 0
            self.faces_assessed = 0
            self.faces_rejected = 0
            self.faces_passed = 0
            self.total_quality_score = 0.0
            self.total_latency_s = 0.0
            self.active_cameras.clear()
            self.camera_stats.clear()


class FaceQualityService:
    """Central service for face quality assessment, telemetry, and persistence."""

    def __init__(
        self,
        assessor: FaceQualityAssessor | None = None,
        selector: BestFrameSelector | None = None,
    ) -> None:
        self.assessor = assessor or face_quality_assessor
        self.selector = selector or best_frame_selector
        self.telemetry = _QualityTelemetryTracker()

    # -------------------------------------------------------------------------
    # Public Service Interfaces (Required by Section 17)
    # -------------------------------------------------------------------------

    def calculate_sharpness(self, image: Any) -> BlurAnalysisResult:
        """Measure blur and sharpness on an image crop."""
        return self.assessor.blur_analyzer.analyze(image)

    def calculate_lighting_quality(self, image: Any) -> LightingAnalysisResult:
        """Measure brightness, contrast, and exposure status."""
        return self.assessor.lighting_analyzer.analyze(image)

    def calculate_face_size_quality(
        self, width: int, height: int, frame_w: int | None = None, frame_h: int | None = None
    ) -> FaceSizeAnalysisResult:
        """Measure absolute and relative face size."""
        return self.assessor.size_analyzer.analyze(width, height, frame_w, frame_h)

    def estimate_pose(
        self,
        landmarks: Sequence[tuple[float, float]] | None = None,
        face_crop: Any = None,
    ) -> PoseEstimationResult:
        """Estimate 3D head pose and orientation angles."""
        return self.assessor.pose_estimator.estimate(landmarks, face_crop)

    def estimate_occlusion(self, image: Any) -> OcclusionAnalysisResult:
        """Estimate facial occlusion and obstruction levels."""
        return self.assessor.occlusion_analyzer.analyze(image)

    def calculate_quality_score(
        self,
        sharpness_score: float,
        brightness_score: float,
        contrast_score: float,
        face_size_score: float,
        pose_score: float,
        occlusion_score: float,
        face_detection_confidence: float = 0.90,
    ) -> float:
        """Calculate composite quality score via assessor (Section 17)."""
        return self.assessor.calculate_quality_score(
            sharpness_score=sharpness_score,
            brightness_score=brightness_score,
            contrast_score=contrast_score,
            face_size_score=face_size_score,
            pose_score=pose_score,
            occlusion_score=occlusion_score,
            face_detection_confidence=face_detection_confidence,
        )

    def create_quality_result(
        self,
        candidate_id: str,
        track_id: str,
        camera_id: int,
        timestamp: Any,
        frame_reference: str,
        blur_res: BlurAnalysisResult,
        light_res: LightingAnalysisResult,
        size_res: FaceSizeAnalysisResult,
        pose_res: PoseEstimationResult,
        occ_res: OcclusionAnalysisResult,
        face_detection_confidence: float = 0.90,
        camera_location: str | None = None,
        department_id: int | None = None,
    ) -> FaceQualityResult:
        """Create a standardized FaceQualityResult via assessor (Section 17)."""
        return self.assessor.create_quality_result(
            candidate_id=candidate_id,
            track_id=track_id,
            camera_id=camera_id,
            timestamp=timestamp,
            frame_reference=frame_reference,
            blur_res=blur_res,
            light_res=light_res,
            size_res=size_res,
            pose_res=pose_res,
            occ_res=occ_res,
            face_detection_confidence=face_detection_confidence,
            camera_location=camera_location,
            department_id=department_id,
        )

    def assess_candidate_observation(
        self,
        observation: CandidateObservation,
        image: Any = None,
        db: Session | None = None,
    ) -> FaceQualityResult:
        """
        Direct adapter interface for Module 5 CandidateObservation objects.
        Integrates Module 5 and Module 6 perception pipelines seamlessly.
        """
        bbox = observation.face_bbox or observation.person_bbox
        # Prefer provided image, then in-memory face crop base64, then frame_reference
        img_source = (
            image
            if image is not None
            else getattr(observation, "face_crop_base64", None) or observation.frame_reference
        )
        return self.assess_face_quality(
            image=img_source,
            candidate_id=observation.candidate_id,
            track_id=observation.track_id,
            camera_id=observation.camera_id,
            timestamp=observation.timestamp,
            frame_reference=observation.frame_reference,
            face_bbox=bbox,
            face_detection_confidence=observation.face_confidence if observation.face_confidence is not None else 0.90,
            camera_location=observation.location,
            department_id=observation.department_id,
            db=db,
        )

    def assess_face_quality(
        self,
        image: Any,
        candidate_id: str,
        track_id: str,
        camera_id: int,
        timestamp: datetime,
        frame_reference: str,
        face_bbox: BoundingBox,
        face_detection_confidence: float = 0.90,
        camera_location: str | None = None,
        department_id: int | None = None,
        landmark_points: Sequence[tuple[float, float]] | None = None,
        frame_width: int | None = 1920,
        frame_height: int | None = 1080,
        db: Session | None = None,
    ) -> FaceQualityResult:
        """
        Evaluate face observation quality, update telemetry, register with
        best-frame tracker, and optionally persist to database.
        """
        start_time = time.perf_counter()

        result = self.assessor.assess(
            image=image,
            candidate_id=candidate_id,
            track_id=track_id,
            camera_id=camera_id,
            timestamp=timestamp,
            frame_reference=frame_reference,
            face_bbox=face_bbox,
            face_detection_confidence=face_detection_confidence,
            camera_location=camera_location,
            department_id=department_id,
            landmark_points=landmark_points,
            frame_width=frame_width,
            frame_height=frame_height,
        )

        elapsed = time.perf_counter() - start_time

        # Update telemetry
        self.telemetry.record_assessment(
            camera_id=camera_id,
            is_match_ready=result.is_match_ready,
            quality_score=result.quality_score,
            latency_s=elapsed,
        )

        # Register observation in track sliding window
        self.selector.register_observation(result)

        # Persist to database if enabled
        if quality_settings.PERSIST_QUALITY_RESULTS:
            self._persist_result(result, db)

        return result

    def select_best_observation(
        self, observations: Sequence[FaceQualityResult]
    ) -> tuple[FaceQualityResult | None, list[FaceQualityResult], str]:
        """Rank and select the optimal usable observation across candidate frames."""
        return self.selector.select_best(observations)

    def evaluate_multi_frame_track(
        self,
        track_id: str,
        observations: Sequence[FaceQualityResult],
    ) -> MultiFrameAssessResponse:
        """Evaluate multiple observations for a track and construct a response."""
        best, ranked, reason = self.select_best_observation(observations)
        usable_count = len(ranked)
        rejected_count = len(observations) - usable_count

        return MultiFrameAssessResponse(
            track_id=track_id,
            total_observations=len(observations),
            usable_observations=usable_count,
            rejected_observations=rejected_count,
            best_observation=best,
            ranked_candidates=ranked,
            selection_reason=reason,
        )

    # -------------------------------------------------------------------------
    # Database Helpers
    # -------------------------------------------------------------------------

    def _persist_result(
        self, result: FaceQualityResult, db: Session | None = None
    ) -> None:
        """Write an assessment row into face_quality_results table."""
        should_close = False
        if db is None:
            db = SessionLocal()
            should_close = True

        try:
            db_row = FaceQualityResultDB(
                candidate_id=result.candidate_id,
                track_id=result.track_id,
                camera_id=result.camera_id,
                timestamp=result.timestamp,
                sharpness_score=result.sharpness_score,
                brightness_score=result.brightness_score,
                contrast_score=result.contrast_score,
                face_size_score=result.face_size_score,
                pose_score=result.pose_score,
                occlusion_score=result.occlusion_score,
                detection_confidence=result.detection_confidence,
                quality_score=result.quality_score,
                quality_status=result.quality_status.value,
                is_match_ready=result.is_match_ready,
                rejection_reason=result.rejection_reason.value,
                best_frame_reference=result.best_frame_reference,
            )
            db.add(db_row)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning("[FaceQualityService] DB write error: %s", exc)
        finally:
            if should_close:
                db.close()

    def get_result_by_candidate(
        self, candidate_id: str, db: Session
    ) -> FaceQualityResultDB | None:
        """Fetch quality assessment by candidate_id from database."""
        return (
            db.query(FaceQualityResultDB)
            .filter(FaceQualityResultDB.candidate_id == candidate_id)
            .order_by(FaceQualityResultDB.id.desc())
            .first()
        )

    def get_history_by_track(
        self, track_id: str, db: Session
    ) -> list[FaceQualityResultDB]:
        """Fetch all historical quality assessments for a track_id from database."""
        return (
            db.query(FaceQualityResultDB)
            .filter(FaceQualityResultDB.track_id == track_id)
            .order_by(FaceQualityResultDB.created_at.asc())
            .all()
        )

    def get_telemetry_snapshot(self) -> QualityTelemetryResponse:
        """Get live telemetry statistics for research/dashboard monitoring."""
        return self.telemetry.snapshot()


# Module-level singleton
quality_service = FaceQualityService()
