"""Actor for THINK BOX AI."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("thinkbox.runtime.actor")


class Actor:
    def __init__(
        self,
        tool_registry: Any = None,
        approval_gate: Any = None,
        audit_log: Any = None,
        memory_store: Any = None,
    ) -> None:
        self.tool_registry = tool_registry
        self.approval_gate = approval_gate
        self.audit_log = audit_log
        self.memory_store = memory_store

    async def execute_step(
        self,
        agent: Any,
        think_box: Any,
        step: Any,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tool_registry = getattr(agent, "tool_registry", self.tool_registry)
        if tool_registry is None:
            return {"status": "success", "output": "No tools available"}
        step_tool = getattr(step, "tool", None) or getattr(step, "action", None)
        if step_tool is None or step_tool == "execute":
            return {"status": "success", "output": f"Executed step: {step.description}"}
        from core.foundation.errors import ToolNotFoundError

        tool_def = tool_registry.get(step_tool)
        if tool_def is None:
            raise ToolNotFoundError(f"Tool not found: {step_tool}")
        step_input = getattr(step, "input", {}) or {}
        if context is None:
            context = {}
        if self.memory_store is not None and "memory_store" not in context:
            context["memory_store"] = self.memory_store
        result = await tool_def.handler(step_input, context)
        logger.info(
            "actor_step tool=%s outcome=%s",
            step_tool, result.get("status", "unknown"),
        )
        return {"status": "success", "tool": step_tool, "output": result}
