from __future__ import annotations

import asyncio
from datetime import datetime
import time
from typing import Any, Callable
from urllib.parse import quote, urlsplit, urlunsplit

from app.core.stream_config import stream_config
from app.utils.frame_queue import BoundedFrameQueue, FrameMetadata


def format_authenticated_stream_url(
    stream_url: str,
    username: str | None,
    password: str | None,
) -> Any:
    """
    Safely injects credentials into the stream URL in-memory for OpenCV VideoCapture.
    Supports RTSP/HTTP/HTTPS URLs, integer webcam devices ("0"), and local video paths.
    """
    clean = stream_url.strip()
    if clean.isdigit():
        return int(clean)
    if clean.startswith("file://"):
        return clean[7:]
    if clean.startswith("test:") or clean.startswith("prerecorded:"):
        return clean.split(":", 1)[1]

    if not username:
        return clean

    parsed = urlsplit(clean)
    if not parsed.scheme or not parsed.netloc:
        return clean

    encoded_user = quote(username, safe="")
    encoded_pass = quote(password or "", safe="")

    if encoded_pass:
        auth_netloc = f"{encoded_user}:{encoded_pass}@{parsed.netloc}"
    else:
        auth_netloc = f"{encoded_user}@{parsed.netloc}"

    return urlunsplit((parsed.scheme, auth_netloc, parsed.path, parsed.query, parsed.fragment))


class StreamWorker:
    """
    Independent worker task managing a single camera stream.
    Samples frames at a configurable rate and pushes them with metadata to a bounded queue.
    """

    def __init__(
        self,
        camera_id: int,
        stream_url: str,
        sample_fps: float = 1.0,
        queue_size: int = 8,
        retry_limit: int = 3,
        on_status: Callable[[str, datetime | None, str | None], None] | None = None,
        *,
        camera_code: str = "",
        location_name: str | None = None,
        department_id: int = 0,
        username_reference: str | None = None,
        decrypted_password: str | None = None,
    ) -> None:
        self.camera_id = camera_id
        self.camera_code = camera_code or f"CAM-{camera_id}"
        self.stream_url = stream_url
        self.sample_fps = max(0.1, sample_fps)
        self.queue_size = queue_size
        self.retry_limit = max(0, retry_limit)
        self.on_status = on_status

        self.location_name = location_name
        self.department_id = department_id
        self.username_reference = username_reference
        self.decrypted_password = decrypted_password

        self.queue = BoundedFrameQueue(maxsize=self.queue_size)
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self.sequence: int = 0

    def start(self) -> asyncio.Task:
        """Start the background streaming worker."""
        if self._task is None or self._task.done():
            self._stop_event.clear()
            self._task = asyncio.create_task(
                self.run(), name=f"camera-stream-{self.camera_id}"
            )
        return self._task

    async def stop(self) -> None:
        """Gracefully signal and stop the stream worker."""
        self._stop_event.set()
        if self._task is not None and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=3.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
        self._task = None

    async def run(self) -> None:
        """Main execution loop for capturing and sampling frames."""
        import os
        retries = 0
        connection_url = format_authenticated_stream_url(
            self.stream_url, self.username_reference, self.decrypted_password
        )

        is_file_stream = False
        if isinstance(connection_url, str):
            if os.path.isfile(connection_url) or connection_url.lower().endswith(
                (".mp4", ".avi", ".mkv", ".mov", ".m4v")
            ):
                is_file_stream = True

        effective_location = self.location_name or ""
        if is_file_stream and "[TEST_MODE: PRERECORDED VIDEO]" not in effective_location:
            effective_location = f"{effective_location} [TEST_MODE: PRERECORDED VIDEO]".strip()

        while not self._stop_event.is_set():
            cap = None
            try:
                self._notify("CONNECTING", None, None)
                cv2 = self._load_cv2()

                def _open_capture():
                    if isinstance(connection_url, int):
                        return cv2.VideoCapture(connection_url)
                    return cv2.VideoCapture(connection_url)

                # Open video stream with 5.0s timeout to prevent hanging on unreachable RTSP
                try:
                    cap = await asyncio.wait_for(
                        asyncio.to_thread(_open_capture), timeout=5.0
                    )
                except asyncio.TimeoutError:
                    raise RuntimeError(
                        f"Connection timed out while reaching camera stream: {self.stream_url}"
                    )

                if cap is None or not cap.isOpened():
                    if isinstance(connection_url, int):
                        raise RuntimeError(
                            f"Cannot open webcam (device index {connection_url}). Verify camera permissions or ensure no other application (e.g. browser, Zoom) is occupying the camera device."
                        )
                    raise RuntimeError(
                        f"Unable to connect to camera stream: {self.stream_url}"
                    )

                # Successfully connected - reset retry counter
                retries = 0
                interval = 1.0 / self.sample_fps
                next_sample = 0.0

                while not self._stop_event.is_set():
                    ok, frame = await asyncio.to_thread(cap.read)
                    if not ok or frame is None:
                        if is_file_stream:
                            # Loop prerecorded test video
                            await asyncio.to_thread(cap.set, cv2.CAP_PROP_POS_FRAMES, 0)
                            ok, frame = await asyncio.to_thread(cap.read)
                        if not ok or frame is None:
                            raise RuntimeError("Camera connection lost or stream returned no frames")

                    now = time.monotonic()
                    if now < next_sample:
                        continue
                    next_sample = now + interval

                    self.sequence += 1
                    timestamp = datetime.utcnow()

                    metadata = FrameMetadata(
                        camera_id=self.camera_id,
                        captured_at=timestamp,
                        frame=frame,
                        sequence=self.sequence,
                        camera_code=self.camera_code,
                        location_name=effective_location,
                        department_id=self.department_id,
                    )

                    self.queue.put_nowait(metadata)
                    self._notify("ONLINE", timestamp, None)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                retries += 1
                error_msg = str(exc)
                self._notify("ERROR", None, error_msg)

                if retries > self.retry_limit:
                    self._notify("OFFLINE", None, f"Max retries ({self.retry_limit}) exceeded: {error_msg}")
                    return

                # Controlled retry delay with backoff
                backoff = stream_config.retry_backoff_seconds * retries
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=backoff)
                except asyncio.TimeoutError:
                    pass
            finally:
                if cap is not None:
                    await asyncio.to_thread(cap.release)

        self._notify("OFFLINE", None, None)

    @staticmethod
    def _load_cv2():
        import cv2
        return cv2

    def _notify(self, status: str, seen: datetime | None, error: str | None) -> None:
        if self.on_status:
            try:
                self.on_status(status, seen, error)
            except Exception:
                pass
