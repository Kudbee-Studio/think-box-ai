"""Integration tests for runtime wiring and secrets resolver.

These tests verify the runtime components work together:
- Planner generates meaningful steps with a mock Provider
- Actor invokes registered tools and checks permissions
- Agent.run() executes the full loop with mock provider + tools
- Runtime works without a provider (backward compatibility)
- SecretResolver resolves env vars correctly
"""

from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from core.foundation.errors import ToolApprovalRequiredError
from core.foundation.secrets import SecretResolver, SecretResolutionError
from core.governance.audit import ApprovalGate, AuditLog, PermissionChecker, PermissionLevel
from core.providers.base import CompletionResponse, Message, ProviderCapabilities
from core.runtime.actor import Actor
from core.runtime.agent import Agent, Goal, ThinkBox
from core.runtime.observer import Observer
from core.runtime.planner import Planner, Step
from core.runtime.thinkbox import ThinkBoxLifecycle
from core.tools.registry import ToolDefinition, ToolRegistry


def _make_mock_provider(response_content: str) -> AsyncMock:
    """Create a mock provider that returns the given response content."""
    provider = AsyncMock()
    provider.capabilities = ProviderCapabilities()
    provider.complete = AsyncMock(
        return_value=CompletionResponse(
            content=response_content,
            model="mock-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )
    )
    return provider


class TestPlannerWithMockProvider(unittest.TestCase):
    """Test Planner generates meaningful steps when a mock Provider is available."""

    def test_planner_parses_json_steps_from_provider(self) -> None:
        json_response = (
            '[{"id": "step-1", "description": "Read the config file", '
            '"action": "file_read", "parameters": {"path": "/etc/config.json"}}, '
            '{"id": "step-2", "description": "Write output", '
            '"action": "file_write", "parameters": {"path": "/tmp/out.txt"}}]'
        )
        provider = _make_mock_provider(json_response)
        planner = Planner(task_memory=MagicMock(), provider=provider)

        goal = Goal(statement="Process configuration")
        tb = ThinkBox(goal=goal)
        steps = planner.plan(tb)

        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0].id, "step-1")
        self.assertEqual(steps[0].description, "Read the config file")
        self.assertEqual(steps[0].action, "file_read")
        self.assertEqual(steps[0].parameters, {"path": "/etc/config.json"})
        self.assertEqual(steps[1].id, "step-2")
        self.assertEqual(steps[1].action, "file_write")

    def test_planner_falls_back_to_placeholder_on_provider_error(self) -> None:
        provider = AsyncMock()
        provider.capabilities = ProviderCapabilities()
        provider.complete = AsyncMock(side_effect=Exception("Connection refused"))
        planner = Planner(task_memory=MagicMock(), provider=provider)

        goal = Goal(statement="Test goal")
        tb = ThinkBox(goal=goal)
        steps = planner.plan(tb)

        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].id, "step-1")
        self.assertIn("Test goal", steps[0].description)

    def test_planner_falls_back_to_placeholder_on_invalid_json(self) -> None:
        provider = _make_mock_provider("This is not JSON at all")
        planner = Planner(task_memory=MagicMock(), provider=provider)

        goal = Goal(statement="Parse this")
        tb = ThinkBox(goal=goal)
        steps = planner.plan(tb)

        self.assertGreater(len(steps), 0)
        for step in steps:
            self.assertIsInstance(step, Step)
            self.assertNotEqual(step.id, "")

    def test_planner_with_provider_in_running_loop_uses_placeholder(self) -> None:
        """When called inside a running loop, planner falls back to placeholder.

        This documents the current behavior where asyncio.get_running_loop()
        succeeds and the provider branch is skipped.
        """
        provider = _make_mock_provider(
            '[{"id": "s1", "description": "Should not appear", "action": "noop"}]'
        )
        planner = Planner(task_memory=MagicMock(), provider=provider)

        async def _run() -> list[Step]:
            goal = Goal(statement="Inside running loop")
            tb = ThinkBox(goal=goal)
            return planner.plan(tb)

        steps = asyncio.run(_run())

        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].id, "step-1")
        self.assertIn("Inside running loop", steps[0].description)


