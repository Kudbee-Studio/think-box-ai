"""Integration tests for THINK BOX AI bootstrap and runtime.

These tests verify the full stack works together:
- Bootstrap loads config, initializes memory, creates layers
- Tools can be registered and executed
- Agent can create Think Boxes and run the Planner → Actor → Observer loop
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core.foundation.bootstrap import RuntimeContext, bootstrap, shutdown
from core.foundation.config import ThinkBoxConfig
from core.foundation.errors import ThinkBoxLimitError, ToolApprovalRequiredError, ToolNotFoundError
from core.governance.audit import ApprovalGate, AuditLog, PermissionChecker
from core.memory.store import MemoryStore
from core.memory.session import SessionMemoryAdapter
from core.memory.task import TaskMemoryAdapter
from core.runtime.actor import Actor
from core.runtime.agent import Agent, Goal, ThinkBox
from core.runtime.observer import Observer
from core.runtime.planner import Planner
from core.runtime.thinkbox import ThinkBoxLifecycle
from core.tools import file_read, file_write, http_request, memory_query, shell_exec
from core.tools.registry import ToolDefinition, ToolRegistry, tool


class TestBootstrapIntegration(unittest.TestCase):
    def test_bootstrap_creates_runtime_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = bootstrap(project_root=Path(tmp), log_level="WARNING")
            try:
                self.assertIsInstance(ctx, RuntimeContext)
                self.assertIsInstance(ctx.config, ThinkBoxConfig)
                self.assertIsInstance(ctx.store, MemoryStore)
                self.assertIsInstance(ctx.session_memory, SessionMemoryAdapter)
                self.assertIsNotNone(ctx.org_memory)
            finally:
                shutdown(ctx)

    def test_bootstrap_config_from_pyproject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pyproject = Path(tmp) / "pyproject.toml"
            pyproject.write_text(
                '[project]\nname = "test"\n[tool.thinkbox]\n'
                'default_provider = "anthropic"\nmax_think_box_depth = 5\n'
            )
            ctx = bootstrap(project_root=Path(tmp), log_level="WARNING")
            try:
                self.assertEqual(ctx.config.default_provider, "anthropic")
                self.assertEqual(ctx.config.max_think_box_depth, 5)
            finally:
                shutdown(ctx)

    def test_bootstrap_creates_task_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = bootstrap(project_root=Path(tmp), log_level="WARNING")
            try:
                task_memory = ctx.create_task_memory("task-1", "goal-1", "agent-1")
                self.assertIsInstance(task_memory, TaskMemoryAdapter)
                self.assertEqual(task_memory.task_id, "task-1")
            finally:
                shutdown(ctx)


class TestToolRegistrationIntegration(unittest.TestCase):
    def test_register_and_execute_file_read(self) -> None:
        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)

        builtin_tools = [file_read, file_write, shell_exec, http_request, memory_query]
        for t in builtin_tools:
            if hasattr(t, "_tool_definition"):
                registry.register(t._tool_definition)

        # Create a temp file and read it
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            tmp_path = f.name

        try:
            tool_def = registry.get("file_read")
            self.assertIsNotNone(tool_def)
            result = asyncio.run(tool_def.handler({"path": tmp_path}))
            self.assertEqual(result["content"], "hello world")
        finally:
            Path(tmp_path).unlink()

    def test_register_all_builtin_tools(self) -> None:
        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)

        builtin_tools = [file_read, file_write, shell_exec, http_request, memory_query]
        for t in builtin_tools:
            if hasattr(t, "_tool_definition"):
                registry.register(t._tool_definition)

        self.assertEqual(len(registry.list_tools()), len(builtin_tools))


class TestRuntimeLoopIntegration(unittest.TestCase):
    def test_full_runtime_loop_with_reasoning_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = bootstrap(project_root=Path(tmp), log_level="WARNING")
            try:
                session = ctx.create_session("s1", "agent-1")
                task_memory = ctx.create_task_memory("task-1", "goal-1", "agent-1")
                config = ThinkBoxConfig()
                agent = Agent(
                    agent_id="agent-1",
                    session_memory=session,
                    task_memory=task_memory,
                    config=config,
                )

                goal = Goal(statement="Test goal", success_criteria=["done"])
                tb = agent.create_think_box(goal)

                planner = Planner(task_memory=task_memory)
                steps = planner.plan(tb)
                self.assertGreater(len(steps), 0)

                mock_store = MagicMock()
                audit = AuditLog(mock_store)
                checker = PermissionChecker()
                gate = ApprovalGate(checker, audit)
                registry = ToolRegistry(audit)

                actor = Actor(
                    tool_registry=registry,
                    approval_gate=gate,
                    audit_log=audit,
                    memory_store=ctx.store,
                )

                observer = Observer()

                step = steps[0]
                result = asyncio.run(actor.execute_step(agent, tb, step))
                self.assertEqual(result["status"], "success")

                step.expected_output = {"status": "success"}
                validated = observer.validate(tb, step, result)
                self.assertTrue(validated)

                ThinkBoxLifecycle.transition(tb, "planning")
                ThinkBoxLifecycle.transition(tb, "executing")
                ThinkBoxLifecycle.transition(tb, "observing")
                ThinkBoxLifecycle.transition(tb, "complete")
                self.assertTrue(ThinkBoxLifecycle.is_terminal(tb))

            finally:
                shutdown(ctx)


if __name__ == "__main__":
    unittest.main()
