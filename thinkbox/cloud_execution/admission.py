"""Fail-closed execution admission (PR #197)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from thinkbox.cloud_execution.errors import AdmissionDeniedError
from thinkbox.cloud_execution.job import ExecutionJob
from thinkbox.cloud_execution.provider import CloudExecutionProvider
from thinkbox.cloud_execution.resources import ResourceLimits
from thinkbox.cloud_execution.workspace import WorkspaceBinding, WorkspaceRegistry


PolicyFn = Callable[[ExecutionJob, ResourceLimits, WorkspaceBinding], None]


@dataclass
class AdmissionDecision:
    admitted: bool
    reason: str = ""
    metadata: dict[str, Any] | None = None


class ExecutionAdmissionGate:
    """Admission before any provider invocation."""

    def __init__(
        self,
        workspace_registry: WorkspaceRegistry,
        policy: PolicyFn | None = None,
    ) -> None:
        self._workspaces = workspace_registry
        self._policy = policy

    def admit(
        self,
        job: ExecutionJob,
        limits: ResourceLimits,
        workspace: WorkspaceBinding,
        provider: CloudExecutionProvider,
    ) -> AdmissionDecision:
        if not job.intent.strip():
            raise AdmissionDeniedError("intent required")
        if not job.job_id:
            raise AdmissionDeniedError("job_id required")
        limits.validate()
        if not provider.is_available():
            raise AdmissionDeniedError("provider unavailable", provider=provider.name)
        if not workspace.workspace_id or not workspace.worktree_path:
            raise AdmissionDeniedError("workspace identity incomplete")
        if self._policy is not None:
            self._policy(job, limits, workspace)
        from thinkbox.cloud_execution.errors import WorkspaceConflictError

        try:
            self._workspaces.bind(workspace, job.job_id)
        except WorkspaceConflictError as exc:
            raise AdmissionDeniedError(
                "workspace already bound",
                workspace_id=workspace.workspace_id,
            ) from exc
        return AdmissionDecision(admitted=True, reason="ok", metadata={"provider": provider.name})
