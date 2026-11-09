from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class FrameMetadata:
    camera_id: int
    captured_at: datetime
    frame: Any
    sequence: int
    camera_code: str = ""
    location_name: str | None = None
    department_id: int = 0
    frame_reference: str = ""

    def __post_init__(self):
        if not self.frame_reference:
            code = self.camera_code or f"CAM-{self.camera_id}"
            time_str = self.captured_at.strftime("%Y%m%d%H%M%S%f")
            self.frame_reference = f"{code}-{self.sequence:06d}-{time_str}"

    @property
    def timestamp(self) -> datetime:
        return self.captured_at


class BoundedFrameQueue:
    """
    Thread-safe bounded queue designed for live streaming pipelines.
    Drops the oldest frame on overflow to maintain near real-time latency for AI processing.
    """

    def __init__(self, maxsize: int = 8) -> None:
        self.maxsize = max(1, maxsize)
        self._queue: asyncio.Queue[FrameMetadata] = asyncio.Queue(maxsize=self.maxsize)
        self.dropped_frames: int = 0
        self._latest_frame: FrameMetadata | None = None

    def put_nowait(self, item: FrameMetadata) -> None:
        """Add a frame to the queue, dropping the oldest if the buffer is full."""
        if self._queue.full():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                pass
            self.dropped_frames += 1

        self._queue.put_nowait(item)
        self._latest_frame = item

    async def get(self) -> FrameMetadata:
        """Fetch the next available frame in FIFO order."""
        return await self._queue.get()

    def get_nowait(self) -> FrameMetadata | None:
        """Retrieve next frame without awaiting; returns None if empty."""
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def get_latest(self) -> FrameMetadata | None:
        """Read the most recent frame without consuming it from the queue."""
        return self._latest_frame

    def task_done(self) -> None:
        self._queue.task_done()

    def qsize(self) -> int:
        return self._queue.qsize()

    def empty(self) -> bool:
        return self._queue.empty()
