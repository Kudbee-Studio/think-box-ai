"""Agent runtime for THINK BOX AI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.runtime.thinkbox import ThinkBoxLifecycle


@dataclass
class Goal:
    statement: str
    success_criteria: list[str] = field(default_factory=list)


@dataclass
class ThinkBox:
    goal: Goal
    state: str = "created"
    context: dict[str, Any] = field(default_factory=dict)


class Agent:
    def __init__(
        self,
        agent_id: str,
        session_memory: Any = None,
        task_memory: Any = None,
        config: Any = None,
        tool_registry: Any = None,
    ) -> None:
        self.agent_id = agent_id
        self.session_memory = session_memory
        self.task_memory = task_memory
        self.config = config
        self.tool_registry = tool_registry

    def create_think_box(self, goal: Goal) -> ThinkBox:
        return ThinkBox(goal=goal)

    async def run(
        self,
        goal: Goal,
        planner: Any = None,
        actor: Any = None,
        observer: Any = None,
    ) -> dict[str, Any]:
        tb = self.create_think_box(goal)
        ThinkBoxLifecycle.transition(tb, "planning")
        steps = planner.plan(tb) if planner else []
        ThinkBoxLifecycle.transition(tb, "executing")
        for step in steps:
            result = await actor.execute_step(self, tb, step) if actor else {"status": "success"}
            if observer and not observer.validate(tb, step, result):
                ThinkBoxLifecycle.transition(tb, "failed")
                return {"status": "failed", "think_box": tb}
        ThinkBoxLifecycle.transition(tb, "observing")
        ThinkBoxLifecycle.transition(tb, "complete")
        return {"status": "success", "think_box": tb}
