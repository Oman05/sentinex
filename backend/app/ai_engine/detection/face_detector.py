"""
Module 5 – Face Detector
==========================
Detects faces within person-crop regions using MTCNN (facenet-pytorch, MIT).

Design contract
---------------
- Input:  the original BGR frame + a list of ``PersonDetection`` objects.
- Output: a list of ``FaceDetection`` objects (may be empty).
- Faces are detected within the bounding box of each detected person,
  not on the full frame. This reduces false positives significantly.
- The detector is stateless — call ``detect()`` per frame.

Important design rule
---------------------
``face_detection_confidence`` reflects the MTCNN confidence score only.
It must NEVER be interpreted as face-recognition or identity confidence.

If no usable face is detected for a person, the candidate observation will
proceed without a face crop — it will not be eligible for face matching
but is still logged as a person detection event.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import numpy as np

from app.ai_engine.config.settings import ai_settings
from app.ai_engine.detection.model_loader import load_face_model
from app.ai_engine.schemas.observations import BoundingBox, FaceDetection, PersonDetection

logger = logging.getLogger(__name__)

# Minimum face bounding-box size (in pixels, applied to the original frame)
_MIN_FACE_SIZE_PX = 20


class FaceDetector:
    """
    Stateless face detector backed by MTCNN.

    Operates on person-crop ROIs to reduce false positives and improve
    detection accuracy on CCTV-scale faces.

    Usage
    -----
    >>> detector = FaceDetector()
    >>> face_detections = detector.detect(frame, person_detections)
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
            Reserved for future model swap; currently unused by MTCNN.
        confidence_threshold:
            Minimum face-detection probability. Defaults to
            ``ai_settings.FACE_DETECTION_THRESHOLD``.
        """
        self._device = device or ai_settings.resolve_device()
        self._model_path = model_path if model_path is not None else ai_settings.FACE_MODEL_PATH
        self._threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else ai_settings.FACE_DETECTION_THRESHOLD
        )
        self._model: Any | None = None

    # -------------------------------------------------------------------------
    # Model lifecycle
    # -------------------------------------------------------------------------

    def _ensure_model(self) -> Any:
        """Lazy-load the MTCNN model on first call."""
        if self._model is None:
            self._model = load_face_model(self._device, self._model_path)
        return self._model

    def warm_up(self) -> None:
        """Pre-warm the model with a dummy crop."""
        _ = self._ensure_model()
        dummy = np.zeros((112, 112, 3), dtype=np.uint8)
        try:
            self._run_mtcnn(dummy)
            logger.info("[FaceDetector] Warm-up complete (device=%s).", self._device)
        except Exception as exc:
            logger.warning("[FaceDetector] Warm-up failed: %s", exc)

    # -------------------------------------------------------------------------
    # Public interface
    # -------------------------------------------------------------------------

    def detect(
        self,
        frame: np.ndarray,
        person_detections: list[PersonDetection],
    ) -> list[FaceDetection]:
        """
        Detect faces associated with the supplied person detections.

        For each person, the corresponding crop region is extracted from the
        full frame and passed to MTCNN. Any detected face box is mapped back
        to original frame coordinates.

        Parameters
        ----------
        frame:
            Full BGR frame from OpenCV.
        person_detections:
            List of ``PersonDetection`` objects from the person detector.

        Returns
        -------
        A (possibly empty) list of ``FaceDetection`` objects. Each face is
        linked to its parent ``PersonDetection`` via ``person_detection_id``.

        Notes
        -----
        - At most one face is associated with each person detection (the
          highest-confidence face within that crop).
        - If a person crop contains no detectable face the person detection
          still proceeds; the candidate will be flagged with ``has_face=False``.
        """
        if frame is None or frame.size == 0:
            return []

        if not person_detections:
            return []

        face_detections: list[FaceDetection] = []
        h, w = frame.shape[:2]

        for person in person_detections:
            try:
                face = self._detect_face_in_person(frame, person, w, h)
                if face is not None:
                    face_detections.append(face)
            except Exception as exc:
                logger.warning(
                    "[FaceDetector] Face detection failed for person %s: %s",
                    person.detection_id,
                    exc,
                )

        logger.debug(
            "[FaceDetector] persons=%d | faces_found=%d",
            len(person_detections),
            len(face_detections),
        )
        return face_detections

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _detect_face_in_person(
        self,
        frame: np.ndarray,
        person: PersonDetection,
        frame_w: int,
        frame_h: int,
    ) -> FaceDetection | None:
        """
        Run MTCNN on the person-crop region and return the best face.

        The crop is derived from the person's bounding box with a small
        vertical bias toward the top (faces are typically in the upper portion).

        Returns ``None`` if no face meets the confidence threshold.
        """
        bbox = person.bounding_box
        x1 = max(0, int(bbox.x1))
        y1 = max(0, int(bbox.y1))
        x2 = min(frame_w, int(bbox.x2))
        y2 = min(frame_h, int(bbox.y2))

        if x2 <= x1 or y2 <= y1:
            return None

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None

        # Convert BGR to RGB for MTCNN
        rgb_crop = crop[:, :, ::-1].copy()

        boxes, probs, landmarks = self._run_mtcnn(rgb_crop)

        if boxes is None or len(boxes) == 0:
            return None

        # Select the highest-confidence face within this crop
        best_idx = int(np.argmax(probs))
        best_conf = float(probs[best_idx])

        if best_conf < self._threshold:
            return None

        # Map face box from crop space back to full-frame coordinates
        fx1, fy1, fx2, fy2 = boxes[best_idx]
        face_bbox = BoundingBox(
            x1=float(fx1) + x1,
            y1=float(fy1) + y1,
            x2=float(fx2) + x1,
            y2=float(fy2) + y1,
        ).clamp(frame_w, frame_h)

        # Reject faces that are unreasonably small
        if face_bbox.width < _MIN_FACE_SIZE_PX or face_bbox.height < _MIN_FACE_SIZE_PX:
            logger.debug(
                "[FaceDetector] Rejecting tiny face (%.0f×%.0f px).",
                face_bbox.width,
                face_bbox.height,
            )
            return None

        # Map landmark points back to full-frame coordinates if available
        mapped_landmarks: list[tuple[float, float]] | None = None
        if landmarks is not None and landmarks[best_idx] is not None:
            raw_lm = landmarks[best_idx]
            mapped_landmarks = [
                (float(pt[0]) + x1, float(pt[1]) + y1) for pt in raw_lm
            ]

        return FaceDetection(
            person_detection_id=person.detection_id,
            bounding_box=face_bbox,
            face_detection_confidence=best_conf,
            frame_reference=person.frame_reference,
            timestamp=person.timestamp,
            landmark_points=mapped_landmarks,
        )

    def detect_on_frame(
        self,
        frame: np.ndarray,
        timestamp: datetime,
        frame_reference: str,
    ) -> list[FaceDetection]:
        """
        Directly detect faces across the entire frame.
        Ensures detections are not lost if body detection misses seated or close-up subjects.
        """
        if frame is None or frame.size == 0:
            return []

        h, w = frame.shape[:2]
        rgb_frame = frame[:, :, ::-1].copy()
        boxes, probs, landmarks = self._run_mtcnn(rgb_frame)
        if boxes is None or len(boxes) == 0:
            return []

        detections: list[FaceDetection] = []
        for i, (box, conf) in enumerate(zip(boxes, probs)):
            if float(conf) < self._threshold:
                continue
            fx1, fy1, fx2, fy2 = box
            face_bbox = BoundingBox(
                x1=float(fx1),
                y1=float(fy1),
                x2=float(fx2),
                y2=float(fy2),
            ).clamp(w, h)

            if face_bbox.width < _MIN_FACE_SIZE_PX or face_bbox.height < _MIN_FACE_SIZE_PX:
                continue

            mapped_landmarks = None
            if landmarks is not None and i < len(landmarks) and landmarks[i] is not None:
                mapped_landmarks = [(float(pt[0]), float(pt[1])) for pt in landmarks[i]]

            detections.append(
                FaceDetection(
                    person_detection_id=f"DIRECT-FACE-{i}",
                    bounding_box=face_bbox,
                    face_detection_confidence=float(conf),
                    frame_reference=frame_reference,
                    timestamp=timestamp,
                    landmark_points=mapped_landmarks,
                )
            )
        return detections

    def _run_mtcnn(
        self, rgb_image: np.ndarray
    ) -> tuple[Any, Any, Any]:
        """
        Internal wrapper around MTCNN / YuNet inference.

        Returns (boxes, probs, landmarks) — any of which may be None if
        no faces are detected.
        """
        model = self._ensure_model()
        try:
            if hasattr(model, "detect"):
                # YuNet or MTCNN detect interface
                return model.detect(rgb_image, landmarks=True)
            from PIL import Image  # noqa: PLC0415

            pil_img = Image.fromarray(rgb_image)
            boxes, probs, landmarks = model.detect(pil_img, landmarks=True)
            return boxes, probs, landmarks
        except Exception as exc:
            logger.debug("[FaceDetector] Face detector inference error: %s", exc)
            return None, None, None
