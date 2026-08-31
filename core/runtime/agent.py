"""Agent runtime for THINK BOX AI."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from core.runtime.thinkbox import ThinkBoxLifecycle

logger = logging.getLogger("thinkbox.runtime.agent")


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
        harness_config: dict[str, Any] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.session_memory = session_memory
        self.task_memory = task_memory
        self.config = config
        self.tool_registry = tool_registry
        self.harness_config = harness_config
        self._harness_runner = None
        self._harness_container_id: str | None = None

    def _harness_enabled(self) -> bool:
        flag = os.environ.get("HARNESS", "")
        if flag == "1":
            return True
        if flag == "0":
            return False
        if self.harness_config is not None:
            return self.harness_config.get("enabled", True)
        from core.runtime.harness import docker_available

        if not docker_available():
            return False
        return True

    def _ensure_harness(self) -> None:
        from core.runtime.harness import HarnessConfig, HarnessLimits, HarnessRunner

        cfg = self.harness_config or {}
        limits = HarnessLimits(
            memory=cfg.get("memory", "2g"),
            cpus=cfg.get("cpus", "1.0"),
            pids_limit=cfg.get("pids_limit", 0),
            read_only_rootfs=cfg.get("read_only_rootfs", False),
        )
        network_mode = cfg.get("network_mode", os.environ.get("HARNESS_NETWORK", "none"))
        config = HarnessConfig(
            enabled=True,
            network_mode=network_mode,
            limits=limits,
            image=cfg.get("image", "ku3bee-harness:dev"),
        )
        runner = HarnessRunner(config)
        container = runner.start_container(
            agent_id=self.agent_id,
            limits=limits,
            mounts={},
            network_mode=network_mode,
        )
        self._harness_runner = runner
        self._harness_container_id = container.container_id

    def _cleanup_harness(self) -> None:
        if self._harness_runner is not None and self._harness_container_id is not None:
            self._harness_runner.stop_container(self._harness_container_id)
            self._harness_runner = None
            self._harness_container_id = None

    def _tool_context(self) -> dict[str, Any]:
        ctx: dict[str, Any] = {"agent_id": self.agent_id}
        if self._harness_runner is not None and self._harness_container_id is not None:
            ctx["harness_runner"] = self._harness_runner
            ctx["harness_container_id"] = self._harness_container_id
        return ctx

    def create_think_box(self, goal: Goal) -> ThinkBox:
        return ThinkBox(goal=goal)

    async def run(
        self,
        goal: Goal,
        planner: Any = None,
        actor: Any = None,
        observer: Any = None,
    ) -> dict[str, Any]:
        if self._harness_enabled():
            self._ensure_harness()
        try:
            return await self._run_loop(goal, planner, actor, observer)
        finally:
            self._cleanup_harness()

    async def _run_loop(
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
            ctx = self._tool_context()
            result = await actor.execute_step(self, tb, step, context=ctx) if actor else {"status": "success"}
            if observer and not observer.validate(tb, step, result):
                ThinkBoxLifecycle.transition(tb, "failed")
                return {"status": "failed", "think_box": tb}
        ThinkBoxLifecycle.transition(tb, "observing")
        ThinkBoxLifecycle.transition(tb, "complete")
        return {"status": "success", "think_box": tb}
