"""Restart recovery for durable queue (PR #198)."""

from __future__ import annotations

import json
from typing import Any

from thinkbox.cloud_execution.job import ExecutionJobState
from thinkbox.cloud_execution.queue import ExecutionJobQueue
from thinkbox.cloud_execution.queue_model import QueueDisposition
from thinkbox.cloud_execution.sqlite_store import DurableExecutionJobStore, _now


def recover_after_restart(
    store: DurableExecutionJobStore,
    queue: ExecutionJobQueue | None = None,
) -> dict[str, Any]:
    """Reconcile persisted jobs after process restart."""
    q = queue or ExecutionJobQueue(store)
    released = q.release_stale_claims()
    blocked: list[str] = []
    for rec in store.list_incomplete_runtime_states():
        job = rec.job
        meta = dict(job.metadata)
        meta["recovery_reason"] = "incomplete_run_after_restart"
        meta["recovered_from_state"] = job.state.value
        store.update_queue_fields(
            job.job_id,
            state=ExecutionJobState.BLOCKED,
            disposition=QueueDisposition.FAILED,
            clear_claim=True,
        )
        with store._lock:
            store._conn.execute(
                "UPDATE cloud_execution_jobs SET metadata_json = ? WHERE job_id = ?",
                (json.dumps({**meta, "session_id": job.session_id}), job.job_id),
            )
            store._conn.commit()
        blocked.append(job.job_id)
    return {
        "released_stale_claims": released,
        "blocked_incomplete_runs": blocked,
        "queued_preserved": [
            r.job.job_id for r in store.list_by_disposition(QueueDisposition.QUEUED)
        ],
    }
