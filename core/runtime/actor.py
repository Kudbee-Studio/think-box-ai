"""Actor for THINK BOX AI."""

from __future__ import annotations

from typing import Any


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

    async def execute_step(self, agent: Any, think_box: Any, step: Any) -> dict[str, Any]:
        tool_registry = getattr(agent, "tool_registry", self.tool_registry)
        if tool_registry is None:
            return {"status": "success", "output": "No tools available"}
        return {"status": "success", "output": f"Executed step: {step.description}"}
