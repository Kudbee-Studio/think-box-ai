"""Durable execution job queue (PR #198)."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from thinkbox.cloud_execution.errors import CloudExecutionError
from thinkbox.cloud_execution.job import ExecutionJob, ExecutionJobState
from thinkbox.cloud_execution.queue_model import QueueDisposition, QueuedJobRecord
from thinkbox.cloud_execution.retry_policy import RetryPolicy
from thinkbox.cloud_execution.resources import ResourceLimits
from thinkbox.cloud_execution.sqlite_store import DurableExecutionJobStore
from thinkbox.cloud_execution.workspace import WorkspaceBinding

DEFAULT_CLAIM_LEASE_S = 30.0


class ExecutionJobQueue:
    def __init__(
        self,
        store: DurableExecutionJobStore,
        retry_policy: RetryPolicy | None = None,
        claim_lease_s: float = DEFAULT_CLAIM_LEASE_S,
    ) -> None:
        self._store = store
        self._retry = retry_policy or RetryPolicy()
        self._retry.validate()
        self._claim_lease_s = claim_lease_s

    @property
    def store(self) -> DurableExecutionJobStore:
        return self._store

    def enqueue(
        self,
        intent: str,
        limits: ResourceLimits,
        workspace: WorkspaceBinding,
        provider_name: str,
        job_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        max_retries: int | None = None,
    ) -> QueuedJobRecord:
        limits.validate()
        job = ExecutionJob(
            job_id=job_id or "",
            intent=intent,
            provider_name=provider_name,
            metadata=metadata or {},
        )
        return self._store.insert_enqueued(
            job,
            limits,
            workspace,
            max_retries if max_retries is not None else self._retry.max_retries,
        )

    def claim(self, worker_id: str) -> QueuedJobRecord | None:
        self.release_stale_claims()
        queued = self._store.list_by_disposition(QueueDisposition.QUEUED)
        if not queued:
            return None
        candidate = queued[0]
        token = secrets.token_hex(16)
        lease_until = (
            datetime.now(timezone.utc) + timedelta(seconds=self._claim_lease_s)
        ).isoformat()
        if not self._store.try_claim(candidate.job.job_id, worker_id, token, lease_until):
            return None
        return self._store.get_record(candidate.job.job_id)

    def complete(self, job_id: str, claim_token: str) -> None:
        self._verify_claim(job_id, claim_token)
        self._store.update_queue_fields(
            job_id,
            disposition=QueueDisposition.COMPLETED,
            clear_claim=True,
        )

    def fail(self, job_id: str, claim_token: str) -> None:
        self._verify_claim(job_id, claim_token)
        self._store.update_queue_fields(
            job_id,
            disposition=QueueDisposition.FAILED,
            clear_claim=True,
        )

    def cancel(self, job_id: str) -> None:
        record = self._store.get_record(job_id)
        if record is None:
            raise CloudExecutionError(error_type="JobNotFound", context={"job_id": job_id})
        if record.queue_disposition in (
            QueueDisposition.COMPLETED,
            QueueDisposition.CANCELLED,
        ):
            return
        self._store.update_queue_fields(
            job_id,
            disposition=QueueDisposition.CANCELLED,
            state=ExecutionJobState.CANCELLED,
            clear_claim=True,
        )

    def retry(self, job_id: str) -> QueuedJobRecord:
        record = self._store.get_record(job_id)
        if record is None:
            raise CloudExecutionError(error_type="JobNotFound", context={"job_id": job_id})
        if record.job.state == ExecutionJobState.CANCELLED:
            raise CloudExecutionError(
                error_type="RetryDenied",
                context={"reason": "cancelled"},
            )
        if record.job.state == ExecutionJobState.TIMED_OUT:
            raise CloudExecutionError(
                error_type="RetryDenied",
                context={"reason": "timeout"},
            )
        receipt_meta: dict[str, object] = {}
        exit_code: int | None = None
        if record.job.metadata.get("last_exit_code") is not None:
            exit_code = int(record.job.metadata["last_exit_code"])
        if not self._retry.is_retryable(record.job.state, exit_code, receipt_meta):
            raise CloudExecutionError(
                error_type="RetryDenied",
                context={"reason": "non_retryable"},
            )
        next_attempt = record.attempt_count + 1
        if next_attempt > self._retry.max_retries:
            raise CloudExecutionError(
                error_type="RetryDenied",
                context={"reason": "max_retries"},
            )
        self._store.update_queue_fields(
            job_id,
            disposition=QueueDisposition.QUEUED,
            state=ExecutionJobState.QUEUED,
            attempt_count=next_attempt,
            clear_claim=True,
        )
        rec = self._store.get_record(job_id)
        if rec is None:
            raise CloudExecutionError(error_type="JobNotFound", context={"job_id": job_id})
        return rec

    def release_stale_claims(self) -> list[str]:
        now = datetime.now(timezone.utc).isoformat()
        stale = self._store.list_stale_claims(now)
        released: list[str] = []
        for rec in stale:
            self._store.update_queue_fields(
                rec.job.job_id,
                disposition=QueueDisposition.QUEUED,
                clear_claim=True,
            )
            released.append(rec.job.job_id)
        return released

    def renew_claim(self, job_id: str, worker_id: str, claim_token: str) -> bool:
        lease_until = (
            datetime.now(timezone.utc) + timedelta(seconds=self._claim_lease_s)
        ).isoformat()
        return self._store.extend_claim_lease(job_id, worker_id, claim_token, lease_until)

    def validate_claim_for_execution(
        self,
        job_id: str,
        claim_token: str,
        worker_id: str,
    ) -> None:
        """Fail closed if claim expired, missing, or owned by another worker."""
        record = self._store.get_record(job_id)
        if record is None:
            raise CloudExecutionError(error_type="JobNotFound", context={"job_id": job_id})
        if record.queue_disposition != QueueDisposition.CLAIMED:
            raise CloudExecutionError(
                error_type="InvalidClaim",
                context={"reason": "not_claimed"},
            )
        if record.claim_token != claim_token:
            raise CloudExecutionError(
                error_type="InvalidClaim",
                context={"reason": "token_mismatch"},
            )
        if record.claimed_by != worker_id:
            raise CloudExecutionError(
                error_type="InvalidClaim",
                context={"reason": "worker_mismatch"},
            )
        if not record.claim_lease_until:
            raise CloudExecutionError(
                error_type="InvalidClaim",
                context={"reason": "missing_lease"},
            )
        now = datetime.now(timezone.utc)
        try:
            lease_end = datetime.fromisoformat(record.claim_lease_until)
        except ValueError:
            raise CloudExecutionError(
                error_type="InvalidClaim",
                context={"reason": "invalid_lease"},
            ) from None
        if lease_end.tzinfo is None:
            lease_end = lease_end.replace(tzinfo=timezone.utc)
        if lease_end < now:
            raise CloudExecutionError(
                error_type="InvalidClaim",
                context={"reason": "lease_expired"},
            )

    def requeue_claim(self, job_id: str, worker_id: str, claim_token: str) -> None:
        """Release a claim back to QUEUED without marking success (shutdown path)."""
        self.validate_claim_for_execution(job_id, claim_token, worker_id)
        self._store.update_queue_fields(
            job_id,
            disposition=QueueDisposition.QUEUED,
            state=ExecutionJobState.QUEUED,
            clear_claim=True,
        )

    def _verify_claim(self, job_id: str, claim_token: str) -> None:
        record = self._store.get_record(job_id)
        if record is None:
            raise CloudExecutionError(error_type="JobNotFound", context={"job_id": job_id})
        if record.queue_disposition != QueueDisposition.CLAIMED:
            raise CloudExecutionError(
                error_type="InvalidClaim",
                context={"reason": "not_claimed"},
            )
        if record.claim_token != claim_token:
            raise CloudExecutionError(
                error_type="InvalidClaim",
                context={"reason": "token_mismatch"},
            )