class TestActorWithToolsAndPermissions(unittest.TestCase):
    """Test Actor correctly invokes registered tools and checks permissions."""

    def test_actor_executes_registered_tool(self) -> None:
        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)

        def echo_handler(params: dict) -> dict:
            return {"status": "success", "output": params.get("message", "")}

        registry.register(ToolDefinition(
            name="echo",
            description="Echoes input",
            handler=echo_handler,
            permission=PermissionLevel.READ_ONLY,
        ))

        checker = PermissionChecker(policy=__import__("core.governance.audit", fromlist=["ApprovalPolicy"]).ApprovalPolicy.AUTO_APPROVE_ALL)
        gate = ApprovalGate(checker, audit)
        actor = Actor(tool_registry=registry, approval_gate=gate, audit_log=audit)

        agent = Agent(agent_id="test-agent", tool_registry=registry, approval_gate=gate, audit_log=audit)
        tb = ThinkBox(goal=Goal(statement="test"))
        step = Step(id="s1", description="Echo test", action="echo", parameters={"message": "hello"})

        result = asyncio.run(actor.execute_step(agent, tb, step))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["output"], "hello")

    def test_actor_raises_approval_required_for_restricted_tool(self) -> None:
        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)

        def dangerous_handler(params: dict) -> dict:
            return {"status": "success"}

        registry.register(ToolDefinition(
            name="dangerous",
            description="Requires approval",
            handler=dangerous_handler,
            permission=PermissionLevel.RESTRICTED,
        ))

        checker = PermissionChecker(policy=__import__("core.governance.audit", fromlist=["ApprovalPolicy"]).ApprovalPolicy.MANUAL)
        gate = ApprovalGate(checker, audit)
        actor = Actor(tool_registry=registry, approval_gate=gate, audit_log=audit)

        agent = Agent(agent_id="test-agent", tool_registry=registry, approval_gate=gate, audit_log=audit)
        tb = ThinkBox(goal=Goal(statement="test"))
        step = Step(id="s1", description="Do dangerous thing", action="dangerous")

        with self.assertRaises(ToolApprovalRequiredError):
            asyncio.run(actor.execute_step(agent, tb, step))

    def test_actor_handles_async_tool_handler(self) -> None:
        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)

        async def async_echo(params: dict) -> dict:
            return {"status": "success", "output": params.get("value", "")}

        registry.register(ToolDefinition(
            name="async_echo",
            description="Async echo",
            handler=async_echo,
            permission=PermissionLevel.READ_ONLY,
        ))

        checker = PermissionChecker(policy=__import__("core.governance.audit", fromlist=["ApprovalPolicy"]).ApprovalPolicy.AUTO_APPROVE_ALL)
        gate = ApprovalGate(checker, audit)
        actor = Actor(tool_registry=registry, approval_gate=gate, audit_log=audit)

        agent = Agent(agent_id="test-agent", tool_registry=registry, approval_gate=gate, audit_log=audit)
        tb = ThinkBox(goal=Goal(statement="test"))
        step = Step(id="s1", description="Async echo", action="async_echo", parameters={"value": "async_result"})

        result = asyncio.run(actor.execute_step(agent, tb, step))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["output"], "async_result")

    def test_actor_returns_success_for_unknown_action(self) -> None:
        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)

        checker = PermissionChecker(policy=__import__("core.governance.audit", fromlist=["ApprovalPolicy"]).ApprovalPolicy.AUTO_APPROVE_ALL)
        gate = ApprovalGate(checker, audit)
        actor = Actor(tool_registry=registry, approval_gate=gate, audit_log=audit)

        agent = Agent(agent_id="test-agent", tool_registry=registry, approval_gate=gate, audit_log=audit)
        tb = ThinkBox(goal=Goal(statement="test"))
        step = Step(id="s1", description="Unknown action", action="nonexistent_tool")

        result = asyncio.run(actor.execute_step(agent, tb, step))

        self.assertEqual(result["status"], "success")
        self.assertIn("Unknown action", result["output"])

    def test_actor_returns_success_when_no_tools_available(self) -> None:
        actor = Actor(tool_registry=None)
        agent = Agent(agent_id="test-agent")
        tb = ThinkBox(goal=Goal(statement="test"))
        step = Step(id="s1", description="No tools", action="anything")

        result = asyncio.run(actor.execute_step(agent, tb, step))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["output"], "No tools available")

    def test_actor_records_audit_on_success(self) -> None:
        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)

        def simple_handler(params: dict) -> dict:
            return {"status": "success", "output": "done"}

        registry.register(ToolDefinition(
            name="simple",
            description="Simple tool",
            handler=simple_handler,
            permission=PermissionLevel.READ_ONLY,
        ))

        checker = PermissionChecker(policy=__import__("core.governance.audit", fromlist=["ApprovalPolicy"]).ApprovalPolicy.AUTO_APPROVE_ALL)
        gate = ApprovalGate(checker, audit)
        actor = Actor(tool_registry=registry, approval_gate=gate, audit_log=audit)

        agent = Agent(agent_id="audit-agent", tool_registry=registry, approval_gate=gate, audit_log=audit)
        tb = ThinkBox(goal=Goal(statement="test"))
        step = Step(id="s1", description="Simple", action="simple")

        asyncio.run(actor.execute_step(agent, tb, step))

        entries = audit.list_entries()
        success_entries = [e for e in entries if e["outcome"] == "success"]
        self.assertGreater(len(success_entries), 0)
        self.assertEqual(success_entries[0]["actor"], "audit-agent")

    def test_actor_records_audit_on_error(self) -> None:
        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)

        def failing_handler(params: dict) -> dict:
            raise RuntimeError("Tool failed!")

        registry.register(ToolDefinition(
            name="failing",
            description="Failing tool",
            handler=failing_handler,
            permission=PermissionLevel.READ_ONLY,
        ))

        checker = PermissionChecker(policy=__import__("core.governance.audit", fromlist=["ApprovalPolicy"]).ApprovalPolicy.AUTO_APPROVE_ALL)
        gate = ApprovalGate(checker, audit)
        actor = Actor(tool_registry=registry, approval_gate=gate, audit_log=audit)

        agent = Agent(agent_id="error-agent", tool_registry=registry, approval_gate=gate, audit_log=audit)
        tb = ThinkBox(goal=Goal(statement="test"))
        step = Step(id="s1", description="Failing", action="failing")

        result = asyncio.run(actor.execute_step(agent, tb, step))

        self.assertEqual(result["status"], "error")
        entries = audit.list_entries()
        error_entries = [e for e in entries if e["outcome"] == "error"]
        self.assertGreater(len(error_entries), 0)


