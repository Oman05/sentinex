"""
Module 6 – Face Image Validator
=================================
Validates incoming face images or crops before processing.
Checks existence, decodability, non-empty dimensions, channels, and corruption.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class ImageValidationStatus(str, Enum):
    VALID = "VALID"
    MISSING_IMAGE = "MISSING_IMAGE"
    DECODE_ERROR = "DECODE_ERROR"
    ZERO_SIZE = "ZERO_SIZE"
    CORRUPT_ALL_BLACK = "CORRUPT_ALL_BLACK"
    INVALID_CHANNELS = "INVALID_CHANNELS"


@dataclass
class ValidatedImage:
    """A verified BGR image array with metadata."""
    image_bgr: np.ndarray
    width: int
    height: int
    channels: int
    status: ImageValidationStatus = ImageValidationStatus.VALID


class FaceImageValidator:
    """Stateless image validator for face crops and CCTV frames."""

    @staticmethod
    def decode_base64(data: str) -> np.ndarray | None:
        """Decode base64 image data (with or without data URI header) to BGR NumPy array."""
        try:
            if "," in data:
                data = data.split(",", 1)[1]
            raw_bytes = base64.b64decode(data)
            nparr = np.frombuffer(raw_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return img
        except Exception as exc:
            logger.warning("[ImageValidator] Base64 decode failed: %s", exc)
            return None

    @staticmethod
    def load_from_reference(ref: str) -> np.ndarray | None:
        """Load image array from file path or storage reference if it exists."""
        import os
        try:
            if os.path.isfile(ref):
                return cv2.imread(ref, cv2.IMREAD_COLOR)
        except Exception as exc:
            logger.warning("[ImageValidator] File load failed for reference '%s': %s", ref, exc)
        return None

    @staticmethod
    def validate(
        image: Any,
        face_bbox: Any = None,
        frame_width: int | None = None,
        frame_height: int | None = None,
    ) -> tuple[ValidatedImage | None, ImageValidationStatus]:
        """
        Validate an input image (NumPy array, base64 string, or file reference).
        
        Returns:
            (ValidatedImage, VALID) if usable, else (None, <error_status>).
        """
        if image is None:
            return None, ImageValidationStatus.MISSING_IMAGE

        if isinstance(image, str):
            # Check if it's a file path reference first
            loaded = FaceImageValidator.load_from_reference(image)
            if loaded is not None:
                image = loaded
            else:
                decoded = FaceImageValidator.decode_base64(image)
                if decoded is None:
                    return None, ImageValidationStatus.DECODE_ERROR
                image = decoded

        if not isinstance(image, np.ndarray):
            return None, ImageValidationStatus.DECODE_ERROR

        if image.size == 0 or image.ndim not in (2, 3):
            return None, ImageValidationStatus.ZERO_SIZE

        h, w = image.shape[:2]
        if w <= 0 or h <= 0:
            return None, ImageValidationStatus.ZERO_SIZE

        # Channel normalization
        if image.ndim == 2:
            # Grayscale -> convert to 3-channel BGR
            image_bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        elif image.shape[2] == 4:
            # BGRA -> strip alpha
            image_bgr = image[:, :, :3]
        elif image.shape[2] == 3:
            image_bgr = image
        else:
            return None, ImageValidationStatus.INVALID_CHANNELS

        # Corruption check: completely all-zero array
        if not np.any(image_bgr):
            return None, ImageValidationStatus.CORRUPT_ALL_BLACK

        return ValidatedImage(
            image_bgr=image_bgr,
            width=w,
            height=h,
            channels=3,
            status=ImageValidationStatus.VALID,
        ), ImageValidationStatus.VALID
