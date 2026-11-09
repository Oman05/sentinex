"""
Module 5 – Abstract Tracker Interface
=======================================
Defines the protocol every short-term person tracker must implement.

Design principle: the pipeline calls ``BaseTracker`` methods exclusively.
Swapping to a different tracking algorithm (e.g. ByteTrack, DeepSORT, SORT)
requires only a new concrete implementation of this class — the rest of the
pipeline is unaffected.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.ai_engine.schemas.observations import FaceDetection, PersonDetection, TrackState


class BaseTracker(ABC):
    """
    Abstract base for short-term person trackers.

    A tracker is responsible for:
    1. Associating new detections with existing tracks (using any suitable
       algorithm — IoU, feature similarity, Kalman prediction, etc.).
    2. Creating new tracks for unmatched detections.
    3. Ageing and purging stale tracks.

    The tracker maintains per-camera state internally; a single instance
    manages all tracks for one camera.
    """

    @abstractmethod
    def update(
        self,
        detections: list[PersonDetection],
        face_detections: list[FaceDetection],
        timestamp: datetime,
        frame_index: int,
    ) -> list[TrackState]:
        """
        Ingest a new set of detections and return the updated track list.

        Parameters
        ----------
        detections:
            Person detections from the current frame.
        face_detections:
            Face detections linked to the persons above.
        timestamp:
            UTC capture timestamp of the current frame.
        frame_index:
            Monotonically increasing frame counter (used for age tracking).

        Returns
        -------
        The full list of currently active ``TrackState`` objects after the
        update. This includes tracks that were matched in the current frame
        AND tracks that are still within their maximum age window.
        """
        ...

    @abstractmethod
    def get_active_tracks(self) -> list[TrackState]:
        """Return all tracks that are currently in ACTIVE or LOST state."""
        ...

    @abstractmethod
    def reset(self) -> None:
        """
        Discard all track state. Used when a camera stream is restarted or
        during testing teardown.
        """
        ...

    @property
    @abstractmethod
    def track_count(self) -> int:
        """Total number of tracks created since last reset."""
        ...