class TestAgentRunFullLoop(unittest.TestCase):
    """Test Agent.run() with mock provider + tools executes the full loop."""

    def test_full_loop_with_mock_provider_and_tools(self) -> None:
        json_response = (
            '[{"id": "step-1", "description": "Echo hello", '
            '"action": "echo", "parameters": {"message": "hello"}}, '
            '{"id": "step-2", "description": "Echo world", '
            '"action": "echo", "parameters": {"message": "world"}}]'
        )
        provider = _make_mock_provider(json_response)

        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)

        def echo_handler(params: dict) -> dict:
            return {"status": "success", "output": params.get("message", "")}

        registry.register(ToolDefinition(
            name="echo",
            description="Echoes input",
            handler=echo_handler,
            permission=PermissionLevel.READ_ONLY,
        ))

        checker = PermissionChecker(policy=__import__("core.governance.audit", fromlist=["ApprovalPolicy"]).ApprovalPolicy.AUTO_APPROVE_ALL)
        gate = ApprovalGate(checker, audit)

        agent = Agent(
            agent_id="loop-agent",
            tool_registry=registry,
            approval_gate=gate,
            audit_log=audit,
            provider=provider,
        )

        goal = Goal(statement="Run echo loop", success_criteria=["done"])
        result = asyncio.run(agent.run(goal))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["think_box"].state.value, "complete")

    def test_full_loop_with_observer_validation(self) -> None:
        json_response = (
            '[{"id": "step-1", "description": "Do something", '
            '"action": "noop", "expected_output": {"status": "success"}}]'
        )
        provider = _make_mock_provider(json_response)

        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)
        checker = PermissionChecker(policy=__import__("core.governance.audit", fromlist=["ApprovalPolicy"]).ApprovalPolicy.AUTO_APPROVE_ALL)
        gate = ApprovalGate(checker, audit)

        agent = Agent(
            agent_id="obs-agent",
            tool_registry=registry,
            approval_gate=gate,
            audit_log=audit,
            provider=provider,
        )

        observer = Observer()
        goal = Goal(statement="Test with observer")
        result = asyncio.run(agent.run(goal, observer=observer))

        self.assertEqual(result["status"], "success")

    def test_full_loop_fails_when_observer_rejects(self) -> None:
        json_response = (
            '[{"id": "step-1", "description": "Will fail validation", '
            '"action": "noop", "expected_output": {"status": "success"}}]'
        )
        provider = _make_mock_provider(json_response)

        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)
        checker = PermissionChecker(policy=__import__("core.governance.audit", fromlist=["ApprovalPolicy"]).ApprovalPolicy.AUTO_APPROVE_ALL)
        gate = ApprovalGate(checker, audit)

        agent = Agent(
            agent_id="fail-agent",
            tool_registry=registry,
            approval_gate=gate,
            audit_log=audit,
            provider=provider,
        )

        observer = MagicMock()
        observer.validate.return_value = False

        goal = Goal(statement="Will fail")
        result = asyncio.run(agent.run(goal, observer=observer))

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["think_box"].state.value, "failed")


