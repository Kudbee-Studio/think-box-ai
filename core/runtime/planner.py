"""Planner for THINK BOX AI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Step:
    id: str
    description: str
    action: str
    expected_output: dict[str, Any] | None = None
    command: str | None = None


class Planner:
    def __init__(self, task_memory: Any = None) -> None:
        self.task_memory = task_memory

    def plan(self, think_box: Any) -> list[Step]:
        goal = getattr(think_box, "goal", None)
        statement = goal.statement if goal else "unknown goal"
        return [
            Step(
                id="step-1",
                description=f"Analyze and execute: {statement}",
                action="execute",
                expected_output={"status": "success"},
            )
        ]
