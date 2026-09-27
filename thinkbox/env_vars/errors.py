"""Structured errors for environmental variable loading (PR #200)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EnvVarsError(Exception):
    """Fail-closed env load/parse error with operator context."""

    error_type: str
    message: str
    env_key: str | None = None
    agent_id: str = "env-vars"
    task_id: str = "load"
    think_box_id: str = "hermetic"
    timestamp: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.error_type}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "think_box_id": self.think_box_id,
            "timestamp": self.timestamp,
            "error_type": self.error_type,
            "env_key": self.env_key,
            "message": self.message,
            "context": self.context,
        }
