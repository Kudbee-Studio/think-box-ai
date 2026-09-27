"""Cloud execution provider abstraction — provider-neutral (PR #197)."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from thinkbox.cloud_execution.heartbeat import WorkerHeartbeat
from thinkbox.cloud_execution.job import ExecutionJob
from thinkbox.cloud_execution.receipt import ExecutionAttemptReceipt
from thinkbox.cloud_execution.resources import ResourceLimits
from thinkbox.cloud_execution.workspace import WorkspaceBinding


@dataclass
class ProviderRunResult:
    success: bool
    exit_code: int
    summary: str = ""
    artifact_refs: list[str] = field(default_factory=list)
    heartbeat: WorkerHeartbeat | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class CloudExecutionProvider(abc.ABC):
    """Adapter boundary for cloud execution substrates."""

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @abc.abstractmethod
    def is_available(self) -> bool: ...

    @abc.abstractmethod
    def run(
        self,
        job: ExecutionJob,
        limits: ResourceLimits,
        workspace: WorkspaceBinding,
    ) -> ProviderRunResult: ...

    def build_receipt(
        self,
        job: ExecutionJob,
        limits: ResourceLimits,
        workspace: WorkspaceBinding,
        result: ProviderRunResult,
        lifecycle_state: Any,
    ) -> ExecutionAttemptReceipt:
        from thinkbox.cloud_execution.job import ExecutionJobState

        hb = result.heartbeat
        hb_status = hb.status() if hb else None
        from thinkbox.cloud_execution.heartbeat import HeartbeatStatus

        return ExecutionAttemptReceipt(
            job_id=job.job_id,
            execution_id=job.execution_id,
            provider=self.name,
            workspace_id=workspace.workspace_id,
            lifecycle_state=lifecycle_state,
            started_at=job.created_at,
            resource_limits=limits,
            exit_code=result.exit_code,
            result_summary=result.summary,
            heartbeat_status=hb_status or HeartbeatStatus.MISSING,
            artifact_refs=list(result.artifact_refs),
            verification_class="TEST_VERIFIED",
            live_api_called=False,
            metadata=dict(result.metadata),
        )
