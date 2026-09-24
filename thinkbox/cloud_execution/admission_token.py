"""Optional governed admission token hook (PR #198) — default disabled."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from thinkbox.cloud_execution.job import ExecutionJob
from thinkbox.cloud_execution.resources import ResourceLimits
from thinkbox.cloud_execution.workspace import WorkspaceBinding


class AdmissionTokenHook(Protocol):
    def validate_token(
        self,
        job: ExecutionJob,
        limits: ResourceLimits,
        workspace: WorkspaceBinding,
        token: str | None,
    ) -> None: ...


@dataclass
class DisabledAdmissionTokenHook:
    """No-op hook — safe default for hermetic Phase 2."""

    enabled: bool = False

    def validate_token(
        self,
        job: ExecutionJob,
        limits: ResourceLimits,
        workspace: WorkspaceBinding,
        token: str | None,
    ) -> None:
        if not self.enabled:
            return
        if not token:
            from thinkbox.cloud_execution.errors import AdmissionDeniedError

            raise AdmissionDeniedError("admission token required when hook enabled")


def noop_admission_token_hook() -> DisabledAdmissionTokenHook:
    return DisabledAdmissionTokenHook(enabled=False)
