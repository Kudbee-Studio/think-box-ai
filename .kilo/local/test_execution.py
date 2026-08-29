"""Unit tests for core.execution — using unittest + stdlib mocks."""

from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

try:
    from core.execution import (
        ExecResult,
        ExecutionProviderRegistry,
        LocalExecProvider,
    )
    from core.execution.base import ExecutionUnavailableError
    from core.execution.firecracker import FirecrackerExecProvider
    from core.foundation.errors import ToolPermissionError
    from core.runtime.actor import Actor
except ModuleNotFoundError as exc:  # pragma: no cover
    ExecutionProviderRegistry = LocalExecProvider = FirecrackerExecProvider = None
    ExecResult = ExecutionUnavailableError = ToolPermissionError = Actor = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


def _run(coro):
    return asyncio.run(coro)


@unittest.skipIf(IMPORT_ERROR is not None, f"execution modules unavailable: {IMPORT_ERROR}")
class TestLocalExecProvider(unittest.TestCase):
    def test_real_echo_captures_stdout(self) -> None:
        provider = LocalExecProvider({})
        result = _run(provider.execute("echo hello-world"))
        self.assertEqual(result.return_code, 0)
        self.assertIn("hello-world", result.stdout)
        self.assertEqual(result.provider, "local")

    def test_stderr_and_return_code(self) -> None:
        provider = LocalExecProvider({})
        result = _run(provider.execute("sh -c 'echo out; echo err 1>&2; exit 7'"))
        self.assertEqual(result.return_code, 7)
        self.assertIn("out", result.stdout)
        self.assertIn("err", result.stderr)

    def test_empty_command_is_error(self) -> None:
        provider = LocalExecProvider({})
        result = _run(provider.execute(""))
        self.assertEqual(result.return_code, -1)
        self.assertIsNotNone(result.error)

    def test_timeout_terminates_process(self) -> None:
        provider = LocalExecProvider({})
        result = _run(provider.execute("sleep 5", timeout=0.3))
        self.assertEqual(result.return_code, -1)
        self.assertEqual(result.error, "timeout")

    def test_health_check_always_true(self) -> None:
        self.assertTrue(_run(LocalExecProvider({}).health_check()))

    def test_shutdown_noop(self) -> None:
        _run(LocalExecProvider({}).shutdown())


@unittest.skipIf(IMPORT_ERROR is not None, f"execution modules unavailable: {IMPORT_ERROR}")
class TestFirecrackerExecProviderUnit(unittest.TestCase):
    def _make_provider(self) -> "FirecrackerExecProvider":
        return FirecrackerExecProvider(
            {
                "firecracker_bin": "/usr/local/bin/firecracker",
                "kernel_image": "/srv/firecracker/vmlinux",
                "rootfs": "/srv/firecracker/rootfs.ext4",
            }
        )

    def test_health_false_without_real_kvm(self) -> None:
        provider = self._make_provider()
        with patch.object(FirecrackerExecProvider, "_real_kvm_device", return_value=False):
            self.assertFalse(_run(provider.health_check()))

    def test_execute_raises_when_unavailable(self) -> None:
        provider = self._make_provider()
        with patch.object(FirecrackerExecProvider, "_real_kvm_device", return_value=False):
            with self.assertRaises(ExecutionUnavailableError):
                _run(provider.execute("echo KUDBEE_FIRECRACKER_OK"))

    def test_execute_orchestrates_lifecycle_when_healthy(self) -> None:
        provider = self._make_provider()

        fake_vsock = MagicMock()
        fake_vsock.read_response.side_effect = [
            {"stream": "stdout", "data": "KUDBEE_FIRECRACKER_OK\n"},
            {"exit": 0},
        ]
        # Pretend kernel/rootfs/firecracker binaries exist on disk.
        real_exists = os.path.exists

        def fake_exists(path: str) -> bool:
            if path in (
                "/usr/local/bin/firecracker",
                "/srv/firecracker/vmlinux",
                "/srv/firecracker/rootfs.ext4",
            ):
                return True
            return real_exists(path)

        with patch.object(FirecrackerExecProvider, "_real_kvm_device", return_value=True), \
             patch("core.execution.firecracker._VsockClient.available", return_value=True), \
             patch.object(FirecrackerExecProvider, "_start_vmm", new=AsyncMock()) as m_start, \
             patch.object(FirecrackerExecProvider, "_configure", new=AsyncMock()) as m_cfg, \
             patch.object(FirecrackerExecProvider, "_boot", new=AsyncMock()) as m_boot, \
             patch.object(FirecrackerExecProvider, "_shutdown", new=AsyncMock()) as m_shut, \
             patch("core.execution.firecracker._VsockClient") as vsock_cls, \
             patch("core.execution.firecracker.os.path.exists", side_effect=fake_exists):

            vsock_cls.side_effect = lambda *a, **k: fake_vsock

            result = _run(provider.execute("echo KUDBEE_FIRECRACKER_OK", timeout=5.0))

        self.assertEqual(result.return_code, 0)
        self.assertIn("KUDBEE_FIRECRACKER_OK", result.stdout)
        self.assertEqual(result.provider, "firecracker")
        self.assertIsNotNone(result.microvm_id)
        m_start.assert_called_once()
        m_cfg.assert_called_once()
        m_boot.assert_called_once()
        m_shut.assert_called_once()