class TestRuntimeWithoutProvider(unittest.TestCase):
    """Test that runtime works without a provider (backward compatibility)."""

    def test_agent_run_without_provider(self) -> None:
        agent = Agent(agent_id="no-provider-agent")
        goal = Goal(statement="No provider goal")

        result = asyncio.run(agent.run(goal))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["think_box"].state.value, "complete")

    def test_planner_without_provider_returns_placeholder(self) -> None:
        planner = Planner(task_memory=MagicMock(), provider=None)

        goal = Goal(statement="No provider planning")
        tb = ThinkBox(goal=goal)
        steps = planner.plan(tb)

        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].id, "step-1")
        self.assertIn("No provider planning", steps[0].description)
        self.assertEqual(steps[0].action, "execute")

    def test_agent_run_with_explicit_planner_no_provider(self) -> None:
        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)

        def echo_handler(params: dict) -> dict:
            return {"status": "success", "output": "ok"}

        registry.register(ToolDefinition(
            name="echo",
            description="Echo",
            handler=echo_handler,
            permission=PermissionLevel.READ_ONLY,
        ))

        checker = PermissionChecker(policy=__import__("core.governance.audit", fromlist=["ApprovalPolicy"]).ApprovalPolicy.AUTO_APPROVE_ALL)
        gate = ApprovalGate(checker, audit)

        agent = Agent(
            agent_id="explicit-planner-agent",
            tool_registry=registry,
            approval_gate=gate,
            audit_log=audit,
            provider=None,
        )

        planner = Planner(task_memory=MagicMock(), provider=None)
        actor = Actor(tool_registry=registry, approval_gate=gate, audit_log=audit)

        goal = Goal(statement="Explicit planner test")
        result = asyncio.run(agent.run(goal, planner=planner, actor=actor))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["think_box"].state.value, "complete")


