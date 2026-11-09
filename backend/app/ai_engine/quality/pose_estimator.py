"""
Module 6 – Face Pose & Angle Estimator
========================================
Estimates approximate head orientation (yaw, pitch, roll) from facial landmarks
or facial symmetry. Classifies observations into FRONTAL, SLIGHTLY_ANGLED,
STRONGLY_ANGLED, or UNKNOWN.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import cv2
import numpy as np

from app.ai_engine.config.quality_settings import quality_settings
from app.ai_engine.schemas.quality import PoseClassification


@dataclass(frozen=True)
class PoseEstimationResult:
    """Outcome of facial pose estimation."""
    yaw: float
    pitch: float
    roll: float
    max_angle: float
    classification: PoseClassification
    pose_score: float
    is_acceptable_pose: bool


class PoseEstimator:
    """
    Estimates 3D head pose angles (yaw, pitch, roll) in degrees.
    Leverages 5-point facial landmarks when provided by Module 5;
    falls back to bilateral facial symmetry analysis when landmarks are absent.
    """

    def __init__(
        self,
        max_yaw: float | None = None,
        max_pitch: float | None = None,
        max_roll: float | None = None,
    ) -> None:
        self.max_yaw = max_yaw if max_yaw is not None else quality_settings.MAX_POSE_YAW
        self.max_pitch = max_pitch if max_pitch is not None else quality_settings.MAX_POSE_PITCH
        self.max_roll = max_roll if max_roll is not None else quality_settings.MAX_POSE_ROLL

    def estimate(
        self,
        landmarks: Sequence[tuple[float, float]] | None = None,
        face_crop: np.ndarray | None = None,
    ) -> PoseEstimationResult:
        """
        Estimate pose from landmarks or face crop.
        
        Parameters:
            landmarks: Optional 5-point facial coordinates:
                       [left_eye, right_eye, nose, left_mouth, right_mouth]
            face_crop: Optional BGR face crop array.
        """
        yaw = 0.0
        pitch = 0.0
        roll = 0.0
        has_estimate = False

        # Approach 1: Geometry from 5-point landmarks
        if landmarks and len(landmarks) >= 5:
            try:
                le, re, nose, lm, rm = landmarks[:5]
                # Roll angle from eye-line tilt
                dx = re[0] - le[0]
                dy = re[1] - le[1]
                roll = math.degrees(math.atan2(dy, dx))

                eye_dist = math.hypot(dx, dy)
                if eye_dist > 1.0:
                    eye_mid_x = (le[0] + re[0]) / 2.0
                    eye_mid_y = (le[1] + re[1]) / 2.0
                    mouth_mid_x = (lm[0] + rm[0]) / 2.0
                    mouth_mid_y = (lm[1] + rm[1]) / 2.0

                    # Yaw approximation from horizontal nose shift relative to eye midpoint
                    # When perfectly frontal, nose is exactly halfway between eyes
                    half_eye = eye_dist / 2.0
                    nose_dx = nose[0] - eye_mid_x
                    yaw = (nose_dx / half_eye) * 45.0  # Scale factor maps offset to degrees

                    # Pitch approximation from nose vertical position relative to eye-mouth span
                    face_h_span = math.hypot(mouth_mid_x - eye_mid_x, mouth_mid_y - eye_mid_y)
                    if face_h_span > 1.0:
                        nose_dy = nose[1] - eye_mid_y
                        expected_nose_y = face_h_span * 0.45
                        pitch = ((nose_dy - expected_nose_y) / (face_h_span * 0.5)) * 30.0

                    has_estimate = True
            except Exception:
                has_estimate = False

        # Approach 2: Symmetry-based fallback on face crop
        if not has_estimate and face_crop is not None and face_crop.size > 0:
            try:
                h, w = face_crop.shape[:2]
                if w >= 20 and h >= 20:
                    gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY) if face_crop.ndim == 3 else face_crop
                    mid = w // 2
                    left_half = gray[:, :mid]
                    right_half = cv2.flip(gray[:, w - mid:], 1)

                    # Compute structural symmetry between left and right halves
                    diff = np.abs(left_half.astype(float) - right_half.astype(float))
                    mean_diff = float(np.mean(diff))
                    # High discrepancy indicates asymmetrical lighting or profile/angled pose
                    yaw = min(50.0, (mean_diff / 30.0) * 25.0)
                    has_estimate = True
            except Exception:
                has_estimate = False

        if not has_estimate:
            return PoseEstimationResult(
                yaw=0.0,
                pitch=0.0,
                roll=0.0,
                max_angle=0.0,
                classification=PoseClassification.UNKNOWN,
                pose_score=0.75,  # Neutral default when unknown
                is_acceptable_pose=True,
            )

        yaw = float(np.clip(yaw, -90.0, 90.0))
        pitch = float(np.clip(pitch, -90.0, 90.0))
        roll = float(np.clip(roll, -90.0, 90.0))

        max_ang = max(abs(yaw), abs(pitch), abs(roll))

        # Classification
        if max_ang <= 12.0:
            classification = PoseClassification.FRONTAL
        elif max_ang <= max(self.max_yaw, self.max_pitch, self.max_roll):
            classification = PoseClassification.SLIGHTLY_ANGLED
        else:
            classification = PoseClassification.STRONGLY_ANGLED

        # Normalized pose score (1.0 for frontal, falling off smoothly)
        pose_score = float(np.clip(1.0 - (max_ang / 60.0), 0.0, 1.0))

        is_acceptable = (
            abs(yaw) <= self.max_yaw
            and abs(pitch) <= self.max_pitch
            and abs(roll) <= self.max_roll
        )

        return PoseEstimationResult(
            yaw=round(yaw, 2),
            pitch=round(pitch, 2),
            roll=round(roll, 2),
            max_angle=round(max_ang, 2),
            classification=classification,
            pose_score=round(pose_score, 4),
            is_acceptable_pose=is_acceptable,
        )
