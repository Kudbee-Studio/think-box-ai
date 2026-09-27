"""Governed cloud execution worker loop (PR #199)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from thinkbox.cloud_execution.durable_engine import DurableCloudExecutionEngine
from thinkbox.cloud_execution.errors import AdmissionDeniedError, CloudExecutionError
from thinkbox.cloud_execution.heartbeat import WorkerHeartbeat
from thinkbox.cloud_execution.job import ExecutionJobState
from thinkbox.cloud_execution.queue_model import QueueDisposition, QueuedJobRecord
from thinkbox.cloud_execution.worker_config import WorkerConfig
from thinkbox.cloud_execution.worker_lifecycle import WorkerState, worker_transition
from thinkbox.cloud_execution.worker_runtime_store import WorkerRuntimeStore


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class _ActiveClaim:
    record: QueuedJobRecord
    claim_token: str


@dataclass
class WorkerStats:
    claims_total: int = 0
    jobs_succeeded: int = 0
    jobs_failed: int = 0
    jobs_retried: int = 0
    claim_renewals: int = 0


class CloudExecutionWorker:
    """Process-local worker loop over the durable SQLite queue."""

    def __init__(
        self,
        engine: DurableCloudExecutionEngine,
        config: WorkerConfig,
        runtime_store: WorkerRuntimeStore | None = None,
        persist_runtime: bool = True,
    ) -> None:
        config.validate()
        self._engine = engine
        self._config = config
        self._state = WorkerState.STARTING
        self._stats = WorkerStats()
        self._active: dict[str, _ActiveClaim] = {}
        self._stop_reason: str | None = None
        self._fail_reason: str | None = None
        self._heartbeat = WorkerHeartbeat(
            worker_id=config.worker_id,
            last_beat_at="",
            interval_s=config.heartbeat_interval_s,
            timeout_s=config.heartbeat_timeout_s,
        )
        self._persist = persist_runtime
        self._runtime_store = runtime_store
        if self._persist and self._runtime_store is None:
            self._runtime_store = WorkerRuntimeStore(engine.db_path)

    @property
    def state(self) -> WorkerState:
        return self._state

    @property
    def config(self) -> WorkerConfig:
        return self._config

    @property
    def heartbeat(self) -> WorkerHeartbeat:
        return self._heartbeat

    @property
    def active_job_ids(self) -> list[str]:
        return list(self._active.keys())

    def start(self) -> None:
        if self._state != WorkerState.STARTING:
            raise CloudExecutionError(
                error_type="InvalidWorkerLifecycle",
                context={"reason": "start_called_twice"},
            )
        self._state = worker_transition(self._state, WorkerState.IDLE)
        self.beat()
        self._persist_snapshot()

    def request_shutdown(self, reason: str = "operator_shutdown") -> None:
        if self._state in (WorkerState.STOPPED, WorkerState.FAILED):
            return
        self._stop_reason = reason
        if self._state == WorkerState.STARTING:
            self._state = WorkerState.DRAINING
        else:
            self._state = worker_transition(self._state, WorkerState.DRAINING)
        self._persist_snapshot()

    def beat(self) -> None:
        self._heartbeat.last_beat_at = _now_iso()
        self._persist_snapshot()

    def renew_active_claims(self) -> int:
        renewed = 0
        for job_id, active in list(self._active.items()):
            if self._engine.queue.renew_claim(
                job_id,
                self._config.worker_id,
                active.claim_token,
            ):
                renewed += 1
                self._stats.claim_renewals += 1
        return renewed

    def poll_once(self) -> bool:
        """Claim and execute at most one job when capacity allows."""
        self._finalize_draining_if_idle()
        if self._state in (WorkerState.STOPPED, WorkerState.FAILED):
            return False
        if self._state == WorkerState.DRAINING:
            return False
        if len(self._active) >= self._config.max_active_jobs:
            return False

        self._state = worker_transition(self._state, WorkerState.CLAIMING)
        claimed = self._engine.queue.claim(self._config.worker_id)
        if claimed is None:
            self._state = worker_transition(self._state, WorkerState.IDLE)
            return False

        token = claimed.claim_token or ""
        self._stats.claims_total += 1
        self._active[claimed.job.job_id] = _ActiveClaim(claimed, token)
        self._state = worker_transition(self._state, WorkerState.EXECUTING)
        self.beat()
        self.renew_active_claims()

        try:
            self._engine.queue.validate_claim_for_execution(
                claimed.job.job_id,
                token,
                self._config.worker_id,
            )
            receipt = self._engine.run_claimed(
                claimed,
                token,
                worker_id=self._config.worker_id,
            )
            job = self._engine.durable_store.get(claimed.job.job_id)
            if job and job.state == ExecutionJobState.SUCCEEDED:
                self._stats.jobs_succeeded += 1
            elif job and job.state in (
                ExecutionJobState.FAILED,
                ExecutionJobState.TIMED_OUT,
                ExecutionJobState.BLOCKED,
            ):
                self._stats.jobs_failed += 1
                self._maybe_retry(claimed.job.job_id, job.state)
            elif job and job.state == ExecutionJobState.CANCELLED:
                pass
            self._active.pop(claimed.job.job_id, None)
            self._state = worker_transition(self._state, WorkerState.IDLE)
            self._persist_snapshot()
            return receipt is not None
        except AdmissionDeniedError:
            self._stats.jobs_failed += 1
            self._active.pop(claimed.job.job_id, None)
            self._state = worker_transition(self._state, WorkerState.IDLE)
            self._persist_snapshot()
            return True
        except CloudExecutionError as exc:
            if exc.error_type == "InvalidClaim":
                self._active.pop(claimed.job.job_id, None)
                self._state = worker_transition(self._state, WorkerState.IDLE)
                self._persist_snapshot()
                return False
            self._stats.jobs_failed += 1
            self._active.pop(claimed.job.job_id, None)
            self._state = worker_transition(self._state, WorkerState.IDLE)
            self._persist_snapshot()
            raise
        except Exception as exc:
            self._fail_reason = str(exc)
            self._state = worker_transition(self._state, WorkerState.FAILED)
            self._release_active_claims_on_failure()
            self._persist_snapshot()
            raise

    def run_until_idle(self, max_iterations: int = 100) -> int:
        """Deterministic drain for tests — returns jobs processed."""
        processed = 0
        for _ in range(max_iterations):
            if self._state == WorkerState.DRAINING and not self._active:
                break
            if self.poll_once():
                processed += 1
                continue
            if self._state == WorkerState.IDLE:
                queued = self._engine.queue.store.list_by_disposition(QueueDisposition.QUEUED)
                if not queued:
                    break
        self._finalize_draining_if_idle()
        return processed

    def settle_shutdown(self) -> None:
        """Re-queue active claims without marking success (graceful interrupt)."""
        for job_id, active in list(self._active.items()):
            try:
                self._engine.queue.requeue_claim(
                    job_id,
                    self._config.worker_id,
                    active.claim_token,
                )
            except CloudExecutionError:
                pass
            self._active.pop(job_id, None)
        if self._state == WorkerState.DRAINING:
            self._state = worker_transition(self._state, WorkerState.STOPPED)
        self._persist_snapshot()

    def inspection_snapshot(self) -> dict[str, Any]:
        hb = self._heartbeat.snapshot()
        return {
            "worker_id": self._config.worker_id,
            "state": self._state.value,
            "capacity": self._config.max_active_jobs,
            "active_job_ids": self.active_job_ids,
            "active_count": len(self._active),
            "last_heartbeat": hb,
            "claim_count": self._stats.claims_total,
            "successful_jobs": self._stats.jobs_succeeded,
            "failed_jobs": self._stats.jobs_failed,
            "retried_jobs": self._stats.jobs_retried,
            "claim_renewals": self._stats.claim_renewals,
            "stopped_reason": self._stop_reason,
            "failed_reason": self._fail_reason,
            "recovery_summary": self._engine.recovery_summary,
            "live_api_called": False,
            "updated_at": _now_iso(),
        }

    def _maybe_retry(self, job_id: str, terminal_state: ExecutionJobState) -> None:
        queue = self._engine.queue
        try:
            queue.retry(job_id)
            self._stats.jobs_retried += 1
        except CloudExecutionError:
            return

    def _finalize_draining_if_idle(self) -> None:
        if self._state == WorkerState.DRAINING and not self._active:
            self._state = worker_transition(self._state, WorkerState.STOPPED)
            self._persist_snapshot()

    def _release_active_claims_on_failure(self) -> None:
        for job_id, active in list(self._active.items()):
            try:
                self._engine.queue.requeue_claim(
                    job_id,
                    self._config.worker_id,
                    active.claim_token,
                )
            except CloudExecutionError:
                pass
            self._active.pop(job_id, None)

    def _persist_snapshot(self) -> None:
        if not self._persist or self._runtime_store is None:
            return
        snap = self.inspection_snapshot()
        self._runtime_store.save_snapshot(
            self._config.worker_id,
            self._state,
            snap,
        )
