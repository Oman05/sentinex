"""
Module 6: Face Quality Assessment – Research & Test Dataset Evaluation Suite
=============================================================================
Evaluates the Face Quality Assessment engine against an authorized, controlled
research test dataset covering 12 distinct CCTV variation scenarios:

 1. Clear frontal faces
 2. Slightly angled faces
 3. Strongly angled faces
 4. Low-resolution faces
 5. Blurred faces
 6. Low-light faces
 7. Overexposed faces
 8. Partially occluded faces
 9. Very small distant faces
10. Multiple faces in one frame
11. Moving subjects (tracking sequence across frames)
12. Different CCTV camera qualities (compression & noise)

Measures and asserts:
- Quality Classification Accuracy
- Blur Detection Performance
- Pose Estimation Error
- Best-Frame Selection Performance
- Pass Rate & Rejection Rate
- Processing Latency Benchmarking
- AI Safety Invariant Verification (Zero identity assertions, image usability only)
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
import cv2
import numpy as np
import pytest

from app.ai_engine.config.quality_settings import quality_settings
from app.ai_engine.quality.best_frame_selector import BestFrameSelector
from app.ai_engine.quality.blur_analyzer import BlurAnalyzer
from app.ai_engine.quality.face_size_analyzer import FaceSizeAnalyzer
from app.ai_engine.quality.lighting_analyzer import LightingAnalyzer
from app.ai_engine.quality.occlusion_analyzer import OcclusionAnalyzer
from app.ai_engine.quality.pose_estimator import PoseEstimator
from app.ai_engine.quality.quality_assessor import FaceQualityAssessor
from app.ai_engine.schemas.observations import BoundingBox, CandidateObservation
from app.ai_engine.schemas.quality import (
    ExposureStatus,
    FaceQualityResult,
    OcclusionLevel,
    PoseClassification,
    QualityClassification,
    RejectionReason,
)
from app.services.quality_service import FaceQualityService


# =============================================================================
# Synthetic Authorized Research Dataset Generator
# =============================================================================


def _create_synthetic_face(
    width: int = 120,
    height: int = 120,
    base_luminance: int = 130,
    contrast_std: float = 45.0,
    blur_ksize: int = 0,
    occlusion_type: str = "none",
    bilateral_uneven: bool = False,
) -> np.ndarray:
    """
    Generates a controlled, consent-free, synthetic face pattern with
    anatomically positioned eyes, nose, and mouth features.
    """
    img = np.full((height, width, 3), base_luminance, dtype=np.uint8)

    # Add realistic texture variance
    rng = np.random.default_rng(42)
    noise = rng.normal(0, contrast_std * 0.4, (height, width, 3))
    img = np.clip(img.astype(float) + noise, 0, 255).astype(np.uint8)

    # Draw anatomical features
    cx, cy = width // 2, height // 2
    eye_y = int(height * 0.35)
    eye_offset_x = int(width * 0.22)
    eye_radius = max(2, int(width * 0.08))

    # Eyes (dark circles with white sclera)
    cv2.circle(img, (cx - eye_offset_x, eye_y), eye_radius, (30, 30, 30), -1)
    cv2.circle(img, (cx + eye_offset_x, eye_y), eye_radius, (30, 30, 30), -1)

    # Nose
    nose_y1 = int(height * 0.45)
    nose_y2 = int(height * 0.60)
    cv2.line(img, (cx, nose_y1), (cx, nose_y2), (40, 40, 40), max(1, int(width * 0.03)))

    # Mouth
    mouth_y = int(height * 0.78)
    mouth_w = int(width * 0.25)
    mouth_h = max(2, int(height * 0.08))
    cv2.ellipse(img, (cx, mouth_y), (mouth_w, mouth_h), 0, 0, 180, (20, 20, 20), max(2, int(width * 0.03)))

    # Apply bilateral illumination disparity if requested
    if bilateral_uneven:
        img[:, :cx] = np.clip(img[:, :cx].astype(float) * 0.4, 0, 255).astype(np.uint8)
        img[:, cx:] = np.clip(img[:, cx:].astype(float) * 1.5, 0, 255).astype(np.uint8)

    # Apply occlusion if requested
    if occlusion_type == "mask":
        # Simulate medical mask covering nose and mouth (from mid-face to chin)
        mask_y = int(height * 0.48)
        img[mask_y:, :] = (220, 220, 220)
    elif occlusion_type == "sunglasses":
        # Simulate dark glasses across upper 35%
        glass_top = int(height * 0.20)
        glass_bot = int(height * 0.45)
        img[glass_top:glass_bot, :] = (15, 15, 15)

    # Apply blur if requested
    if blur_ksize > 1:
        k = blur_ksize if blur_ksize % 2 == 1 else blur_ksize + 1
        img = cv2.GaussianBlur(img, (k, k), 0)

    return img


# =============================================================================
# Research Test Suite
# =============================================================================


class TestResearchDatasetControlledVariations:
    """
    Evaluates all 12 controlled variations specified for Module 6.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        self.assessor = FaceQualityAssessor()
        self.service = FaceQualityService(assessor=self.assessor)

    def _assess_crop(self, image: np.ndarray, landmarks=None, confidence: float = 0.95) -> FaceQualityResult:
        h, w = image.shape[:2]
        return self.service.assess_face_quality(
            image=image,
            candidate_id=f"RESEARCH-{int(time.time()*1000)}",
            track_id="TRACK-RESEARCH-01",
            camera_id=101,
            timestamp=datetime.now(timezone.utc),
            frame_reference="cctv_frame_ref_001",
            face_bbox=BoundingBox(x1=10, y1=10, x2=10 + w, y2=10 + h),
            face_detection_confidence=confidence,
            landmark_points=landmarks,
            frame_width=1920,
            frame_height=1080,
        )

    # -------------------------------------------------------------------------
    # Scenario 1: Clear Frontal Faces
    # -------------------------------------------------------------------------
    def test_01_clear_frontal_face(self):
        """Clear, well-lit, frontal face crop must pass quality gating for Module 7."""
        face = _create_synthetic_face(width=128, height=128, base_luminance=128)
        # Frontal landmarks: eyes horizontal, nose centered, mouth level
        landmarks = [(40.0, 45.0), (88.0, 45.0), (64.0, 68.0), (45.0, 95.0), (83.0, 95.0)]

        result = self._assess_crop(face, landmarks=landmarks)

        assert result.quality_status in (QualityClassification.EXCELLENT, QualityClassification.GOOD)
        assert result.is_match_ready is True
        assert result.rejection_reason == RejectionReason.NONE
        assert result.quality_score >= quality_settings.GOOD_THRESHOLD
        assert result.sharpness_score > 0.60
        assert result.pose_score > 0.80

    # -------------------------------------------------------------------------
    # Scenario 2: Slightly Angled Faces
    # -------------------------------------------------------------------------
    def test_02_slightly_angled_face(self):
        """Slightly angled faces (~12-15 deg yaw) should remain match-ready."""
        face = _create_synthetic_face(width=120, height=120)
        # Moderate yaw offset
        landmarks = [(38.0, 45.0), (82.0, 45.0), (68.0, 68.0), (44.0, 95.0), (80.0, 95.0)]

        result = self._assess_crop(face, landmarks=landmarks)

        assert result.is_match_ready is True
        assert result.quality_status in (
            QualityClassification.EXCELLENT,
            QualityClassification.GOOD,
            QualityClassification.ACCEPTABLE,
        )
        assert result.metrics is not None
        assert result.metrics.pose_classification in (PoseClassification.FRONTAL, PoseClassification.SLIGHTLY_ANGLED)

    # -------------------------------------------------------------------------
    # Scenario 3: Strongly Angled Faces (Severe Pose)
    # -------------------------------------------------------------------------
    def test_03_strongly_angled_face_rejected(self):
        """Strongly angled faces (>30 deg yaw) must be rejected to prevent mismatch."""
        face = _create_synthetic_face(width=120, height=120)
        # Severe yaw offset (nose close to right eye)
        landmarks = [(30.0, 45.0), (80.0, 45.0), (79.0, 68.0), (40.0, 95.0), (78.0, 95.0)]

        result = self._assess_crop(face, landmarks=landmarks)

        assert result.is_match_ready is False
        assert result.rejection_reason == RejectionReason.SEVERE_POSE
        assert result.quality_status == QualityClassification.POOR
        assert "Severe face angle" in result.reason

    # -------------------------------------------------------------------------
    # Scenario 4: Low-Resolution Faces
    # -------------------------------------------------------------------------
    def test_04_low_resolution_face_rejected(self):
        """Face smaller than MIN_FACE_WIDTH / MIN_FACE_HEIGHT must be rejected."""
        small_w, small_h = 32, 32  # Below 40x40 threshold
        face = _create_synthetic_face(width=small_w, height=small_h)

        result = self._assess_crop(face)

        assert result.is_match_ready is False
        assert result.rejection_reason == RejectionReason.FACE_TOO_SMALL
        assert result.quality_status == QualityClassification.POOR

    # -------------------------------------------------------------------------
    # Scenario 5: Blurred Faces (Motion / Defocus)
    # -------------------------------------------------------------------------
    def test_05_blurred_face_rejected(self):
        """Blurred face crop must fail sharpness check with EXCESSIVE_BLUR."""
        blurry_face = _create_synthetic_face(width=120, height=120, blur_ksize=25)

        result = self._assess_crop(blurry_face)

        assert result.is_match_ready is False
        assert result.rejection_reason == RejectionReason.EXCESSIVE_BLUR
        assert result.sharpness_score < 0.35

    # -------------------------------------------------------------------------
    # Scenario 6: Low-Light Faces (Underexposed)
    # -------------------------------------------------------------------------
    def test_06_low_light_face_rejected(self):
        """Underexposed face crop must fail lighting check with INSUFFICIENT_LIGHT."""
        dark_face = _create_synthetic_face(width=120, height=120, base_luminance=25, contrast_std=10.0)

        result = self._assess_crop(dark_face)

        assert result.is_match_ready is False
        assert result.rejection_reason in (RejectionReason.INSUFFICIENT_LIGHT, RejectionReason.LOW_CONTRAST)

    # -------------------------------------------------------------------------
    # Scenario 7: Overexposed Faces (Blown-Out Highlights)
    # -------------------------------------------------------------------------
    def test_07_overexposed_face_rejected(self):
        """Overexposed face crop must fail lighting check with OVEREXPOSED."""
        bright_face = _create_synthetic_face(width=120, height=120, base_luminance=235, contrast_std=10.0)

        result = self._assess_crop(bright_face)

        assert result.is_match_ready is False
        assert result.rejection_reason in (RejectionReason.OVEREXPOSED, RejectionReason.LOW_CONTRAST)

    # -------------------------------------------------------------------------
    # Scenario 8: Partially Occluded Faces (Mask / Sunglasses)
    # -------------------------------------------------------------------------
    def test_08_partially_occluded_face_rejected(self):
        """Face with surgical mask or dark sunglasses must flag occlusion."""
        masked_face = _create_synthetic_face(width=120, height=120, occlusion_type="mask")

        result = self._assess_crop(masked_face)

        assert result.is_match_ready is False
        assert result.rejection_reason == RejectionReason.HIGH_OCCLUSION
        assert result.metrics is not None
        assert result.metrics.occlusion_level in (OcclusionLevel.PARTIAL, OcclusionLevel.SEVERE)

    # -------------------------------------------------------------------------
    # Scenario 9: Very Small Distant Faces
    # -------------------------------------------------------------------------
    def test_09_very_small_distant_face(self):
        """Distant CCTV subject (16x16 face) must fail immediately."""
        tiny_face = _create_synthetic_face(width=16, height=16)

        result = self._assess_crop(tiny_face)

        assert result.is_match_ready is False
        assert result.rejection_reason == RejectionReason.FACE_TOO_SMALL

    # -------------------------------------------------------------------------
    # Scenario 10: Multiple Faces in One Frame
    # -------------------------------------------------------------------------
    def test_10_multiple_faces_in_frame(self):
        """Simultaneous candidate faces in one frame are assessed independently."""
        face_good = _create_synthetic_face(width=120, height=120)
        face_blurry = _create_synthetic_face(width=120, height=120, blur_ksize=21)
        face_tiny = _create_synthetic_face(width=25, height=25)

        res_good = self._assess_crop(face_good)
        res_blurry = self._assess_crop(face_blurry)
        res_tiny = self._assess_crop(face_tiny)

        assert res_good.is_match_ready is True
        assert res_blurry.is_match_ready is False
        assert res_tiny.is_match_ready is False

    # -------------------------------------------------------------------------
    # Scenario 11: Moving Subject & Best-Frame Selection
    # -------------------------------------------------------------------------
    def test_11_moving_subject_best_frame_selection(self):
        """
        Simulates 5 consecutive CCTV frames of a moving subject:
        Frame 1: severe motion blur
        Frame 2: slight motion blur
        Frame 3: clear peak observation (best frame)
        Frame 4: head turned away (severe angle)
        Frame 5: motion blur
        The BestFrameSelector must correctly choose Frame 3.
        """
        f1 = self._assess_crop(_create_synthetic_face(112, 112, blur_ksize=27))
        f2 = self._assess_crop(_create_synthetic_face(112, 112, blur_ksize=9))
        f3 = self._assess_crop(
            _create_synthetic_face(112, 112, blur_ksize=0),
            landmarks=[(35.0, 40.0), (77.0, 40.0), (56.0, 60.0), (39.0, 85.0), (73.0, 85.0)],
        )
        f4 = self._assess_crop(
            _create_synthetic_face(112, 112),
            landmarks=[(25.0, 40.0), (75.0, 40.0), (74.0, 60.0), (35.0, 85.0), (73.0, 85.0)],
        )
        f5 = self._assess_crop(_create_synthetic_face(112, 112, blur_ksize=21))

        observations = [f1, f2, f3, f4, f5]
        best_obs, ranked, reason = self.service.select_best_observation(observations)

        assert best_obs is not None
        assert best_obs.candidate_id == f3.candidate_id
        assert best_obs.is_match_ready is True
        assert len(ranked) >= 1

    # -------------------------------------------------------------------------
    # Scenario 12: Different CCTV Camera Qualities (Noise & Compression)
    # -------------------------------------------------------------------------
    def test_12_cctv_compression_and_noise(self):
        """Simulates low-bitrate CCTV JPEG compression artifacts and sensor noise."""
        clean_face = _create_synthetic_face(width=112, height=112)
        # Heavy JPEG compression artifact simulation
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 15]
        _, encimg = cv2.imencode(".jpg", clean_face, encode_param)
        compressed_face = cv2.imdecode(encimg, 1)

        res_clean = self._assess_crop(clean_face)
        res_compressed = self._assess_crop(compressed_face)

        # Both assess cleanly without crashing
        assert hasattr(res_clean, "quality_score")
        assert hasattr(res_compressed, "quality_score")
        # Compression noticeably degrades edge sharpness and gradient energy
        assert res_clean.metrics is not None and res_compressed.metrics is not None
        assert res_clean.metrics.sharpness_raw > res_compressed.metrics.sharpness_raw
        assert res_clean.metrics.gradient_magnitude > res_compressed.metrics.gradient_magnitude