@unittest.skipIf(IMPORT_ERROR is not None, f"execution modules unavailable: {IMPORT_ERROR}")
class TestExecutionRegistry(unittest.TestCase):
    def test_register_and_get(self) -> None:
        self.assertIn("local", ExecutionProviderRegistry.list_providers())
        self.assertIn("firecracker", ExecutionProviderRegistry.list_providers())
        cls = ExecutionProviderRegistry.get("local")
        self.assertIsNotNone(cls)
        inst = ExecutionProviderRegistry.create("local")
        self.assertEqual(inst.name, "local")

    def test_unknown_provider_raises(self) -> None:
        with self.assertRaises(ExecutionUnavailableError):
            ExecutionProviderRegistry.create("does-not-exist")


@unittest.skipIf(IMPORT_ERROR is not None, f"execution modules unavailable: {IMPORT_ERROR}")
class TestActorExecutionRouting(unittest.TestCase):
    def _actor(self, provider) -> "Actor":
        return Actor(
            approval_gate=MagicMock(require_approval=MagicMock(return_value=False)),
            audit_log=MagicMock(record=MagicMock()),
            execution_provider=provider,
        )

    def test_execute_step_routes_to_provider(self) -> None:
        provider = LocalExecProvider({})
        actor = self._actor(provider)
        step = MagicMock()
        step.action = "execute"
        step.command = "echo routed-ok"
        step.id = "s1"
        step.description = "run"
        agent = MagicMock()
        agent.agent_id = "a1"
        agent.tool_registry = MagicMock()

        result = _run(actor.execute_step(agent, MagicMock(), step))
        self.assertEqual(result["status"], "success")
        self.assertIn("routed-ok", result["output"])

    def test_non_execute_step_not_routed(self) -> None:
        provider = LocalExecProvider({})
        actor = self._actor(provider)
        step = MagicMock()
        step.action = "plan"
        step.command = None
        step.description = "think"
        result = _run(actor.execute_step(MagicMock(), MagicMock(), step))
        self.assertIn("Executed step", result["output"])

    def test_approval_required_blocks_execution(self) -> None:
        provider = LocalExecProvider({})
        actor = self._actor(provider)
        actor.approval_gate.require_approval.return_value = True
        step = MagicMock()
        step.action = "execute"
        step.command = "echo nope"
        step.id = "s2"
        step.description = "run"
        agent = MagicMock()
        agent.agent_id = "a1"
        agent.tool_registry = MagicMock()
        with self.assertRaises(ToolPermissionError):
            _run(actor.execute_step(agent, MagicMock(), step))
