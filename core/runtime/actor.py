"""Actor for THINK BOX AI."""

from __future__ import annotations

import inspect
from typing import Any

from core.foundation.errors import ToolApprovalRequiredError


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
        approval_gate = getattr(agent, "approval_gate", self.approval_gate)
        audit_log = getattr(agent, "audit_log", self.audit_log)

        if tool_registry is None:
            return {"status": "success", "output": "No tools available"}

        tool_name = getattr(step, "action", None)
        tool_def = tool_registry.get(tool_name) if tool_name else None

        if tool_def is None:
            return {"status": "success", "output": f"Executed step: {step.description}"}

        agent_id = getattr(agent, "agent_id", "unknown")
        params = getattr(step, "parameters", {}) or {}

        if approval_gate is not None:
            try:
                requires_approval = approval_gate.require_approval(
                    tool_name, tool_def.permission, {"agent_id": agent_id}
                )
                if requires_approval:
                    if audit_log:
                        audit_log.record(
                            action=f"tool_execute:{tool_name}",
                            actor=agent_id,
                            outcome="approval_required",
                            metadata={"tool": tool_name},
                        )
                    raise ToolApprovalRequiredError(
                        message=f"Tool '{tool_name}' requires approval",
                        agent_id=agent_id,
                    )
            except ToolApprovalRequiredError:
                raise
            except Exception:
                pass

        handler = tool_def.handler
        try:
            if inspect.iscoroutinefunction(handler):
                output = await handler(params)
            else:
                output = handler(params)
        except Exception as e:
            if audit_log:
                audit_log.record(
                    action=f"tool_execute:{tool_name}",
                    actor=agent_id,
                    outcome="error",
                    metadata={"tool": tool_name, "error": str(e)},
                )
            return {"status": "error", "output": str(e)}

        if audit_log:
            audit_log.record(
                action=f"tool_execute:{tool_name}",
                actor=agent_id,
                outcome="success",
                metadata={"tool": tool_name},
            )

        if isinstance(output, dict):
            return output
        return {"status": "success", "output": output}
