"""
Module 6 – Face Quality Assessor
==================================
The primary quality evaluation engine. Orchestrates image validation, blur,
lighting, resolution, pose, and occlusion analysis to compute a composite
quality score, assign a categorical status, and determine match-readiness.

Safety Invariant:
    This assessor evaluates image quality only. It never performs person
    identification or generates identity confidence scores.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

import numpy as np

from app.ai_engine.config.quality_settings import quality_settings
from app.ai_engine.quality.blur_analyzer import BlurAnalysisResult, BlurAnalyzer
from app.ai_engine.quality.face_size_analyzer import FaceSizeAnalysisResult, FaceSizeAnalyzer
from app.ai_engine.quality.image_validator import FaceImageValidator, ImageValidationStatus
from app.ai_engine.quality.lighting_analyzer import LightingAnalysisResult, LightingAnalyzer
from app.ai_engine.quality.occlusion_analyzer import OcclusionAnalysisResult, OcclusionAnalyzer
from app.ai_engine.quality.pose_estimator import PoseEstimationResult, PoseEstimator
from app.ai_engine.schemas.observations import BoundingBox
from app.ai_engine.schemas.quality import (
    ExposureStatus,
    FaceQualityMetrics,
    FaceQualityResult,
    QualityClassification,
    RejectionReason,
)

logger = logging.getLogger(__name__)


class FaceQualityAssessor:
    """
    Modular, stateless evaluator determining whether a face observation
    from Module 5 is of sufficient quality to enter Module 7 candidate matching.
    """

    def __init__(
        self,
        blur_analyzer: BlurAnalyzer | None = None,
        lighting_analyzer: LightingAnalyzer | None = None,
        size_analyzer: FaceSizeAnalyzer | None = None,
        pose_estimator: PoseEstimator | None = None,
        occlusion_analyzer: OcclusionAnalyzer | None = None,
    ) -> None:
        self.blur_analyzer = blur_analyzer or BlurAnalyzer()
        self.lighting_analyzer = lighting_analyzer or LightingAnalyzer()
        self.size_analyzer = size_analyzer or FaceSizeAnalyzer()
        self.pose_estimator = pose_estimator or PoseEstimator()
        self.occlusion_analyzer = occlusion_analyzer or OcclusionAnalyzer()

    # -------------------------------------------------------------------------
    # Modular Internal Perception & Measurement Interfaces (Section 17)
    # -------------------------------------------------------------------------

    def calculate_sharpness(self, image_bgr: np.ndarray) -> BlurAnalysisResult:
        """Measure blur and sharpness on a face crop."""
        return self.blur_analyzer.analyze(image_bgr)

    def calculate_lighting_quality(self, image_bgr: np.ndarray) -> LightingAnalysisResult:
        """Measure brightness, contrast, and exposure status."""
        return self.lighting_analyzer.analyze(image_bgr)

    def calculate_face_size_quality(
        self,
        face_width: int,
        face_height: int,
        frame_width: int | None = None,
        frame_height: int | None = None,
    ) -> FaceSizeAnalysisResult:
        """Measure face crop dimensions against minimum and optimal benchmarks."""
        return self.size_analyzer.analyze(face_width, face_height, frame_width, frame_height)

    def estimate_pose(
        self,
        landmarks: Sequence[tuple[float, float]] | None = None,
        face_crop: np.ndarray | None = None,
    ) -> PoseEstimationResult:
        """Estimate 3D head pose and orientation angles."""
        return self.pose_estimator.estimate(landmarks, face_crop)

    def estimate_occlusion(self, face_bgr: np.ndarray) -> OcclusionAnalysisResult:
        """Estimate facial occlusion and obstruction levels."""
        return self.occlusion_analyzer.analyze(face_bgr)

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
        """
        Calculate normalized composite quality score [0.0, 1.0].
        Represents image usability, NOT identity probability (AI Safety Invariant).
        """
        weights = quality_settings
        score_sharp = sharpness_score * weights.WEIGHT_SHARPNESS
        score_light = brightness_score * weights.WEIGHT_LIGHTING
        score_contrast = contrast_score * weights.WEIGHT_CONTRAST
        score_size = face_size_score * weights.WEIGHT_SIZE
        score_pose = pose_score * weights.WEIGHT_POSE
        score_occ = (1.0 - occlusion_score) * weights.WEIGHT_OCCLUSION

        raw_composite = (
            score_sharp + score_light + score_contrast + score_size + score_pose + score_occ
        )
        det_conf_factor = 0.85 + 0.15 * min(1.0, max(0.0, face_detection_confidence))
        return float(np.clip(raw_composite * det_conf_factor, 0.0, 1.0))

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
        """
        Synthesize individual perceptual metrics into a standardized FaceQualityResult.
        """
        w = size_res.face_width
        h = size_res.face_height

        composite_score = self.calculate_quality_score(
            sharpness_score=blur_res.sharpness_score,
            brightness_score=light_res.brightness_score,
            contrast_score=light_res.contrast_score,
            face_size_score=size_res.face_size_score,
            pose_score=pose_res.pose_score,
            occlusion_score=occ_res.occlusion_score,
            face_detection_confidence=face_detection_confidence,
        )

        rejection_reason = RejectionReason.NONE
        failure_messages: list[str] = []

        if not size_res.is_sufficient_size:
            rejection_reason = RejectionReason.FACE_TOO_SMALL
            failure_messages.append(
                f"Face dimensions ({w}x{h}) below minimum ({quality_settings.MIN_FACE_WIDTH}x{quality_settings.MIN_FACE_HEIGHT})"
            )
        elif blur_res.is_excessive_blur:
            rejection_reason = RejectionReason.EXCESSIVE_BLUR
            failure_messages.append(
                f"Excessive blur (sharpness={blur_res.sharpness_raw:.1f} < {quality_settings.MIN_SHARPNESS_SCORE})"
            )
        elif light_res.exposure_status == ExposureStatus.UNDEREXPOSED:
            rejection_reason = RejectionReason.INSUFFICIENT_LIGHT
            failure_messages.append(
                f"Underexposed face region (luminance={light_res.brightness_raw:.1f} < {quality_settings.MIN_BRIGHTNESS_SCORE})"
            )
        elif light_res.exposure_status == ExposureStatus.OVEREXPOSED:
            rejection_reason = RejectionReason.OVEREXPOSED
            failure_messages.append(
                f"Overexposed face region (luminance={light_res.brightness_raw:.1f} > {quality_settings.MAX_BRIGHTNESS_SCORE})"
            )
        elif light_res.exposure_status == ExposureStatus.LOW_CONTRAST:
            rejection_reason = RejectionReason.LOW_CONTRAST
            failure_messages.append(
                f"Low contrast face region (contrast={light_res.contrast_raw:.1f} < {quality_settings.MIN_CONTRAST_SCORE})"
            )
        elif light_res.exposure_status == ExposureStatus.UNEVEN_ILLUMINATION:
            rejection_reason = RejectionReason.UNEVEN_ILLUMINATION
            failure_messages.append(
                f"Uneven facial illumination (uniformity={light_res.illumination_uniformity:.2f})"
            )
        elif not pose_res.is_acceptable_pose:
            rejection_reason = RejectionReason.SEVERE_POSE
            failure_messages.append(
                f"Severe face angle (max_angle={pose_res.max_angle:.1f}° > {quality_settings.MAX_POSE_YAW}°)"
            )
        elif not occ_res.is_acceptable_occlusion:
            rejection_reason = RejectionReason.HIGH_OCCLUSION
            failure_messages.append(
                f"High facial occlusion (score={occ_res.occlusion_score:.2f} > {quality_settings.MAX_OCCLUSION_SCORE})"
            )
        elif face_detection_confidence < 0.50:
            rejection_reason = RejectionReason.LOW_DETECTION_CONFIDENCE
            failure_messages.append(
                f"Face detection confidence too low ({face_detection_confidence:.2f} < 0.50)"
            )

        # Quality Classification
        if rejection_reason != RejectionReason.NONE or composite_score < quality_settings.ACCEPTABLE_THRESHOLD:
            status = QualityClassification.POOR
            is_match_ready = False
        elif composite_score >= quality_settings.EXCELLENT_THRESHOLD:
            status = QualityClassification.EXCELLENT
            is_match_ready = True
        elif composite_score >= quality_settings.GOOD_THRESHOLD:
            status = QualityClassification.GOOD
            is_match_ready = True
        else:
            status = QualityClassification.ACCEPTABLE
            is_match_ready = (composite_score >= quality_settings.MIN_QUALITY_SCORE)

        if is_match_ready:
            reason = (
                f"Face observation is suitable for downstream candidate matching "
                f"(quality_score={composite_score:.2f}, status={status.value})."
            )
        else:
            details = "; ".join(failure_messages) if failure_messages else f"Score {composite_score:.2f} below threshold"
            reason = (
                f"Face observation is insufficient for reliable downstream matching: {details}."
            )

        metrics = FaceQualityMetrics(
            sharpness_raw=blur_res.sharpness_raw,
            sharpness_score=blur_res.sharpness_score,
            brightness_raw=light_res.brightness_raw,
            brightness_score=light_res.brightness_score,
            contrast_raw=light_res.contrast_raw,
            contrast_score=light_res.contrast_score,
            exposure_status=light_res.exposure_status,
            illumination_uniformity=light_res.illumination_uniformity,
            gradient_magnitude=blur_res.gradient_magnitude,
            face_width=size_res.face_width,
            face_height=size_res.face_height,
            face_area=size_res.face_area,
            relative_face_size=size_res.relative_face_size,
            face_size_score=size_res.face_size_score,
            estimated_yaw=pose_res.yaw,
            estimated_pitch=pose_res.pitch,
            estimated_roll=pose_res.roll,
            pose_classification=pose_res.classification,
            pose_score=pose_res.pose_score,
            occlusion_score=occ_res.occlusion_score,
            occlusion_level=occ_res.occlusion_level,
            detection_confidence=face_detection_confidence,
        )

        return FaceQualityResult(
            candidate_id=candidate_id,
            track_id=track_id,
            camera_id=camera_id,
            timestamp=timestamp,
            sharpness_score=blur_res.sharpness_score,
            brightness_score=light_res.brightness_score,
            contrast_score=light_res.contrast_score,
            face_size_score=size_res.face_size_score,
            pose_score=pose_res.pose_score,
            occlusion_score=occ_res.occlusion_score,
            detection_confidence=face_detection_confidence,
            quality_score=round(composite_score, 4),
            quality_status=status,
            is_match_ready=is_match_ready,
            reason=reason,
            rejection_reason=rejection_reason,
            best_frame_reference=frame_reference,
            camera_location=camera_location,
            department_id=department_id,
            metrics=metrics,
        )

    def assess(
        self,
        image: Any,
        candidate_id: str,
        track_id: str,
        camera_id: int,
        timestamp: Any,
        frame_reference: str,
        face_bbox: BoundingBox,
        face_detection_confidence: float = 0.90,
        camera_location: str | None = None,
        department_id: int | None = None,
        landmark_points: Sequence[tuple[float, float]] | None = None,
        frame_width: int | None = 1920,
        frame_height: int | None = 1080,
    ) -> FaceQualityResult:
        """
        Run the complete quality perception pipeline on a face crop or frame ROI.

        Parameters:
            image: BGR NumPy array or base64 encoded string or file path reference.
            candidate_id: Traceable ID from Module 5.
            track_id: Person track identifier.
            camera_id: CCTV camera ID.
            timestamp: Capture datetime.
            frame_reference: Traceable frame string.
            face_bbox: Face bounding box coordinates.
            face_detection_confidence: Detector score from Module 5 (NOT identity conf).
            camera_location: Optional human readable camera placement.
            department_id: Optional department identifier.
            landmark_points: Optional 5 facial landmark tuples.
            frame_width, frame_height: Optional full frame dimensions.
        """
        # Step 1: Image Validation
        validated_img, val_status = FaceImageValidator.validate(
            image, face_bbox=face_bbox, frame_width=frame_width, frame_height=frame_height
        )

        if val_status != ImageValidationStatus.VALID or validated_img is None:
            logger.info(
                "[QualityAssessor] Candidate %s rejected during image validation: %s",
                candidate_id,
                val_status.value,
            )
            return FaceQualityResult(
                candidate_id=candidate_id,
                track_id=track_id,
                camera_id=camera_id,
                timestamp=timestamp,
                sharpness_score=0.0,
                brightness_score=0.0,
                contrast_score=0.0,
                face_size_score=0.0,
                pose_score=0.0,
                occlusion_score=1.0,
                detection_confidence=face_detection_confidence,
                quality_score=0.0,
                quality_status=QualityClassification.INVALID,
                is_match_ready=False,
                reason=f"Face image is invalid or could not be decoded ({val_status.value}).",
                rejection_reason=RejectionReason.INVALID_IMAGE,
                best_frame_reference=frame_reference,
                camera_location=camera_location,
                department_id=department_id,
            )

        face_bgr = validated_img.image_bgr
        w = validated_img.width
        h = validated_img.height

        # Step 2: Individual Component Analysis using modular methods
        blur_res = self.calculate_sharpness(face_bgr)
        light_res = self.calculate_lighting_quality(face_bgr)
        size_res = self.calculate_face_size_quality(
            face_width=w,
            face_height=h,
            frame_width=frame_width,
            frame_height=frame_height,
        )
        pose_res = self.estimate_pose(
            landmarks=landmark_points,
            face_crop=face_bgr,
        )
        occ_res = self.estimate_occlusion(face_bgr)

        # Steps 3-5: Composite Scoring, Rejection Gating, & Classification
        return self.create_quality_result(
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


# Module-level singleton
face_quality_assessor = FaceQualityAssessor()
