"""Structured errors for cloud execution substrate (PR #197)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class CloudExecutionError(Exception):
    agent_id: str = "cloud_execution"
    task_id: str = ""
    think_box_id: str = ""
    timestamp: str = ""
    error_type: str = "CloudExecutionError"
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        super().__init__(self.error_type)

    def __str__(self) -> str:
        return f"{self.error_type}: {self.context}"


class AdmissionDeniedError(CloudExecutionError):
    def __init__(self, reason: str, **ctx: Any) -> None:
        super().__init__(
            error_type="AdmissionDenied",
            context={"reason": reason, **ctx},
        )


class InvalidTransitionError(CloudExecutionError):
    def __init__(self, message: str) -> None:
        super().__init__(
            error_type="InvalidTransition",
            context={"message": message},
        )


class WorkspaceConflictError(CloudExecutionError):
    def __init__(self, workspace_id: str, job_id: str) -> None:
        super().__init__(
            error_type="WorkspaceConflict",
            context={"workspace_id": workspace_id, "bound_job_id": job_id},
        )


class ProviderUnavailableError(CloudExecutionError):
    def __init__(self, provider_name: str) -> None:
        super().__init__(
            error_type="ProviderUnavailable",
            context={"provider": provider_name},
        )
