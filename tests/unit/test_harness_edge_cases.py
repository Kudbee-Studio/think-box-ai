"""Tests for harness edge cases — timeout, concurrency, cleanup."""

from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import MagicMock, patch

from core.runtime.harness import HarnessConfig, HarnessLimits, HarnessRunner


class TestHarnessTimeout(unittest.TestCase):
    def test_exec_timeout_returns_error(self) -> None:
        runner = HarnessRunner()
        with patch.object(runner, "_docker") as mock_docker:
            mock_docker.return_value = MagicMock(returncode=0, stderr="")
            container = runner.start_container("timeout-test")

            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_proc = MagicMock()

                async def slow_communicate():
                    await asyncio.sleep(10)
                    return (b"", b"")

                mock_proc.communicate = slow_communicate
                mock_proc.returncode = 0
                mock_exec.return_value = mock_proc

                result = asyncio.run(
                    runner.exec_in_container(
                        container.container_id, ["sleep", "60"], timeout=1
                    )
                )
                self.assertFalse(result["success"])


class TestHarnessConcurrency(unittest.TestCase):
    def test_multiple_agents_isolated(self) -> None:
        runner = HarnessRunner()
        containers = []

        with patch.object(runner, "_docker") as mock_docker:
            mock_docker.return_value = MagicMock(returncode=0, stderr="")

            for i in range(5):
                c = runner.start_container(f"agent-{i}")
                containers.append(c.container_id)

            self.assertEqual(len(runner.list_containers()), 5)

            for cid in containers[:3]:
                runner.stop_container(cid)

            self.assertEqual(len(runner.list_containers()), 2)


class TestHarnessContainerNaming(unittest.TestCase):
    def test_naming_format(self) -> None:
        runner = HarnessRunner()
        with patch.object(runner, "_docker") as mock_docker:
            mock_docker.return_value = MagicMock(returncode=0, stderr="")

            c = runner.start_container("mytoken123")
            self.assertRegex(
                c.container_name, r"^ku3bee-mytoken123-[a-f0-9-]+$"
            )

    def test_unique_ids(self) -> None:
        runner = HarnessRunner()
        with patch.object(runner, "_docker") as mock_docker:
            mock_docker.return_value = MagicMock(returncode=0, stderr="")

            c1 = runner.start_container("agent-1")
            c2 = runner.start_container("agent-1")

            self.assertNotEqual(c1.container_id, c2.container_id)


class TestHarnessCleanup(unittest.TestCase):
    def test_stop_unknown_container(self) -> None:
        runner = HarnessRunner()
        result = runner.stop_container("nonexistent-id")
        self.assertFalse(result)

    def test_double_stop(self) -> None:
        runner = HarnessRunner()
        with patch.object(runner, "_docker") as mock_docker:
            mock_docker.return_value = MagicMock(returncode=0, stderr="")
            c = runner.start_container("double-stop")

            r1 = runner.stop_container(c.container_id)
            r2 = runner.stop_container(c.container_id)

            self.assertTrue(r1)
            self.assertFalse(r2)


class TestHarnessNetworkModes(unittest.TestCase):
    def test_default_network_is_none(self) -> None:
        config = HarnessConfig()
        self.assertEqual(config.network_mode, "none")

    def test_bridge_network_mode(self) -> None:
        config = HarnessConfig(network_mode="bridge")
        runner = HarnessRunner(config)

        with patch.object(runner, "_docker") as mock_docker:
            mock_docker.return_value = MagicMock(returncode=0, stderr="")
            c = runner.start_container("net-test")
            self.assertEqual(c.network_mode, "bridge")


class TestHarnessLimitsEdgeCases(unittest.TestCase):
    def test_zero_pids_limit(self) -> None:
        limits = HarnessLimits(pids_limit=0)
        self.assertEqual(limits.pids_limit, 0)

    def test_large_memory(self) -> None:
        limits = HarnessLimits(memory="128g")
        self.assertEqual(limits.memory, "128g")

    def test_fractional_cpu(self) -> None:
        limits = HarnessLimits(cpus="0.25")
        self.assertEqual(limits.cpus, "0.25")


class TestHarnessConfigDefaults(unittest.TestCase):
    def test_workdir_root_empty_by_default(self) -> None:
        config = HarnessConfig()
        self.assertEqual(config.workdir_root, "")

    def test_backend_is_docker(self) -> None:
        from core.runtime.harness import SandboxBackend

        config = HarnessConfig()
        self.assertEqual(config.backend, SandboxBackend.DOCKER)


if __name__ == "__main__":
    unittest.main()
