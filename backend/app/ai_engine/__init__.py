"""
Module 5: AI Video Processing
==============================
Receives authorised live CCTV frames from Module 4, performs computer-vision
perception (person detection, face detection, short-term tracking, duplicate
filtering) and produces structured CandidateObservation objects for downstream
modules.

This module does NOT make identity decisions.
"""

from app.ai_engine.config.settings import AIEngineSettings, ai_settings
from app.ai_engine.metrics.performance_monitor import (
    CameraMetricsSnapshot,
    PerformanceMonitor,
    performance_monitor,
)
from app.ai_engine.pipeline.processing_pipeline import (
    CandidateHandler,
    VideoProcessingPipeline,
    video_pipeline,
)
from app.ai_engine.schemas.observations import (
    BoundingBox,
    CandidateObservation,
    FaceDetection,
    PersonDetection,
    ProcessingStatus,
    QualityStatus,
    TrackState,
    TrackStatus,
)

__all__ = [
    "AIEngineSettings",
    "BoundingBox",
    "CameraMetricsSnapshot",
    "CandidateHandler",
    "CandidateObservation",
    "FaceDetection",
    "PerformanceMonitor",
    "PersonDetection",
    "ProcessingStatus",
    "QualityStatus",
    "TrackState",
    "TrackStatus",
    "VideoProcessingPipeline",
    "ai_settings",
    "performance_monitor",
    "video_pipeline",
]
