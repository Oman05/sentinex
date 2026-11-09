"""
Module 5 – Model Loader
========================
Centralised, lazy-loading model factory with per-device caching.

Design principle: all coupling to specific AI frameworks is isolated here.
To swap a model, change only this file — the rest of the pipeline remains
untouched.

Supported model roles
---------------------
- PERSON_DETECTOR   YOLOv8n (Ultralytics, AGPL-3.0)
- FACE_DETECTOR     MTCNN from facenet-pytorch (MIT)
"""

from __future__ import annotations

import logging
import threading
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal model registry (populated on first use)
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_registry: dict[str, Any] = {}


class ModelRole(str, Enum):
    PERSON_DETECTOR = "person_detector"
    FACE_DETECTOR = "face_detector"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_person_model(device: str, model_path: str = "") -> Any:
    """
    Return a ready-to-use YOLOv8 person-detection model.

    The model is loaded once per (device, model_path) combination and cached
    for the lifetime of the process.

    Parameters
    ----------
    device:
        Torch device string, e.g. ``"cpu"``, ``"cuda"``, ``"cuda:0"``.
    model_path:
        Optional path to a custom ``.pt`` weights file. When empty the
        default ``yolov8n.pt`` is used (downloaded automatically on first
        run to the Ultralytics cache directory).

    Returns
    -------
    An ``ultralytics.YOLO`` instance ready for inference.
    """
    cache_key = f"{ModelRole.PERSON_DETECTOR}:{device}:{model_path}"
    with _lock:
        if cache_key not in _registry:
            _registry[cache_key] = _build_person_model(device, model_path)
    return _registry[cache_key]


def load_face_model(device: str, model_path: str = "") -> Any:
    """
    Return a ready-to-use MTCNN face-detection model.

    Parameters
    ----------
    device:
        Torch device string.
    model_path:
        Currently unused for MTCNN (weights are bundled with facenet-pytorch).
        Reserved for future model-swap capability.

    Returns
    -------
    A ``facenet_pytorch.MTCNN`` instance ready for inference.
    """
    cache_key = f"{ModelRole.FACE_DETECTOR}:{device}:{model_path}"
    with _lock:
        if cache_key not in _registry:
            _registry[cache_key] = _build_face_model(device)
    return _registry[cache_key]


def unload_all() -> None:
    """
    Release all cached models and free GPU/CPU memory.
    Intended for use during controlled service shutdown or testing teardown.
    """
    with _lock:
        _registry.clear()
    logger.info("[ModelLoader] All models unloaded.")


def get_loaded_models() -> list[str]:
    """Return cache keys of currently loaded models (for diagnostics)."""
    with _lock:
        return list(_registry.keys())


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Native OpenCV Fallback Detectors (Zero external heavy dependencies)
# ---------------------------------------------------------------------------

class _BoxWrapper:
    def __init__(self, xyxy: list[float], conf: float) -> None:
        self.xyxy = [xyxy]
        self.conf = [conf]


class _ResultWrapper:
    def __init__(self, boxes: list[_BoxWrapper]) -> None:
        self.boxes = boxes


class OpenCVHOGPersonModel:
    """
    Standard OpenCV HOG person detector fallback.
    Provides identical .predict() interface to ultralytics.YOLO.
    """

    def __init__(self) -> None:
        import cv2  # noqa: PLC0415
        self._cv2 = cv2
        self._hog = cv2.HOGDescriptor()
        self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def to(self, device: str) -> "OpenCVHOGPersonModel":
        return self

    def predict(
        self,
        frame: Any,
        conf: float = 0.35,
        classes: list[int] | None = None,
        verbose: bool = False,
        stream: bool = False,
    ) -> list[_ResultWrapper]:
        import numpy as np  # noqa: PLC0415
        if frame is None or getattr(frame, "size", 0) == 0:
            return [_ResultWrapper([])]

        h, w = frame.shape[:2]
        # Run HOG detector with scale stepping
        rects, weights = self._hog.detectMultiScale(
            frame, winStride=(8, 8), padding=(8, 8), scale=1.05
        )

        boxes: list[_BoxWrapper] = []
        for (rx, ry, rw, rh), weight in zip(rects, weights):
            raw_w = float(weight[0]) if hasattr(weight, "__len__") else float(weight)
            # Map SVM margin score to probabilistic confidence [0, 1]
            c_norm = float(1.0 / (1.0 + np.exp(-raw_w)))
            if c_norm >= conf or raw_w >= 0.0:
                score = max(c_norm, 0.50)
                boxes.append(
                    _BoxWrapper(
                        [float(rx), float(ry), float(rx + rw), float(ry + rh)],
                        score,
                    )
                )

        return [_ResultWrapper(boxes)]


