"""Cloud execution engine — Intent → Admission → Provider → Receipt (PR #197)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from thinkbox.cloud_execution.admission import ExecutionAdmissionGate
from thinkbox.cloud_execution.errors import AdmissionDeniedError, InvalidTransitionError
from thinkbox.cloud_execution.job import ExecutionJob, ExecutionJobState
from thinkbox.cloud_execution.lifecycle import transition
from thinkbox.cloud_execution.provider import CloudExecutionProvider
from thinkbox.cloud_execution.receipt import ExecutionAttemptReceipt
from thinkbox.cloud_execution.resources import ResourceLimits
from thinkbox.cloud_execution.store import ExecutionJobStore
from thinkbox.cloud_execution.workspace import WorkspaceBinding, WorkspaceRegistry


class CloudExecutionEngine:
    def __init__(
        self,
        provider: CloudExecutionProvider,
        workspace_registry: WorkspaceRegistry | None = None,
        job_store: ExecutionJobStore | None = None,
        admission: ExecutionAdmissionGate | None = None,
    ) -> None:
        self._provider = provider
        self._workspaces = workspace_registry or WorkspaceRegistry()
        self._store = job_store or ExecutionJobStore()
        self._admission = admission or ExecutionAdmissionGate(self._workspaces)

    @property
    def workspace_registry(self) -> WorkspaceRegistry:
        return self._workspaces

    def submit_intent(
        self,
        intent: str,
        limits: ResourceLimits,
        workspace: WorkspaceBinding,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionJob:
        job = ExecutionJob(intent=intent, provider_name=self._provider.name, metadata=metadata or {})
        job.workspace_id = workspace.workspace_id
        self._store.put(job)
        return job

    def execute(
        self,
        job: ExecutionJob,
        limits: ResourceLimits,
        workspace: WorkspaceBinding,
    ) -> ExecutionAttemptReceipt:
        try:
            self._admission.admit(job, limits, workspace, self._provider)
            job.state = transition(job.state, ExecutionJobState.ADMITTED)
            job.state = transition(job.state, ExecutionJobState.STARTING)
            job.state = transition(job.state, ExecutionJobState.RUNNING)
            job.updated_at = datetime.now(timezone.utc).isoformat()
            result = self._provider.run(job, limits, workspace)
            if result.success:
                job.state = transition(job.state, ExecutionJobState.SUCCEEDED)
            else:
                scenario = str(result.metadata.get("scenario", ""))
                if scenario == "timeout":
                    job.state = transition(job.state, ExecutionJobState.TIMED_OUT)
                elif scenario == "cancel":
                    job.state = transition(job.state, ExecutionJobState.CANCELLED)
                else:
                    job.state = transition(job.state, ExecutionJobState.FAILED)
            receipt = self._provider.build_receipt(job, limits, workspace, result, job.state)
            self._store.put(job)
            return receipt
        except AdmissionDeniedError:
            job.state = ExecutionJobState.BLOCKED
            self._store.put(job)
            raise
        except InvalidTransitionError:
            job.state = ExecutionJobState.FAILED
            self._store.put(job)
            raise
        finally:
            if workspace.workspace_id:
                self._workspaces.release(workspace.workspace_id, job.job_id)
