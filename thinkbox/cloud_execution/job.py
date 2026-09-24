"""Persistent execution-job model (PR #197)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ExecutionJobState(str, Enum):
    QUEUED = "QUEUED"
    ADMITTED = "ADMITTED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    BLOCKED = "BLOCKED"


TERMINAL_STATES: frozenset[ExecutionJobState] = frozenset(
    {
        ExecutionJobState.SUCCEEDED,
        ExecutionJobState.FAILED,
        ExecutionJobState.CANCELLED,
        ExecutionJobState.TIMED_OUT,
        ExecutionJobState.BLOCKED,
    },
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class ExecutionJob:
    """Durable execution job record (in-memory or serialized)."""

    job_id: str = ""
    execution_id: str = ""
    intent: str = ""
    provider_name: str = ""
    state: ExecutionJobState = ExecutionJobState.QUEUED
    workspace_id: str = ""
    session_id: str | None = None
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.job_id:
            self.job_id = _new_id("cex_job")
        if not self.execution_id:
            self.execution_id = _new_id("cex_exec")
        now = _now()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def snapshot(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "execution_id": self.execution_id,
            "intent": self.intent,
            "provider_name": self.provider_name,
            "state": self.state.value,
            "workspace_id": self.workspace_id,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }
