"""Queue inspection API (PR #198)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from thinkbox.cloud_execution.job import ExecutionJobState
from thinkbox.cloud_execution.queue import ExecutionJobQueue
from thinkbox.cloud_execution.queue_model import QueueDisposition
from thinkbox.cloud_execution.sqlite_store import DurableExecutionJobStore


def inspect_queue(store: DurableExecutionJobStore, queue: ExecutionJobQueue) -> dict[str, Any]:
    queue.release_stale_claims()
    now = datetime.now(timezone.utc).isoformat()
    return {
        "queued": [r.snapshot() for r in store.list_by_disposition(QueueDisposition.QUEUED)],
        "claimed": [r.snapshot() for r in store.list_by_disposition(QueueDisposition.CLAIMED)],
        "stale_claims": [r.snapshot() for r in store.list_stale_claims(now)],
        "completed": [r.snapshot() for r in store.list_by_disposition(QueueDisposition.COMPLETED)],
        "failed": [r.snapshot() for r in store.list_by_disposition(QueueDisposition.FAILED)],
        "cancelled": [r.snapshot() for r in store.list_by_disposition(QueueDisposition.CANCELLED)],
        "blocked_jobs": [
            s
            for s in store.list_jobs()
            if s["job"]["state"] == ExecutionJobState.BLOCKED.value
        ],
        "live_api_called": False,
    }