class OpenCVYuNetFaceModel:
    """
    OpenCV YuNet ONNX face detector fallback.
    Provides identical .detect(img, landmarks=True) interface to facenet_pytorch.MTCNN.
    """

    def __init__(self, model_path: str | None = None) -> None:
        import cv2  # noqa: PLC0415
        from pathlib import Path  # noqa: PLC0415

        root = Path(__file__).resolve().parents[5]
        candidate_paths = [
            Path(model_path) if model_path else None,
            root / "backend" / "face_detection_yunet_2023mar.onnx",
            Path("backend/face_detection_yunet_2023mar.onnx"),
            Path("/home/oman/workshop/sentinex/backend/face_detection_yunet_2023mar.onnx"),
        ]

        resolved_path = None
        for p in candidate_paths:
            if p and p.is_file():
                resolved_path = str(p)
                break

        if not resolved_path:
            raise FileNotFoundError("YuNet ONNX model face_detection_yunet_2023mar.onnx not found")

        self._detector = cv2.FaceDetectorYN.create(
            resolved_path, "", (320, 320), 0.50, 0.30, 20
        )
        self._current_size = (320, 320)
        self._cv2 = cv2

    def detect(
        self, img: Any, landmarks: bool = True
    ) -> tuple[Any, Any, Any]:
        import numpy as np  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415

        if isinstance(img, Image.Image):
            arr = np.array(img)
            bgr = self._cv2.cvtColor(arr, self._cv2.COLOR_RGB2BGR)
        elif isinstance(img, np.ndarray):
            bgr = img if img.ndim == 3 else self._cv2.cvtColor(img, self._cv2.COLOR_GRAY2BGR)
        else:
            return None, None, None

        if bgr.size == 0:
            return None, None, None

        h, w = bgr.shape[:2]
        if (w, h) != self._current_size:
            self._detector.setInputSize((w, h))
            self._current_size = (w, h)

        count, faces = self._detector.detect(bgr)
        if faces is None or count == 0:
            return None, None, None

        boxes: list[list[float]] = []
        probs: list[float] = []
        all_landmarks: list[list[tuple[float, float]]] = []

        for face in faces:
            fx, fy, fw, fh = float(face[0]), float(face[1]), float(face[2]), float(face[3])
            conf = float(face[14])
            boxes.append([fx, fy, fx + fw, fy + fh])
            probs.append(conf)
            if landmarks:
                lms = [(float(face[4 + 2 * i]), float(face[5 + 2 * i])) for i in range(5)]
                all_landmarks.append(lms)

        return (
            np.array(boxes, dtype=np.float32),
            np.array(probs, dtype=np.float32),
            all_landmarks if landmarks else None,
        )


# ---------------------------------------------------------------------------
# Private builders – one per model family
# ---------------------------------------------------------------------------


def _build_person_model(device: str, model_path: str) -> Any:
    """
    Instantiate and warm-up the person-detection model.
    Attempts YOLOv8; gracefully falls back to native OpenCV HOG detector.
    """
    try:
        from ultralytics import YOLO  # noqa: PLC0415
        weights = model_path if model_path else "yolov8n.pt"
        logger.info("[ModelLoader] Loading YOLO person detector: %s on device=%s", weights, device)
        model = YOLO(weights)
        model.to(device)
        logger.info("[ModelLoader] YOLO person detector ready.")
        return model
    except Exception as exc:
        logger.info(
            "[ModelLoader] Ultralytics YOLO not available (%s). Using native OpenCV HOG person detector.",
            exc,
        )
        return OpenCVHOGPersonModel()


def _build_face_model(device: str) -> Any:
    """
    Instantiate the face-detection model.
    Attempts MTCNN from facenet-pytorch; gracefully falls back to OpenCV YuNet ONNX.
    """
    try:
        import torch  # noqa: PLC0415
        from facenet_pytorch import MTCNN  # noqa: PLC0415

        logger.info("[ModelLoader] Loading MTCNN face detector on device=%s", device)
        torch_device = torch.device(device)
        model = MTCNN(
            keep_all=True,
            device=torch_device,
            post_process=False,
            select_largest=False,
        )
        logger.info("[ModelLoader] MTCNN face detector ready.")
        return model
    except Exception as exc:
        logger.info(
            "[ModelLoader] MTCNN not available (%s). Using native OpenCV YuNet ONNX face detector.",
            exc,
        )
        return OpenCVYuNetFaceModel()
