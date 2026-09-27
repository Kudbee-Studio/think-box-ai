"""In-memory execution job store (PR #197)."""

from __future__ import annotations

import threading
from typing import Any

from thinkbox.cloud_execution.job import ExecutionJob


class ExecutionJobStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, ExecutionJob] = {}

    def put(self, job: ExecutionJob) -> None:
        with self._lock:
            self._jobs[job.job_id] = job

    def get(self, job_id: str) -> ExecutionJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            return [j.snapshot() for j in self._jobs.values()]
