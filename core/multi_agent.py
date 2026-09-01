"""Multi-agent coordination — sub-agents, handoffs, and parallel execution."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from core.observability import Trace, Span, SpanType, SpanStatus


class AgentRole(str, Enum):
    RESEARCHER = "researcher"
    RUNNER = "runner"
    REVIEWER = "reviewer"
    DIRECTOR = "director"
    CAMERA = "camera"
    JURY = "jury"


@dataclass
class AgentTask:
    goal: str
    role: AgentRole = AgentRole.RESEARCHER
    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    parent_task_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    status: str = "pending"

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "role": self.role.value,
            "parent_task_id": self.parent_task_id,
            "status": self.status,
            "result": self.result,
        }


@dataclass
class SubAgentResult:
    agent_id: str
    role: AgentRole
    goal: str
    status: str
    output: str = ""
    artifacts: list[str] = field(default_factory=list)
    error: str | None = None
    tokens_used: int = 0
    cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role.value,
            "goal": self.goal,
            "status": self.status,
            "output": self.output,
            "artifacts": self.artifacts,
            "error": self.error,
            "tokens_used": self.tokens_used,
            "cost_usd": round(self.cost_usd, 6),
        }


class AgentPool:
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._semaphore = asyncio.Semaphore(max_workers)
        self._results: dict[str, SubAgentResult] = {}

    async def submit(self, task: AgentTask, agent_runner: Any) -> SubAgentResult:
        async with self._semaphore:
            agent_id = f"agent_{uuid.uuid4().hex()[:8]}"
            result = await self._run_agent(agent_id, task, agent_runner)
            self._results[task.task_id] = result
            return result

    async def submit_all(
        self, tasks: list[AgentTask], agent_runner: Any
    ) -> list[SubAgentResult]:
        coros = [self.submit(t, agent_runner) for t in tasks]
        return await asyncio.gather(*coros, return_exceptions=False)

    async def _run_agent(
        self, agent_id: str, task: AgentTask, agent_runner: Any
    ) -> SubAgentResult:
        task.status = "running"
        try:
            result = await agent_runner(task)
            task.status = "completed"
            task.result = result
            return SubAgentResult(
                agent_id=agent_id,
                role=task.role,
                goal=task.goal,
                status="completed",
                output=result.get("output", ""),
                artifacts=result.get("artifacts", []),
                tokens_used=result.get("tokens_used", 0),
                cost_usd=result.get("cost_usd", 0.0),
            )
        except Exception as e:
            task.status = "failed"
            return SubAgentResult(
                agent_id=agent_id,
                role=task.role,
                goal=task.goal,
                status="failed",
                error=str(e),
            )

    def get_result(self, task_id: str) -> SubAgentResult | None:
        return self._results.get(task_id)


class AgentHandoff:
    def __init__(self):
        self._context: dict[str, Any] = {}

    def transfer(self, from_agent: str, to_agent: str, context: dict[str, Any]) -> None:
        self._context[to_agent] = {
            "from": from_agent,
            "context": context,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def receive(self, agent_id: str) -> dict[str, Any]:
        return self._context.pop(agent_id, {})

    def get_context(self, agent_id: str) -> dict[str, Any]:
        return self._context.get(agent_id, {}).get("context", {})


class ParallelExecutor:
    def __init__(self, max_concurrency: int = 5):
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def execute_tool_calls(
        self,
        calls: list[dict[str, Any]],
        registry: Any,
        trace: Trace,
        parent_span_id: str | None = None,
    ) -> list[dict[str, Any]]:
        coros = [
            self._exec_single_call(call, registry, trace, parent_span_id)
            for call in calls
        ]
        return await asyncio.gather(*coros, return_exceptions=False)

    async def _exec_single_call(
        self,
        call: dict[str, Any],
        registry: Any,
        trace: Trace,
        parent_span_id: str | None,
    ) -> dict[str, Any]:
        tool_name = call.get("tool", "")
        tool_args = call.get("args", {})
        async with self._semaphore:
            span = trace.start_span(
                name=f"tool:{tool_name}",
                span_type=SpanType.TOOL_CALL,
                parent_span_id=parent_span_id,
                input_data={"tool": tool_name, "args": tool_args},
            )
            try:
                result = await registry.execute(tool_name, tool_args)
                trace.end_span(
                    span,
                    output=result,
                    status=SpanStatus.OK if result.get("success") else SpanStatus.ERROR,
                )
                return {"tool": tool_name, "result": result}
            except Exception as e:
                trace.end_span(span, error=str(e), status=SpanStatus.ERROR)
                return {"tool": tool_name, "result": {"success": False, "error": str(e)}}
