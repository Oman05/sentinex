"""
Module 5 – Performance Monitor
================================
Thread-safe per-camera processing metrics.

Metrics collected
-----------------
- frames_received         Total frames pulled from the frame queue
- frames_processed        Frames that passed validation and completed detection
- frames_dropped          Frames rejected during validation
- frames_errored          Frames that failed due to model/runtime error
- total_processing_time   Cumulative wall-clock time spent in detection (seconds)
- active_tracks           Number of tracks currently alive (snapshot)
- candidates_emitted      Total candidate observations emitted

Derived (computed on read)
--------------------------
- average_latency_ms      Mean processing time per successfully processed frame
- fps_processed           Processed frames per second (rolling or cumulative)

These metrics feed the research evaluation module (Module 8) and the
operational dashboard without exposing any raw biometric data.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict


# ---------------------------------------------------------------------------
# Per-camera metrics snapshot (immutable, returned to callers)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CameraMetricsSnapshot:
    """Immutable point-in-time snapshot of metrics for a single camera."""

    camera_id: int
    frames_received: int
    frames_processed: int
    frames_dropped: int
    frames_errored: int
    active_tracks: int
    candidates_emitted: int
    total_processing_time_s: float
    average_latency_ms: float
    fps_processed: float
    started_at: datetime
    snapshot_at: datetime


# ---------------------------------------------------------------------------
# Mutable per-camera counter state (internal)
# ---------------------------------------------------------------------------


@dataclass
class _CameraCounters:
    camera_id: int
    frames_received: int = 0
    frames_processed: int = 0
    frames_dropped: int = 0
    frames_errored: int = 0
    active_tracks: int = 0
    candidates_emitted: int = 0
    total_processing_time_s: float = 0.0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def average_latency_ms(self) -> float:
        if self.frames_processed == 0:
            return 0.0
        return (self.total_processing_time_s / self.frames_processed) * 1000

    def fps_processed(self) -> float:
        elapsed = (datetime.now(timezone.utc) - self.started_at).total_seconds()
        if elapsed <= 0 or self.frames_processed == 0:
            return 0.0
        return self.frames_processed / elapsed

    def snapshot(self) -> CameraMetricsSnapshot:
        now = datetime.now(timezone.utc)
        return CameraMetricsSnapshot(
            camera_id=self.camera_id,
            frames_received=self.frames_received,
            frames_processed=self.frames_processed,
            frames_dropped=self.frames_dropped,
            frames_errored=self.frames_errored,
            active_tracks=self.active_tracks,
            candidates_emitted=self.candidates_emitted,
            total_processing_time_s=round(self.total_processing_time_s, 4),
            average_latency_ms=round(self.average_latency_ms(), 2),
            fps_processed=round(self.fps_processed(), 3),
            started_at=self.started_at,
            snapshot_at=now,
        )


# ---------------------------------------------------------------------------
# Global Performance Monitor
# ---------------------------------------------------------------------------


class PerformanceMonitor:
    """
    Thread-safe registry of per-camera processing metrics.

    One singleton instance is used throughout the AI engine.

    Usage
    -----
    >>> monitor = PerformanceMonitor()
    >>> monitor.record_frame_received(camera_id=1)
    >>> monitor.record_frame_processed(camera_id=1, latency_s=0.035)
    >>> snapshot = monitor.snapshot(camera_id=1)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cameras: Dict[int, _CameraCounters] = {}

    # -------------------------------------------------------------------------
    # Recording methods (called from the pipeline)
    # -------------------------------------------------------------------------

    def record_frame_received(self, camera_id: int) -> None:
        self._get(camera_id).frames_received += 1

    def record_frame_processed(self, camera_id: int, latency_s: float) -> None:
        c = self._get(camera_id)
        c.frames_processed += 1
        c.total_processing_time_s += latency_s

    def record_frame_dropped(self, camera_id: int) -> None:
        self._get(camera_id).frames_dropped += 1

    def record_frame_error(self, camera_id: int) -> None:
        self._get(camera_id).frames_errored += 1

    def update_active_tracks(self, camera_id: int, count: int) -> None:
        self._get(camera_id).active_tracks = count

    def record_candidate_emitted(self, camera_id: int, count: int = 1) -> None:
        self._get(camera_id).candidates_emitted += count

    def reset_camera(self, camera_id: int) -> None:
        """Reset counters for a camera (e.g. when its stream restarts)."""
        with self._lock:
            self._cameras[camera_id] = _CameraCounters(camera_id=camera_id)

    def remove_camera(self, camera_id: int) -> None:
        """Remove all metric state for a camera."""
        with self._lock:
            self._cameras.pop(camera_id, None)

    # -------------------------------------------------------------------------
    # Read methods
    # -------------------------------------------------------------------------

    def snapshot(self, camera_id: int) -> CameraMetricsSnapshot:
        """Return an immutable metrics snapshot for one camera."""
        with self._lock:
            return self._get(camera_id).snapshot()

    def all_snapshots(self) -> list[CameraMetricsSnapshot]:
        """Return snapshots for every tracked camera."""
        with self._lock:
            return [c.snapshot() for c in self._cameras.values()]

    def active_camera_ids(self) -> list[int]:
        with self._lock:
            return list(self._cameras.keys())

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _get(self, camera_id: int) -> _CameraCounters:
        """Get or create counters for the specified camera (not lock-protected internally)."""
        if camera_id not in self._cameras:
            with self._lock:
                if camera_id not in self._cameras:
                    self._cameras[camera_id] = _CameraCounters(camera_id=camera_id)
        return self._cameras[camera_id]


# Module-level singleton
performance_monitor = PerformanceMonitor()