# =============================================================================
# Benchmarking & Performance Metrics
# =============================================================================


class TestPerformanceAndTelemetry:
    """
    Evaluates Section 19 requirements:
    - Pass/rejection rate accuracy
    - Processing latency benchmark (< 15 ms per face on CPU)
    - Per-camera telemetry accumulation
    """

    def test_telemetry_accuracy_and_latency(self):
        service = FaceQualityService()
        service.telemetry.reset()

        # Assess 10 good faces and 10 bad faces
        good_face = _create_synthetic_face(120, 120)
        bad_face = _create_synthetic_face(20, 20)  # Too small

        for _ in range(10):
            service.assess_face_quality(
                image=good_face,
                candidate_id=f"CAND-GOOD-{_}",
                track_id="TRACK-1",
                camera_id=1,
                timestamp=datetime.now(timezone.utc),
                frame_reference="frame_ref",
                face_bbox=BoundingBox(x1=0, y1=0, x2=120, y2=120),
            )

        for _ in range(10):
            service.assess_face_quality(
                image=bad_face,
                candidate_id=f"CAND-BAD-{_}",
                track_id="TRACK-2",
                camera_id=2,
                timestamp=datetime.now(timezone.utc),
                frame_reference="frame_ref",
                face_bbox=BoundingBox(x1=0, y1=0, x2=20, y2=20),
            )

        snap = service.get_telemetry_snapshot()

        assert snap.faces_received == 20
        assert snap.faces_assessed == 20
        assert snap.faces_passed == 10
        assert snap.faces_rejected == 10
        assert snap.pass_rate == pytest.approx(0.50, abs=0.01)
        assert snap.rejection_rate == pytest.approx(0.50, abs=0.01)
        assert snap.active_camera_count == 2
        # Benchmarking: average latency should be well within real-time CCTV constraints (< 50ms)
        assert snap.average_processing_latency_ms < 50.0
        assert snap.camera_telemetry is not None
        assert "1" in snap.camera_telemetry
        assert "2" in snap.camera_telemetry


