"""Structured execution attempt receipts (PR #197)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from thinkbox.cloud_execution.heartbeat import HeartbeatStatus
from thinkbox.cloud_execution.job import ExecutionJobState
from thinkbox.cloud_execution.resources import ResourceLimits


@dataclass
class ExecutionAttemptReceipt:
    job_id: str
    execution_id: str
    provider: str
    workspace_id: str
    lifecycle_state: ExecutionJobState
    started_at: str
    ended_at: str = ""
    resource_limits: ResourceLimits | None = None
    exit_code: int | None = None
    result_summary: str = ""
    heartbeat_status: HeartbeatStatus = HeartbeatStatus.MISSING
    artifact_refs: list[str] = field(default_factory=list)
    verification_class: str = "TEST_VERIFIED"
    live_api_called: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.verification_class == "LIVE_VERIFIED":
            raise ValueError("receipt cannot claim LIVE_VERIFIED from substrate layer")

    def finalize(self) -> None:
        if not self.ended_at:
            self.ended_at = datetime.now(timezone.utc).isoformat()

    def snapshot(self) -> dict[str, Any]:
        self.finalize()
        return {
            "job_id": self.job_id,
            "execution_id": self.execution_id,
            "provider": self.provider,
            "workspace_id": self.workspace_id,
            "lifecycle_state": self.lifecycle_state.value,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "resource_limits": self.resource_limits.snapshot() if self.resource_limits else None,
            "exit_code": self.exit_code,
            "result_summary": self.result_summary,
            "heartbeat_status": self.heartbeat_status.value,
            "artifact_refs": list(self.artifact_refs),
            "verification_class": self.verification_class,
            "live_api_called": self.live_api_called,
            "metadata": self.metadata,
        }
