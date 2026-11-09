"""Module 5 Detection Package."""

from app.ai_engine.detection.face_detector import FaceDetector
from app.ai_engine.detection.model_loader import (
    ModelRole,
    get_loaded_models,
    load_face_model,
    load_person_model,
    unload_all,
)
from app.ai_engine.detection.person_detector import PersonDetector

__all__ = [
    "FaceDetector",
    "ModelRole",
    "PersonDetector",
    "get_loaded_models",
    "load_face_model",
    "load_person_model",
    "unload_all",
]