class TestSecretResolverIntegration(unittest.TestCase):
    """Test SecretResolver resolves env vars correctly.

    Integration tests verify the resolver works with the actual
    THINKBOX_ environment variable prefix from config.
    """

    def test_resolve_from_env_with_thinkbox_prefix(self) -> None:
        os.environ["THINKBOX_INTEGRATION_TEST_KEY"] = "integration_value"
        try:
            resolver = SecretResolver()
            result = resolver.resolve("INTEGRATION_TEST_KEY")
            self.assertEqual(result, "integration_value")
        finally:
            del os.environ["THINKBOX_INTEGRATION_TEST_KEY"]

    def test_resolve_uses_correct_prefix_format(self) -> None:
        """Verify the env var key is THINKBOX_{KEY} format."""
        os.environ["THINKBOX_API_SECRET"] = "secret123"
        try:
            resolver = SecretResolver()
            self.assertEqual(resolver.resolve("API_SECRET"), "secret123")
        finally:
            del os.environ["THINKBOX_API_SECRET"]

    def test_resolve_required_raises_with_helpful_message(self) -> None:
        resolver = SecretResolver()
        with self.assertRaises(SecretResolutionError) as ctx:
            resolver.resolve_required("TOTALLY_NONEXISTENT_SECRET_XYZ")
        self.assertIn("THINKBOX_TOTALLY_NONEXISTENT_SECRET_XYZ", str(ctx.exception))
        self.assertEqual(ctx.exception.key, "TOTALLY_NONEXISTENT_SECRET_XYZ")

    def test_resolve_env_takes_precedence_over_default(self) -> None:
        os.environ["THINKBOX_PRECEDENCE_TEST"] = "from_env"
        try:
            resolver = SecretResolver(defaults={"PRECEDENCE_TEST": "from_default"})
            self.assertEqual(resolver.resolve("PRECEDENCE_TEST"), "from_env")
        finally:
            del os.environ["THINKBOX_PRECEDENCE_TEST"]

    def test_resolve_returns_default_when_env_not_set(self) -> None:
        resolver = SecretResolver(defaults={"DEFAULT_ONLY_KEY": "default_val"})
        self.assertEqual(resolver.resolve("DEFAULT_ONLY_KEY"), "default_val")

    def test_resolve_returns_none_for_completely_missing_key(self) -> None:
        resolver = SecretResolver()
        self.assertIsNone(resolver.resolve("COMPLETELY_MISSING_KEY_ABCXYZ"))

    def test_is_set_reflects_env_availability(self) -> None:
        os.environ["THINKBOX_IS_SET_TEST"] = "present"
        try:
            resolver = SecretResolver()
            self.assertTrue(resolver.is_set("IS_SET_TEST"))
        finally:
            del os.environ["THINKBOX_IS_SET_TEST"]

        resolver = SecretResolver()
        self.assertFalse(resolver.is_set("IS_SET_TEST"))

    def test_resolve_required_with_default_value(self) -> None:
        resolver = SecretResolver(defaults={"REQUIRED_WITH_DEFAULT": "my_secret"})
        self.assertEqual(resolver.resolve_required("REQUIRED_WITH_DEFAULT"), "my_secret")

    def test_multiple_secrets_with_defaults(self) -> None:
        resolver = SecretResolver(defaults={
            "KEY_A": "value_a",
            "KEY_B": "value_b",
        })
        self.assertEqual(resolver.resolve("KEY_A"), "value_a")
        self.assertEqual(resolver.resolve("KEY_B"), "value_b")
        self.assertIsNone(resolver.resolve("KEY_C"))

    def test_secret_not_cached_in_instance(self) -> None:
        """Verify secrets are read from env on each access, not cached."""
        os.environ["THINKBOX_DYNAMIC_KEY"] = "first"
        try:
            resolver = SecretResolver()
            self.assertEqual(resolver.resolve("DYNAMIC_KEY"), "first")

            os.environ["THINKBOX_DYNAMIC_KEY"] = "second"
            self.assertEqual(resolver.resolve("DYNAMIC_KEY"), "second")
        finally:
            del os.environ["THINKBOX_DYNAMIC_KEY"]


if __name__ == "__main__":
    unittest.main()
