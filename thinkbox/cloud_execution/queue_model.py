"""Queued job representation (PR #198)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from thinkbox.cloud_execution.job import ExecutionJob, ExecutionJobState
from thinkbox.cloud_execution.resources import ResourceLimits
from thinkbox.cloud_execution.workspace import WorkspaceBinding


class QueueDisposition(str, Enum):
    QUEUED = "QUEUED"
    CLAIMED = "CLAIMED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class QueuedJobRecord:
    job: ExecutionJob
    limits: ResourceLimits
    workspace: WorkspaceBinding
    queue_disposition: QueueDisposition
    queue_position: int
    attempt_count: int
    max_retries: int
    claimed_by: str | None = None
    claim_token: str | None = None
    claim_lease_until: str | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "job": self.job.snapshot(),
            "limits": self.limits.snapshot(),
            "workspace": self.workspace.snapshot(),
            "queue_disposition": self.queue_disposition.value,
            "queue_position": self.queue_position,
            "attempt_count": self.attempt_count,
            "max_retries": self.max_retries,
            "claimed_by": self.claimed_by,
            "claim_token": self.claim_token,
            "claim_lease_until": self.claim_lease_until,
        }
