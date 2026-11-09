"""
Module 5 – Person Detector
============================
Wraps the YOLOv8 object-detection model to detect people in CCTV frames.

Design contract
---------------
- Input:  a raw NumPy BGR frame (as produced by OpenCV / Module 4).
- Output: a list of ``PersonDetection`` objects (may be empty).
- The detector is stateless — call ``detect()`` per frame.
- Coupling to a specific model is minimal: change ``model_loader.py`` to
  swap the underlying model without touching this file.

Important design rule
---------------------
The ``detection_confidence`` in ``PersonDetection`` reflects the object-
detection model's class confidence. It must NEVER be interpreted as identity
confidence or used in downstream matching decisions.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import numpy as np

from app.ai_engine.config.settings import ai_settings
from app.ai_engine.detection.model_loader import load_person_model
from app.ai_engine.schemas.observations import BoundingBox, PersonDetection

logger = logging.getLogger(__name__)

# COCO class index for "person"
_PERSON_CLASS_ID = 0


class PersonDetector:
    """
    Stateless person detector backed by YOLOv8.

    Usage
    -----
    >>> detector = PersonDetector()
    >>> detections = detector.detect(frame, camera_id=1, timestamp=..., frame_ref="...")
    """

    def __init__(
        self,
        device: str | None = None,
        model_path: str | None = None,
        confidence_threshold: float | None = None,
    ) -> None:
        """
        Parameters
        ----------
        device:
            Torch device string. Defaults to ``ai_settings.resolve_device()``.
        model_path:
            Path to custom YOLO weights. Defaults to ``ai_settings.PERSON_MODEL_PATH``.
        confidence_threshold:
            Minimum confidence to accept. Defaults to ``ai_settings.PERSON_DETECTION_THRESHOLD``.
        """
        self._device = device or ai_settings.resolve_device()
        self._model_path = model_path if model_path is not None else ai_settings.PERSON_MODEL_PATH
        self._threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else ai_settings.PERSON_DETECTION_THRESHOLD
        )
        self._model: Any | None = None

    # -------------------------------------------------------------------------
    # Model lifecycle
    # -------------------------------------------------------------------------

    def _ensure_model(self) -> Any:
        """Lazy-load and cache the underlying model on first inference call."""
        if self._model is None:
            self._model = load_person_model(self._device, self._model_path)
        return self._model

    def warm_up(self) -> None:
        """
        Pre-load the model into memory and run a single dummy inference pass.
        Call this during service startup to avoid first-frame latency spikes.
        """
        model = self._ensure_model()
        dummy = np.zeros((480, 640, 3), dtype=np.uint8)
        try:
            model.predict(dummy, verbose=False, classes=[_PERSON_CLASS_ID])
            logger.info("[PersonDetector] Warm-up complete (device=%s).", self._device)
        except Exception as exc:
            logger.warning("[PersonDetector] Warm-up failed: %s", exc)

    # -------------------------------------------------------------------------
    # Public interface
    # -------------------------------------------------------------------------

    def detect(
        self,
        frame: np.ndarray,
        camera_id: int,
        timestamp: datetime,
        frame_reference: str,
    ) -> list[PersonDetection]:
        """
        Detect all people in ``frame``.

        Parameters
        ----------
        frame:
            BGR NumPy array (H × W × 3) from OpenCV.
        camera_id:
            ID of the originating camera (propagated into detection metadata).
        timestamp:
            UTC capture timestamp of the frame.
        frame_reference:
            Opaque reference string linking to the source frame.

        Returns
        -------
        A (possibly empty) list of ``PersonDetection`` objects.
        Each detection includes a bounding box and model confidence score.

        Raises
        ------
        RuntimeError
            If the underlying model raises an unrecoverable error during inference.
        """
        if frame is None or frame.size == 0:
            logger.debug("[PersonDetector] Received empty frame; skipping detection.")
            return []

        h, w = frame.shape[:2]
        model = self._ensure_model()

        try:
            results = model.predict(
                frame,
                conf=self._threshold,
                classes=[_PERSON_CLASS_ID],
                verbose=False,
                stream=False,
            )
        except Exception as exc:
            raise RuntimeError(f"[PersonDetector] Model inference failed: {exc}") from exc

        detections: list[PersonDetection] = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                try:
                    conf = float(box.conf[0])
                    if conf < self._threshold:
                        continue

                    xyxy = box.xyxy[0].tolist()
                    x1, y1, x2, y2 = xyxy

                    bbox = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)

                    # Reject detections that are too small to be useful
                    if bbox.area < ai_settings.MIN_PERSON_BBOX_AREA:
                        logger.debug(
                            "[PersonDetector] Rejecting small detection (area=%.0f < %d).",
                            bbox.area,
                            ai_settings.MIN_PERSON_BBOX_AREA,
                        )
                        continue

                    detection = PersonDetection(
                        camera_id=camera_id,
                        timestamp=timestamp,
                        bounding_box=bbox.clamp(w, h),
                        detection_confidence=conf,
                        frame_reference=frame_reference,
                        frame_width=w,
                        frame_height=h,
                    )
                    detections.append(detection)

                except Exception as box_exc:
                    logger.warning(
                        "[PersonDetector] Failed to parse detection box: %s", box_exc
                    )

        logger.debug(
            "[PersonDetector] camera_id=%d | frame=%s | detected=%d",
            camera_id,
            frame_reference,
            len(detections),
        )
        return detections
