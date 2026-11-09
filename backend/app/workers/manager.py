from __future__ import annotations

import asyncio
from datetime import datetime
import logging
import time
from typing import Any, Callable

logger = logging.getLogger("sentinex.workers")


class WorkerInstance:
    def __init__(self, name: str, display_name: str, queue_capacity: int = 100):
        self.name = name
        self.display_name = display_name
        self.status = "IDLE"  # ONLINE, BUSY, IDLE, OFFLINE, ERROR
        self.current_job: str | None = None
        self.queue_size: int = 0
        self.jobs_processed: int = 0
        self.jobs_failed: int = 0
        self.total_time_ms: float = 0.0
        self.last_heartbeat: datetime = datetime.utcnow()
        self.last_error: str | None = None
        self.is_running: bool = True

    def heartbeat(self) -> None:
        self.last_heartbeat = datetime.utcnow()
        if self.status == "OFFLINE":
            self.status = "IDLE"

    def record_job_start(self, job_name: str) -> None:
        self.current_job = job_name
        self.status = "BUSY"
        self.heartbeat()

    def record_job_finish(self, duration_ms: float, success: bool = True, error: str | None = None) -> None:
        self.current_job = None
        self.total_time_ms += duration_ms
        if success:
            self.jobs_processed += 1
            self.status = "IDLE"
            self.last_error = None
        else:
            self.jobs_failed += 1
            self.status = "ERROR"
            self.last_error = error
        self.heartbeat()

    @property
    def avg_processing_time_ms(self) -> float:
        total = self.jobs_processed + self.jobs_failed
        return round(self.total_time_ms / total, 2) if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_name": self.name,
            "display_name": self.display_name,
            "status": self.status,
            "current_job": self.current_job,
            "queue_size": self.queue_size,
            "jobs_processed": self.jobs_processed,
            "jobs_failed": self.jobs_failed,
            "avg_processing_time_ms": self.avg_processing_time_ms,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "last_error": self.last_error,
        }


class WorkerManager:
    """Centralized management and health registry for all asynchronous workers."""

    def __init__(self):
        self._workers: dict[str, WorkerInstance] = {}
        self._init_standard_workers()

    def _init_standard_workers(self) -> None:
        standard_workers = [
            ("cctv_frame_worker", "CCTV Frame Ingestion & Sampling Worker"),
            ("ai_inference_worker", "YOLO / Person & Face Detection Worker"),
            ("face_quality_worker", "Face Quality & Pose Assessment Worker"),
            ("candidate_matching_worker", "Feature Vector & Candidate Search Worker"),
            ("alert_notification_worker", "Multi-Channel Alert Notification Worker"),
            ("evidence_processing_worker", "Evidence Clipping & SHA-256 Hashing Worker"),
            ("analytics_aggregation_worker", "Analytics Aggregator & Drift Monitor Worker"),
            ("cleanup_retention_worker", "Data Retention & Storage Cleanup Worker"),
        ]
        for name, display in standard_workers:
            self._workers[name] = WorkerInstance(name, display)

    def get_worker(self, name: str) -> WorkerInstance | None:
        return self._workers.get(name)

    def list_workers(self) -> list[dict[str, Any]]:
        # Refresh heartbeats for online status
        now = datetime.utcnow()
        for w in self._workers.values():
            diff = (now - w.last_heartbeat).total_seconds()
            if diff > 300 and w.status not in ("OFFLINE", "ERROR"):
                w.status = "IDLE"
        return [w.to_dict() for w in self._workers.values()]

    def restart_worker(self, name: str) -> dict[str, Any]:
        worker = self._workers.get(name)
        if not worker:
            raise ValueError(f"Worker '{name}' not found.")
        worker.status = "ONLINE"
        worker.current_job = None
        worker.last_error = None
        worker.heartbeat()
        return worker.to_dict()

    async def run_safe_task(
        self,
        worker_name: str,
        job_description: str,
        task_func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """Executes a background job isolated from other workers with automatic failure tracking."""
        worker = self._workers.get(worker_name)
        if not worker:
            worker = WorkerInstance(worker_name, worker_name)
            self._workers[worker_name] = worker

        worker.record_job_start(job_description)
        start_t = time.perf_counter()
        try:
            if asyncio.iscoroutinefunction(task_func):
                result = await task_func(*args, **kwargs)
            else:
                result = task_func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start_t) * 1000.0
            worker.record_job_finish(duration_ms, success=True)
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start_t) * 1000.0
            err_msg = str(e)
            logger.error(f"Worker '{worker_name}' failed job '{job_description}': {err_msg}", exc_info=True)
            worker.record_job_finish(duration_ms, success=False, error=err_msg)
            # Re-raise so caller can handle gracefully, but worker state remains contained
            raise


worker_manager = WorkerManager()
