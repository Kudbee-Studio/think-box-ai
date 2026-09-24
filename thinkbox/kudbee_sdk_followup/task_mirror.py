"""Task lifecycle helpers (PR #179 F12)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SdkTaskFollowup:
    task_id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    result: Any | None = None
    error: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)

    def start(self) -> None:
        if self.status not in (TaskStatus.PENDING,):
            raise ValueError("task already started")
        self.status = TaskStatus.RUNNING

    def complete(self, result: Any) -> None:
        self.status = TaskStatus.COMPLETED
        self.result = result

    def fail(self, message: str) -> None:
        self.status = TaskStatus.FAILED
        self.error = message

    def record_event(self, name: str, payload: dict[str, Any] | None = None) -> None:
        self.events.append({"name": name, "payload": payload or {}})
