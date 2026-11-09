from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class StreamHealth:
    status: str = "OFFLINE"
    last_seen_at: datetime | None = None
    failures: int = 0
    last_error: str | None = None

    @property
    def connection_status(self) -> str:
        return self.status

    @property
    def current_state(self) -> str:
        return self.status

    @property
    def error_state(self) -> str | None:
        return self.last_error


class StreamHealthService:
    """Tracks in-memory live health status and metrics for all camera streams."""

    def __init__(self) -> None:
        self._health: dict[int, StreamHealth] = {}

    def get(self, camera_id: int) -> StreamHealth:
        return self._health.setdefault(camera_id, StreamHealth())

    def record_connecting(self, camera_id: int) -> StreamHealth:
        h = self.get(camera_id)
        h.status = "CONNECTING"
        h.last_error = None
        return h

    def record_frame(self, camera_id: int, timestamp: datetime | None = None) -> StreamHealth:
        h = self.get(camera_id)
        h.status = "ONLINE"
        h.last_seen_at = timestamp or datetime.utcnow()
        h.failures = 0
        h.last_error = None
        return h

    record_online = record_frame

    def record_failure(self, camera_id: int, error: str) -> StreamHealth:
        h = self.get(camera_id)
        h.status = "ERROR"
        h.failures += 1
        h.last_error = str(error)[:500]
        return h

    def record_offline(self, camera_id: int, reason: str | None = None) -> StreamHealth:
        h = self.get(camera_id)
        h.status = "OFFLINE"
        if reason:
            h.last_error = str(reason)[:500]
        return h

    def get_summary(self, registered_camera_ids: list[int] | None = None) -> dict:
        counts = {"ONLINE": 0, "CONNECTING": 0, "ERROR": 0, "OFFLINE": 0}
        target_ids = registered_camera_ids if registered_camera_ids is not None else list(self._health.keys())

        for cid in target_ids:
            st = self.get(cid).status
            counts[st] = counts.get(st, 0) + 1

        return {
            "total": len(target_ids),
            "online": counts.get("ONLINE", 0),
            "connecting": counts.get("CONNECTING", 0),
            "error": counts.get("ERROR", 0),
            "offline": counts.get("OFFLINE", 0),
            "by_status": counts,
        }
