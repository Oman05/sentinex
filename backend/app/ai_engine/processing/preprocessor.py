"""
Module 5 – Frame Preprocessor
================================
Validates and prepares incoming ``FrameMetadata`` objects before they enter
the detection pipeline.

Responsibilities
----------------
- Validate that required metadata fields are present and non-trivial.
- Check frame dimensions against configured minimums.
- Detect corrupt or zero-filled frames.
- Normalise colour-space if required (frames arrive as BGR from OpenCV).
- Preserve all relevant metadata; do not discard anything needed downstream.

Non-responsibilities
--------------------
- Do NOT permanently store the raw frame.
- Do NOT perform any AI inference.
- Do NOT resize frames (the YOLO model handles its own input scaling).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import numpy as np

from app.ai_engine.config.settings import ai_settings
from app.utils.frame_queue import FrameMetadata

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------


class ValidationResult(str, Enum):
    VALID = "VALID"
    MISSING_METADATA = "MISSING_METADATA"
    MISSING_FRAME = "MISSING_FRAME"
    INVALID_DIMENSIONS = "INVALID_DIMENSIONS"
    CORRUPT_FRAME = "CORRUPT_FRAME"
    WRONG_CHANNELS = "WRONG_CHANNELS"


@dataclass
class PreprocessedFrame:
    """
    A validated, preprocessed frame ready for detection.

    The ``frame`` field is a guaranteed-valid BGR NumPy array.
    All original metadata is preserved in the remaining fields.
    """

    frame: np.ndarray
    camera_id: int
    camera_code: str
    timestamp: datetime
    location: str | None
    department_id: int
    frame_reference: str
    frame_width: int
    frame_height: int

    @classmethod
    def from_metadata(cls, meta: FrameMetadata, frame: np.ndarray) -> PreprocessedFrame:
        h, w = frame.shape[:2]
        return cls(
            frame=frame,
            camera_id=meta.camera_id,
            camera_code=meta.camera_code,
            timestamp=meta.captured_at,
            location=meta.location_name,
            department_id=meta.department_id,
            frame_reference=meta.frame_reference,
            frame_width=w,
            frame_height=h,
        )


# ---------------------------------------------------------------------------
# Preprocessor
# ---------------------------------------------------------------------------


class FramePreprocessor:
    """
    Validates and preprocesses incoming CCTV frames.

    This class is stateless — call ``preprocess()`` per frame. It never
    stores frames on disk or in memory beyond the lifetime of a single call.
    """

    def preprocess(
        self, frame_meta: FrameMetadata
    ) -> tuple[PreprocessedFrame | None, ValidationResult]:
        """
        Validate and prepare a ``FrameMetadata`` object for AI processing.

        Parameters
        ----------
        frame_meta:
            Incoming frame from Module 4's ``BoundedFrameQueue``.

        Returns
        -------
        A tuple of ``(PreprocessedFrame | None, ValidationResult)``.
        On success, ``ValidationResult`` is ``VALID`` and the first element
        is a ``PreprocessedFrame``. On failure, the first element is ``None``
        and the result describes the failure reason.
        """
        # ----------------------------------------------------------------
        # 1. Metadata presence checks
        # ----------------------------------------------------------------
        if frame_meta is None:
            logger.warning("[Preprocessor] Received None FrameMetadata.")
            return None, ValidationResult.MISSING_METADATA

        if not frame_meta.camera_id:
            logger.warning("[Preprocessor] FrameMetadata missing camera_id.")
            return None, ValidationResult.MISSING_METADATA

        if frame_meta.captured_at is None:
            logger.warning(
                "[Preprocessor] camera_id=%d | Missing captured_at timestamp.",
                frame_meta.camera_id,
            )
            return None, ValidationResult.MISSING_METADATA

        # ----------------------------------------------------------------
        # 2. Frame presence check
        # ----------------------------------------------------------------
        frame = frame_meta.frame
        if frame is None:
            logger.warning(
                "[Preprocessor] camera_id=%d | Frame data is None.",
                frame_meta.camera_id,
            )
            return None, ValidationResult.MISSING_FRAME

        if not isinstance(frame, np.ndarray):
            logger.warning(
                "[Preprocessor] camera_id=%d | Frame is not a NumPy array (type=%s).",
                frame_meta.camera_id,
                type(frame).__name__,
            )
            return None, ValidationResult.MISSING_FRAME

        if frame.size == 0:
            logger.warning(
                "[Preprocessor] camera_id=%d | Frame array is empty.",
                frame_meta.camera_id,
            )
            return None, ValidationResult.MISSING_FRAME

        # ----------------------------------------------------------------
        # 3. Dimension checks
        # ----------------------------------------------------------------
        if frame.ndim not in (2, 3):
            logger.warning(
                "[Preprocessor] camera_id=%d | Unexpected frame ndim=%d.",
                frame_meta.camera_id,
                frame.ndim,
            )
            return None, ValidationResult.INVALID_DIMENSIONS

        h, w = frame.shape[:2]

        if w < ai_settings.MIN_FRAME_WIDTH or h < ai_settings.MIN_FRAME_HEIGHT:
            logger.warning(
                "[Preprocessor] camera_id=%d | Frame too small: %dx%d (min %dx%d).",
                frame_meta.camera_id,
                w,
                h,
                ai_settings.MIN_FRAME_WIDTH,
                ai_settings.MIN_FRAME_HEIGHT,
            )
            return None, ValidationResult.INVALID_DIMENSIONS

        # ----------------------------------------------------------------
        # 4. Channel normalisation
        # ----------------------------------------------------------------
        if frame.ndim == 2:
            # Greyscale → convert to 3-channel BGR for model compatibility
            import cv2  # noqa: PLC0415
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        elif frame.shape[2] == 4:
            # BGRA → strip alpha channel
            frame = frame[:, :, :3]
        elif frame.shape[2] != 3:
            logger.warning(
                "[Preprocessor] camera_id=%d | Unsupported channel count: %d.",
                frame_meta.camera_id,
                frame.shape[2],
            )
            return None, ValidationResult.WRONG_CHANNELS

        # ----------------------------------------------------------------
        # 5. Corruption check — reject completely blank (all-zero) frames
        # ----------------------------------------------------------------
        if not np.any(frame):
            logger.warning(
                "[Preprocessor] camera_id=%d | Frame is entirely black (possible corruption).",
                frame_meta.camera_id,
            )
            return None, ValidationResult.CORRUPT_FRAME

        # ----------------------------------------------------------------
        # All checks passed
        # ----------------------------------------------------------------
        preprocessed = PreprocessedFrame.from_metadata(frame_meta, frame)
        logger.debug(
            "[Preprocessor] camera_id=%d | Frame %s OK (%dx%d).",
            frame_meta.camera_id,
            frame_meta.frame_reference,
            w,
            h,
        )
        return preprocessed, ValidationResult.VALID