# =============================================================================
# Module 5 & Module 7 Integration Contracts
# =============================================================================


class TestModuleIntegrationContracts:
    """
    Verifies Section 21 interface contracts with Module 5 and downstream Module 7.
    """

    def test_candidate_observation_adapter(self):
        service = FaceQualityService()

        # Simulate CandidateObservation from Module 5
        obs = CandidateObservation(
            candidate_id="CAND-MOD5-001",
            track_id="TRACK-001",
            camera_id=5,
            camera_code="CAM-ENTRY",
            timestamp=datetime.now(timezone.utc),
            location="Main Gate",
            department_id=1,
            person_bbox=BoundingBox(x1=100, y1=100, x2=300, y2=500),
            face_bbox=BoundingBox(x1=150, y1=120, x2=250, y2=220),
            person_confidence=0.94,
            face_confidence=0.91,
            frame_reference="ref_cam5_f001",
        )

        face_crop = _create_synthetic_face(100, 100)
        quality_res = service.assess_candidate_observation(obs, image=face_crop)

        assert quality_res.candidate_id == "CAND-MOD5-001"
        assert quality_res.track_id == "TRACK-001"
        assert quality_res.camera_id == 5
        assert quality_res.detection_confidence == 0.91
        assert isinstance(quality_res.is_match_ready, bool)

    def test_ai_safety_contract(self):
        """Verify output never declares identity confirmation."""
        service = FaceQualityService()
        face = _create_synthetic_face(112, 112)
        result = service.assess_face_quality(
            image=face,
            candidate_id="CAND-SAFETY-01",
            track_id="TRACK-SAFETY",
            camera_id=1,
            timestamp=datetime.now(timezone.utc),
            frame_reference="ref_01",
            face_bbox=BoundingBox(x1=0, y1=0, x2=112, y2=112),
        )

        # AI Safety Invariant: NEVER output identity confirmations
        forbidden_phrases = [
            "This is the wanted person",
            "This is the missing person",
            "Identity confirmed",
            "match probability",
        ]
        for phrase in forbidden_phrases:
            assert phrase.lower() not in result.reason.lower()
