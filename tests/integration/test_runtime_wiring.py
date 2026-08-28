"""Integration tests for runtime wiring: Planner, Actor, Agent.

Tests that the provider → planner → actor → tools → memory → observer
loop works correctly with mock providers and tools.
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from core.foundation.bootstrap import RuntimeContext, bootstrap, shutdown
from core.foundation.config import ThinkBoxConfig
from core.foundation.errors import ApprovalDeniedError, ToolApprovalRequiredError
from core.governance.audit import ApprovalGate, AuditLog, PermissionChecker, ApprovalPolicy
from core.providers.base import CompletionResponse, Message
from core.runtime.actor import Actor
from core.runtime.agent import Agent, Goal, ThinkBox
from core.runtime.observer import Observer
from core.runtime.planner import Planner, Step
from core.runtime.thinkbox import ThinkBoxLifecycle
from core.tools.registry import ToolDefinition, ToolRegistry


def _make_mock_provider(steps_json: str) -> AsyncMock:
    provider = AsyncMock()
    provider.complete = AsyncMock(
        return_value=CompletionResponse(content=steps_json, model="mock-model")
    )
    return provider


class TestPlannerWithProvider(unittest.TestCase):
    def test_planner_uses_provider_when_available(self) -> None:
        steps_json = '[{"id": "s1", "description": "Do something", "action": "file_read", "parameters": {"path": "/tmp/x"}}]'
        provider = _make_mock_provider(steps_json)
        planner = Planner(task_memory=None, provider=provider)
        tb = ThinkBox(goal=Goal(statement="test goal"))

        steps = asyncio.run(planner.plan(tb))

        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].action, "file_read")
        self.assertEqual(steps[0].parameters, {"path": "/tmp/x"})
        provider.complete.assert_called_once()

    def test_planner_falls_back_on_provider_error(self) -> None:
        provider = AsyncMock()
        provider.complete = AsyncMock(side_effect=Exception("boom"))
        planner = Planner(task_memory=None, provider=provider)
        tb = ThinkBox(goal=Goal(statement="test goal"))

        steps = asyncio.run(planner.plan(tb))

        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].action, "execute")

    def test_planner_placeholder_without_provider(self) -> None:
        planner = Planner(task_memory=None)
        tb = ThinkBox(goal=Goal(statement="test goal"))

        steps = asyncio.run(planner.plan(tb))

        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].action, "execute")
        self.assertIn("test goal", steps[0].description)


class TestActorWithTools(unittest.TestCase):
    def test_actor_executes_registered_tool(self) -> None:
        async def handler(params: dict) -> dict:
            return {"status": "success", "content": "hello"}

        tool_def = ToolDefinition(
            name="my_tool",
            description="A tool",
            handler=handler,
            permission="read_only",
        )
        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)
        registry.register(tool_def)

        checker = PermissionChecker(policy=ApprovalPolicy.AUTO_APPROVE_ALL)
        gate = ApprovalGate(checker, audit)

        actor = Actor(tool_registry=registry, approval_gate=gate, audit_log=audit)
        agent = Agent(agent_id="agent-1", tool_registry=registry, approval_gate=gate, audit_log=audit)
        tb = ThinkBox(goal=Goal(statement="test"))
        step = Step(id="s1", description="Run my_tool", action="my_tool", parameters={})

        result = asyncio.run(actor.execute_step(agent, tb, step))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["content"], "hello")

    def test_actor_raises_approval_required(self) -> None:
        async def handler(params: dict) -> dict:
            return {"status": "success", "content": "secret"}

        tool_def = ToolDefinition(
            name="restricted_tool",
            description="Needs approval",
            handler=handler,
            permission="restricted",
        )
        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)
        registry.register(tool_def)

        checker = PermissionChecker(policy=ApprovalPolicy.MANUAL)
        gate = ApprovalGate(checker, audit)

        actor = Actor(tool_registry=registry, approval_gate=gate, audit_log=audit)
        agent = Agent(agent_id="agent-1", tool_registry=registry, approval_gate=gate, audit_log=audit)
        tb = ThinkBox(goal=Goal(statement="test"))
        step = Step(id="s1", description="Run restricted", action="restricted_tool", parameters={})

        with self.assertRaises(ToolApprovalRequiredError):
            asyncio.run(actor.execute_step(agent, tb, step))

    def test_actor_raises_on_gate_error(self) -> None:
        async def handler(params: dict) -> dict:
            return {"status": "success", "content": "data"}

        tool_def = ToolDefinition(
            name="my_tool",
            description="A tool",
            handler=handler,
            permission="read_only",
        )
        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)
        registry.register(tool_def)

        gate = MagicMock()
        gate.require_approval = MagicMock(side_effect=RuntimeError("gate crashed"))

        actor = Actor(tool_registry=registry, approval_gate=gate, audit_log=audit)
        agent = Agent(agent_id="agent-1", tool_registry=registry, approval_gate=gate, audit_log=audit)
        tb = ThinkBox(goal=Goal(statement="test"))
        step = Step(id="s1", description="Run tool", action="my_tool", parameters={})

        with self.assertRaises(ApprovalDeniedError):
            asyncio.run(actor.execute_step(agent, tb, step))

    def test_actor_no_tools_returns_success(self) -> None:
        actor = Actor(tool_registry=None)
        agent = Agent(agent_id="agent-1")
        tb = ThinkBox(goal=Goal(statement="test"))
        step = Step(id="s1", description="noop", action="execute")

        result = asyncio.run(actor.execute_step(agent, tb, step))

        self.assertEqual(result["status"], "success")


class TestAgentRunLoop(unittest.TestCase):
    def test_full_run_with_mock_provider_and_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = bootstrap(project_root=Path(tmp), log_level="WARNING")
            try:
                steps_json = '[{"id": "s1", "description": "Read config", "action": "file_read", "parameters": {"path": "/tmp/cfg.txt"}}]'
                provider = _make_mock_provider(steps_json)

                async def file_handler(params: dict) -> dict:
                    return {"status": "success", "content": "config data"}

                mock_store = MagicMock()
                audit = AuditLog(mock_store)
                registry = ToolRegistry(audit)
                registry.register(ToolDefinition(
                    name="file_read",
                    description="Read file",
                    handler=file_handler,
                    permission="read_only",
                ))

                checker = PermissionChecker(policy=ApprovalPolicy.AUTO_APPROVE_ALL)
                gate = ApprovalGate(checker, audit)

                agent = Agent(
                    agent_id="agent-1",
                    session_memory=ctx.create_session("s1", "agent-1"),
                    task_memory=ctx.create_task_memory("t1", "g1", "agent-1"),
                    config=ThinkBoxConfig(),
                    tool_registry=registry,
                    approval_gate=gate,
                    audit_log=audit,
                    provider=provider,
                )

                goal = Goal(statement="Read the config file")
                result = asyncio.run(agent.run(goal, observer=Observer()))

                self.assertEqual(result["status"], "success")
                self.assertEqual(result["think_box"].state, "complete")
            finally:
                shutdown(ctx)

    def test_run_without_provider_backward_compat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = bootstrap(project_root=Path(tmp), log_level="WARNING")
            try:
                agent = Agent(
                    agent_id="agent-1",
                    session_memory=ctx.create_session("s1", "agent-1"),
                    task_memory=ctx.create_task_memory("t1", "g1", "agent-1"),
                    config=ThinkBoxConfig(),
                )

                goal = Goal(statement="Simple goal")
                result = asyncio.run(agent.run(goal))

                self.assertEqual(result["status"], "success")
            finally:
                shutdown(ctx)

    def test_run_with_explicit_planner_and_actor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = bootstrap(project_root=Path(tmp), log_level="WARNING")
            try:
                session = ctx.create_session("s1", "agent-1")
                task_memory = ctx.create_task_memory("t1", "g1", "agent-1")

                agent = Agent(agent_id="agent-1", config=ThinkBoxConfig())

                planner = Planner(task_memory=task_memory)
                actor = Actor(tool_registry=None)

                goal = Goal(statement="Explicit planner and actor")
                result = asyncio.run(agent.run(goal, planner=planner, actor=actor))

                self.assertEqual(result["status"], "success")
            finally:
                shutdown(ctx)


if __name__ == "__main__":
    unittest.main()
