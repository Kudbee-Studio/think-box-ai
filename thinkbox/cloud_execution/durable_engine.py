"""Durable queue + cloud execution engine integration (PR #198)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from thinkbox.cloud_execution.admission import ExecutionAdmissionGate
from thinkbox.cloud_execution.admission_token import AdmissionTokenHook, noop_admission_token_hook
from thinkbox.cloud_execution.engine import CloudExecutionEngine
from thinkbox.cloud_execution.errors import AdmissionDeniedError
from thinkbox.cloud_execution.job import ExecutionJob, ExecutionJobState
from thinkbox.cloud_execution.provider import CloudExecutionProvider
from thinkbox.cloud_execution.queue import ExecutionJobQueue
from thinkbox.cloud_execution.queue_model import QueueDisposition, QueuedJobRecord
from thinkbox.cloud_execution.recovery import recover_after_restart
from thinkbox.cloud_execution.receipt import ExecutionAttemptReceipt
from thinkbox.cloud_execution.resources import ResourceLimits
from thinkbox.cloud_execution.sqlite_store import DurableExecutionJobStore
from thinkbox.cloud_execution.workspace import WorkspaceBinding, WorkspaceRegistry


class DurableCloudExecutionEngine(CloudExecutionEngine):
    """Cloud execution with SQLite-backed queue and worker claims."""

    def __init__(
        self,
        provider: CloudExecutionProvider,
        db_path: str | Path,
        workspace_registry: WorkspaceRegistry | None = None,
        admission: ExecutionAdmissionGate | None = None,
        admission_token_hook: AdmissionTokenHook | None = None,
        run_recovery: bool = True,
    ) -> None:
        store = DurableExecutionJobStore(db_path)
        self._durable_store = store
        self._queue = ExecutionJobQueue(store)
        super().__init__(
            provider,
            workspace_registry=workspace_registry,
            job_store=store,
            admission=admission,
        )
        self._token_hook = admission_token_hook or noop_admission_token_hook()
        if run_recovery:
            self._recovery_summary = recover_after_restart(store, self._queue)
        else:
            self._recovery_summary = {}

    @property
    def queue(self) -> ExecutionJobQueue:
        return self._queue

    @property
    def durable_store(self) -> DurableExecutionJobStore:
        return self._durable_store

    @property
    def recovery_summary(self) -> dict[str, Any]:
        return dict(self._recovery_summary)

    def enqueue_intent(
        self,
        intent: str,
        limits: ResourceLimits,
        workspace: WorkspaceBinding,
        job_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        admission_token: str | None = None,
    ) -> QueuedJobRecord:
        self._token_hook.validate_token(
            ExecutionJob(intent=intent, job_id=job_id or ""),
            limits,
            workspace,
            admission_token,
        )
        return self._queue.enqueue(
            intent,
            limits,
            workspace,
            self._provider.name,
            job_id=job_id,
            metadata=metadata,
        )

    def run_claimed(
        self,
        record: QueuedJobRecord,
        claim_token: str,
        admission_token: str | None = None,
    ) -> ExecutionAttemptReceipt:
        job = record.job
        limits = record.limits
        workspace = record.workspace
        self._token_hook.validate_token(job, limits, workspace, admission_token)
        try:
            receipt = self.execute(job, limits, workspace)
            job.metadata["last_exit_code"] = receipt.exit_code
            self._durable_store.put(job)
            if job.state == ExecutionJobState.SUCCEEDED:
                self._queue.complete(job.job_id, claim_token)
                disposition = QueueDisposition.COMPLETED
            elif job.state == ExecutionJobState.CANCELLED:
                self._queue.cancel(job.job_id)
                disposition = QueueDisposition.CANCELLED
            else:
                self._queue.fail(job.job_id, claim_token)
                disposition = QueueDisposition.FAILED
            self._durable_store.save_receipt(
                job.job_id,
                json.dumps(receipt.snapshot(), sort_keys=True),
                disposition,
            )
            return receipt
        except AdmissionDeniedError:
            self._queue.fail(job.job_id, claim_token)
            raise
