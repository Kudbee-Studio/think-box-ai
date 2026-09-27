"""Durable SQLite execution job store (PR #198)."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from thinkbox.cloud_execution.errors import CloudExecutionError
from thinkbox.cloud_execution.job import ExecutionJob, ExecutionJobState, TERMINAL_STATES
from thinkbox.cloud_execution.queue_model import QueueDisposition, QueuedJobRecord
from thinkbox.cloud_execution.resources import ResourceLimits
from thinkbox.cloud_execution.workspace import WorkspaceBinding

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cloud_execution_jobs (
    job_id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    intent TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    state TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    workspace_json TEXT NOT NULL,
    limits_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    queue_disposition TEXT NOT NULL,
    queue_position INTEGER NOT NULL,
    attempt_count INTEGER NOT NULL,
    max_retries INTEGER NOT NULL,
    claimed_by TEXT,
    claim_token TEXT,
    claim_lease_until TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_receipt_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_cej_queue
    ON cloud_execution_jobs(queue_disposition, queue_position);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_from_row(row: sqlite3.Row) -> ExecutionJob:
    meta = json.loads(row["metadata_json"])
    job = ExecutionJob(
        job_id=row["job_id"],
        execution_id=row["execution_id"],
        intent=row["intent"],
        provider_name=row["provider_name"],
        state=ExecutionJobState(row["state"]),
        workspace_id=row["workspace_id"],
        session_id=meta.get("session_id"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        metadata={k: v for k, v in meta.items() if k != "session_id"},
    )
    return job


def _record_from_row(row: sqlite3.Row) -> QueuedJobRecord:
    ws_data = json.loads(row["workspace_json"])
    lim_data = json.loads(row["limits_json"])
    return QueuedJobRecord(
        job=_job_from_row(row),
        limits=ResourceLimits(
            cpu_cores=float(lim_data["cpu_cores"]),
            memory_mb=int(lim_data["memory_mb"]),
            wall_clock_timeout_s=float(lim_data["wall_clock_timeout_s"]),
            max_concurrency=int(lim_data["max_concurrency"]),
        ),
        workspace=WorkspaceBinding(
            workspace_id=ws_data["workspace_id"],
            worktree_path=ws_data["worktree_path"],
            git_branch=ws_data.get("git_branch", ""),
            metadata=ws_data.get("metadata") or {},
        ),
        queue_disposition=QueueDisposition(row["queue_disposition"]),
        queue_position=int(row["queue_position"]),
        attempt_count=int(row["attempt_count"]),
        max_retries=int(row["max_retries"]),
        claimed_by=row["claimed_by"],
        claim_token=row["claim_token"],
        claim_lease_until=row["claim_lease_until"],
    )


class DurableExecutionJobStore:
    """SQLite-backed job + queue persistence."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    @property
    def db_path(self) -> Path:
        return self._path

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def put(self, job: ExecutionJob) -> None:
        with self._lock:
            row = self._conn.execute(
                "SELECT job_id FROM cloud_execution_jobs WHERE job_id = ?",
                (job.job_id,),
            ).fetchone()
            if row is None:
                raise CloudExecutionError(
                    error_type="JobNotEnqueued",
                    context={"job_id": job.job_id},
                )
            self._conn.execute(
                """
                UPDATE cloud_execution_jobs
                SET state = ?, updated_at = ?, metadata_json = ?
                WHERE job_id = ?
                """,
                (
                    job.state.value,
                    _now(),
                    json.dumps({**job.metadata, "session_id": job.session_id}),
                    job.job_id,
                ),
            )
            self._conn.commit()

    def get(self, job_id: str) -> ExecutionJob | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM cloud_execution_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return _job_from_row(row)

    def get_record(self, job_id: str) -> QueuedJobRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM cloud_execution_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return _record_from_row(row)

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM cloud_execution_jobs ORDER BY queue_position ASC",
            ).fetchall()
        return [_record_from_row(r).snapshot() for r in rows]

    def _next_queue_position(self) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(queue_position), 0) + 1 AS n FROM cloud_execution_jobs",
        ).fetchone()
        return int(row["n"])

    def insert_enqueued(
        self,
        job: ExecutionJob,
        limits: ResourceLimits,
        workspace: WorkspaceBinding,
        max_retries: int,
    ) -> QueuedJobRecord:
        with self._lock:
            existing = self._conn.execute(
                "SELECT job_id FROM cloud_execution_jobs WHERE job_id = ?",
                (job.job_id,),
            ).fetchone()
            if existing is not None:
                raise CloudExecutionError(
                    error_type="DuplicateJobId",
                    context={"job_id": job.job_id},
                )
            active = self._conn.execute(
                """
                SELECT job_id FROM cloud_execution_jobs
                WHERE workspace_id = ?
                  AND state NOT IN (?, ?, ?, ?, ?)
                  AND queue_disposition IN (?, ?)
                """,
                (
                    workspace.workspace_id,
                    ExecutionJobState.SUCCEEDED.value,
                    ExecutionJobState.FAILED.value,
                    ExecutionJobState.CANCELLED.value,
                    ExecutionJobState.TIMED_OUT.value,
                    ExecutionJobState.BLOCKED.value,
                    QueueDisposition.QUEUED.value,
                    QueueDisposition.CLAIMED.value,
                ),
            ).fetchone()
            if active is not None:
                raise CloudExecutionError(
                    error_type="DuplicateActiveWorkspace",
                    context={
                        "workspace_id": workspace.workspace_id,
                        "existing_job_id": active["job_id"],
                    },
                )
            pos = self._next_queue_position()
            now = _now()
            job.state = ExecutionJobState.QUEUED
            job.workspace_id = workspace.workspace_id
            job.updated_at = now
            self._conn.execute(
                """
                INSERT INTO cloud_execution_jobs (
                    job_id, execution_id, intent, provider_name, state,
                    workspace_id, workspace_json, limits_json, metadata_json,
                    queue_disposition, queue_position, attempt_count, max_retries,
                    claimed_by, claim_token, claim_lease_until,
                    created_at, updated_at, last_receipt_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, NULL)
                """,
                (
                    job.job_id,
                    job.execution_id,
                    job.intent,
                    job.provider_name,
                    job.state.value,
                    workspace.workspace_id,
                    json.dumps(workspace.snapshot()),
                    json.dumps(limits.snapshot()),
                    json.dumps({**job.metadata, "session_id": job.session_id}),
                    QueueDisposition.QUEUED.value,
                    pos,
                    0,
                    max_retries,
                    job.created_at or now,
                    now,
                ),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM cloud_execution_jobs WHERE job_id = ?",
                (job.job_id,),
            ).fetchone()
            return _record_from_row(row)

    def save_receipt(self, job_id: str, receipt_json: str, disposition: QueueDisposition) -> None:
        with self._lock:
            self._conn.execute(
                """
                UPDATE cloud_execution_jobs
                SET last_receipt_json = ?, queue_disposition = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (receipt_json, disposition.value, _now(), job_id),
            )
            self._conn.commit()

    def update_queue_fields(
        self,
        job_id: str,
        *,
        disposition: QueueDisposition | None = None,
        claimed_by: str | None = None,
        claim_token: str | None = None,
        claim_lease_until: str | None = None,
        clear_claim: bool = False,
        attempt_count: int | None = None,
        state: ExecutionJobState | None = None,
    ) -> None:
        with self._lock:
            sets: list[str] = ["updated_at = ?"]
            params: list[Any] = [_now()]
            if disposition is not None:
                sets.append("queue_disposition = ?")
                params.append(disposition.value)
            if state is not None:
                sets.append("state = ?")
                params.append(state.value)
            if attempt_count is not None:
                sets.append("attempt_count = ?")
                params.append(attempt_count)
            if clear_claim:
                sets.extend(
                    ["claimed_by = NULL", "claim_token = NULL", "claim_lease_until = NULL"],
                )
            else:
                if claimed_by is not None:
                    sets.append("claimed_by = ?")
                    params.append(claimed_by)
                if claim_token is not None:
                    sets.append("claim_token = ?")
                    params.append(claim_token)
                if claim_lease_until is not None:
                    sets.append("claim_lease_until = ?")
                    params.append(claim_lease_until)
            params.append(job_id)
            sql = f"UPDATE cloud_execution_jobs SET {', '.join(sets)} WHERE job_id = ?"
            self._conn.execute(sql, params)
            self._conn.commit()

    def list_by_disposition(self, disposition: QueueDisposition) -> list[QueuedJobRecord]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM cloud_execution_jobs
                WHERE queue_disposition = ?
                ORDER BY queue_position ASC
                """,
                (disposition.value,),
            ).fetchall()
        return [_record_from_row(r) for r in rows]

    def list_incomplete_runtime_states(self) -> list[QueuedJobRecord]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM cloud_execution_jobs
                WHERE state IN (?, ?, ?)
                """,
                (
                    ExecutionJobState.ADMITTED.value,
                    ExecutionJobState.STARTING.value,
                    ExecutionJobState.RUNNING.value,
                ),
            ).fetchall()
        return [_record_from_row(r) for r in rows]

    def try_claim(
        self,
        job_id: str,
        worker_id: str,
        claim_token: str,
        claim_lease_until: str,
    ) -> bool:
        with self._lock:
            cur = self._conn.execute(
                """
                UPDATE cloud_execution_jobs
                SET queue_disposition = ?, claimed_by = ?, claim_token = ?,
                    claim_lease_until = ?, updated_at = ?
                WHERE job_id = ? AND queue_disposition = ?
                """,
                (
                    QueueDisposition.CLAIMED.value,
                    worker_id,
                    claim_token,
                    claim_lease_until,
                    _now(),
                    job_id,
                    QueueDisposition.QUEUED.value,
                ),
            )
            self._conn.commit()
            return cur.rowcount == 1

    def list_stale_claims(self, now_iso: str) -> list[QueuedJobRecord]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM cloud_execution_jobs
                WHERE queue_disposition = ?
                  AND claim_lease_until IS NOT NULL
                  AND claim_lease_until < ?
                """,
                (QueueDisposition.CLAIMED.value, now_iso),
            ).fetchall()
        return [_record_from_row(r) for r in rows]

    def extend_claim_lease(
        self,
        job_id: str,
        worker_id: str,
        claim_token: str,
        claim_lease_until: str,
    ) -> bool:
        """Renew lease only when worker and token still match (claim fencing)."""
        with self._lock:
            cur = self._conn.execute(
                """
                UPDATE cloud_execution_jobs
                SET claim_lease_until = ?, updated_at = ?
                WHERE job_id = ?
                  AND queue_disposition = ?
                  AND claimed_by = ?
                  AND claim_token = ?
                  AND claim_lease_until IS NOT NULL
                  AND claim_lease_until >= ?
                """,
                (
                    claim_lease_until,
                    _now(),
                    job_id,
                    QueueDisposition.CLAIMED.value,
                    worker_id,
                    claim_token,
                    _now(),
                ),
            )
            self._conn.commit()
            return cur.rowcount == 1
