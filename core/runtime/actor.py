"""Actor for THINK BOX AI."""

from __future__ import annotations

from typing import Any

from core.execution.base import ExecResult, ExecutionUnavailableError
from core.foundation.errors import ToolPermissionError
from core.foundation.logging import get_logger

logger = get_logger(__name__)


class Actor:
    def __init__(
        self,
        tool_registry: Any = None,
        approval_gate: Any = None,
        audit_log: Any = None,
        memory_store: Any = None,
        execution_provider: Any = None,
    ) -> None:
        self.tool_registry = tool_registry
        self.approval_gate = approval_gate
        self.audit_log = audit_log
        self.memory_store = memory_store
        self.execution_provider = execution_provider

    async def execute_step(self, agent: Any, think_box: Any, step: Any) -> dict[str, Any]:
        # Execute steps are routed to the Execution provider (local or
        # Firecracker microVM). This is independent of the tool registry and
        # takes priority: execution is a dedicated substrate, not a tool.
        if step.action == "execute" and step.command:
            return await self._execute_via_provider(agent, think_box, step)

        tool_registry = getattr(agent, "tool_registry", self.tool_registry)
        if tool_registry is None:
            return {"status": "success", "output": "No tools available"}

        return {"status": "success", "output": f"Executed step: {step.description}"}

    async def _execute_via_provider(self, agent: Any, think_box: Any, step: Any) -> dict[str, Any]:
        provider = self.execution_provider
        if provider is None:
            return {"status": "success", "output": f"[no-execution-provider] {step.command}"}

        # Governance gate: EXEC permission must be satisfied before the
        # command is handed to the execution substrate.
        if self.approval_gate is not None and self.audit_log is not None:
            agent_id = getattr(agent, "agent_id", "unknown")
            requires_approval = self.approval_gate.require_approval(
                tool_name="shell_exec",
                permission="exec",
                context={"agent_id": agent_id, "step": step.id},
            )
            if requires_approval:
                self.audit_log.record(
                    action="execution_blocked",
                    actor=agent_id,
                    outcome="denied",
                    metadata={"reason": "approval_required", "step": step.id},
                )
                raise ToolPermissionError(
                    message=f"Execution of step {step.id} requires approval",
                    agent_id=agent_id,
                    context={"step": step.id},
                )

        try:
            result: ExecResult = await provider.execute(step.command)
        except ExecutionUnavailableError as e:
            logger.warning("Execution provider unavailable", extra={"error": str(e)})
            return {
                "status": "error",
                "output": "",
                "error": str(e),
                "provider": getattr(provider, "name", "unknown"),
            }

        return {
            "status": "success" if result.return_code == 0 else "error",
            "output": result.stdout,
            "stderr": result.stderr,
            "return_code": result.return_code,
            "provider": result.provider,
            "microvm_id": result.microvm_id,
            "duration": result.duration,
        }
