"""
Module 5 – AI Engine Configuration
====================================
All processing thresholds, model paths, hardware device selection,
and feature flags are driven by environment variables so they can be
changed without touching source code.

Environment variables (with defaults):

  PERSON_DETECTION_THRESHOLD   0.45   Minimum confidence to accept a person detection
  FACE_DETECTION_THRESHOLD     0.70   Minimum confidence to accept a face detection
  MAX_TRACK_AGE                30     Frames a track may go unmatched before it is purged
  MAX_QUEUE_SIZE               8      Inherited limit (mirrors Module 4 BoundedFrameQueue)
  PERSON_MODEL_PATH            ""     Path to custom YOLO weights; empty = auto-download
  FACE_MODEL_PATH              ""     Path to custom face model weights; empty = auto-download
  DEVICE                       auto   "auto" | "cpu" | "cuda" | "cuda:0" etc.
  PROCESSING_EVENTS_ENABLED    True   Write rows to processing_events table
  MIN_PERSON_BBOX_AREA         1024   Minimum bounding-box pixel area to consider a detection
  MIN_FRAME_WIDTH              64     Reject frames narrower than this
  MIN_FRAME_HEIGHT             64     Reject frames shorter than this
  CANDIDATE_EMIT_INTERVAL      5      Emit a new candidate for a track every N frames at most
  PIPELINE_WORKERS             1      Number of parallel pipeline coroutines (per camera)
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class AIEngineSettings(BaseSettings):
    """AI Video Processing module configuration."""

    # -------------------------------------------------------------------------
    # Detection thresholds
    # -------------------------------------------------------------------------
    PERSON_DETECTION_THRESHOLD: float = 0.45
    """Minimum model confidence required to emit a PersonDetection."""

    FACE_DETECTION_THRESHOLD: float = 0.70
    """Minimum face-detector confidence required to emit a FaceDetection."""

    # -------------------------------------------------------------------------
    # Tracking
    # -------------------------------------------------------------------------
    MAX_TRACK_AGE: int = 30
    """Maximum number of consecutive unmatched frames before a track is removed."""

    IOU_ASSIGNMENT_THRESHOLD: float = 0.30
    """Minimum IoU overlap to associate a new detection with an existing track."""

    # -------------------------------------------------------------------------
    # Frame filtering
    # -------------------------------------------------------------------------
    MIN_FRAME_WIDTH: int = 64
    """Frames narrower than this are rejected during validation."""

    MIN_FRAME_HEIGHT: int = 64
    """Frames shorter than this are rejected during validation."""

    MIN_PERSON_BBOX_AREA: int = 1024
    """Minimum bounding-box pixel area (w*h) for a detection to be retained."""

    # -------------------------------------------------------------------------
    # Candidate emission
    # -------------------------------------------------------------------------
    CANDIDATE_EMIT_INTERVAL: int = 5
    """
    How many frames must pass between successive candidate emissions for the
    same track. Prevents flooding downstream modules with near-duplicate
    observations of the same person.
    """

    # -------------------------------------------------------------------------
    # Model paths (empty = use auto-download / bundled defaults)
    # -------------------------------------------------------------------------
    PERSON_MODEL_PATH: str = ""
    """
    Absolute path to custom YOLOv8 weights (.pt file).
    Leave empty to use the default yolov8n.pt (downloaded on first run).
    """

    FACE_MODEL_PATH: str = ""
    """
    Absolute path to custom face-detection model weights.
    Leave empty to use the bundled MTCNN defaults from facenet-pytorch.
    """

    # -------------------------------------------------------------------------
    # Hardware
    # -------------------------------------------------------------------------
    DEVICE: str = "auto"
    """
    Compute device for AI inference.
    "auto" selects CUDA if available, otherwise CPU.
    Explicit values: "cpu", "cuda", "cuda:0", "cuda:1", etc.
    """

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------
    PROCESSING_EVENTS_ENABLED: bool = True
    """Write a row to the processing_events table for every processed frame."""

    # -------------------------------------------------------------------------
    # Pipeline concurrency
    # -------------------------------------------------------------------------
    PIPELINE_WORKERS: int = 1
    """Number of async worker coroutines to spawn per active camera."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    def resolve_device(self) -> str:
        """
        Return the concrete torch device string.
        When DEVICE is "auto", detect CUDA availability at runtime.
        """
        if self.DEVICE.lower() == "auto":
            try:
                import torch  # noqa: PLC0415
                return "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                return "cpu"
        return self.DEVICE


# Module-level singleton – import this everywhere inside ai_engine
ai_settings = AIEngineSettings()
