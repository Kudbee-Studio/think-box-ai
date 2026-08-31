"""Tests for core.runtime.harness — Docker-backed execution harness."""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from core.runtime.harness import HarnessConfig, HarnessLimits, HarnessRunner


def _docker_available() -> bool:
    """Check if Docker is available in this environment."""
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


DOCKER_AVAILABLE = _docker_available()
REQUIRES_DOCKER = unittest.skipUnless(DOCKER_AVAILABLE, "Docker not available")


class TestHarnessLimits(unittest.TestCase):
    def test_defaults(self) -> None:
        limits = HarnessLimits()
        self.assertEqual(limits.memory, "2g")
        self.assertEqual(limits.cpus, "1.0")
        self.assertEqual(limits.pids_limit, 0)
        self.assertFalse(limits.read_only_rootfs)

    def test_custom(self) -> None:
        limits = HarnessLimits(memory="4g", cpus="2.0", pids_limit=100, read_only_rootfs=True)
        self.assertEqual(limits.memory, "4g")
        self.assertEqual(limits.cpus, "2.0")
        self.assertEqual(limits.pids_limit, 100)
        self.assertTrue(limits.read_only_rootfs)


class TestHarnessConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        config = HarnessConfig()
        self.assertTrue(config.enabled)
        self.assertEqual(config.network_mode, "none")
        self.assertEqual(config.image, "ku3bee-harness:dev")
        self.assertIsInstance(config.limits, HarnessLimits)

    def test_custom(self) -> None:
        config = HarnessConfig(network_mode="bridge", image="custom:latest")
        self.assertEqual(config.network_mode, "bridge")
        self.assertEqual(config.image, "custom:latest")


class TestHarnessRunnerUnit(unittest.TestCase):
    def test_init_default(self) -> None:
        runner = HarnessRunner()
        self.assertIsInstance(runner.config, HarnessConfig)
        self.assertEqual(len(runner._containers), 0)

    def test_init_custom_config(self) -> None:
        config = HarnessConfig(network_mode="bridge")
        runner = HarnessRunner(config)
        self.assertEqual(runner.config.network_mode, "bridge")

    def test_list_containers_empty(self) -> None:
        runner = HarnessRunner()
        self.assertEqual(runner.list_containers(), [])

    def test_stop_container_unknown(self) -> None:
        runner = HarnessRunner()
        self.assertFalse(runner.stop_container("nonexistent"))


class TestHarnessRunnerMocked(unittest.TestCase):
    def test_start_container_success(self) -> None:
        runner = HarnessRunner()
        with patch.object(runner, "_docker") as mock_docker:
            mock_docker.return_value = MagicMock(returncode=0, stderr="")
            container = runner.start_container("test-agent")
            self.assertIsNotNone(container.container_id)
            self.assertTrue(container.container_name.startswith("ku3bee-test-agent-"))
            mock_docker.assert_called_once()

    def test_start_container_failure(self) -> None:
        runner = HarnessRunner()
        with patch.object(runner, "_docker") as mock_docker:
            mock_docker.return_value = MagicMock(returncode=1, stderr="docker error")
            with self.assertRaises(RuntimeError) as ctx:
                runner.start_container("test-agent")
            self.assertIn("Failed to start container", str(ctx.exception))

    def test_stop_container_releases_resources(self) -> None:
        runner = HarnessRunner()
        with patch.object(runner, "_docker") as mock_docker:
            mock_docker.return_value = MagicMock(returncode=0, stderr="")
            container = runner.start_container("test-agent")
            container_id = container.container_id
            self.assertEqual(len(runner.list_containers()), 1)
            result = runner.stop_container(container_id)
            self.assertTrue(result)
            self.assertEqual(len(runner.list_containers()), 0)
            self.assertEqual(mock_docker.call_count, 2)

    def test_stop_all(self) -> None:
        runner = HarnessRunner()
        with patch.object(runner, "_docker") as mock_docker:
            mock_docker.return_value = MagicMock(returncode=0, stderr="")
            c1 = runner.start_container("agent-1")
            c2 = runner.start_container("agent-2")
            self.assertEqual(len(runner.list_containers()), 2)
            runner.stop_all()
            self.assertEqual(len(runner.list_containers()), 0)

    def test_exec_in_container_unknown(self) -> None:
        runner = HarnessRunner()
        result = asyncio.run(
            runner.exec_in_container("nonexistent", ["echo", "hi"])
        )
        self.assertFalse(result["success"])
        self.assertIn("Unknown container", result["error"])

    def test_exec_in_container_success(self) -> None:
        runner = HarnessRunner()
        with patch.object(runner, "_docker") as mock_docker:
            mock_docker.return_value = MagicMock(returncode=0, stderr="")
            container = runner.start_container("test-agent")
            with patch("asyncio.create_subprocess_exec") as mock_exec:
                async def fake_communicate():
                    return (b"hello\n", b"")
                mock_proc = MagicMock()
                mock_proc.communicate = fake_communicate
                mock_proc.returncode = 0
                mock_exec.return_value = mock_proc
                result = asyncio.run(
                    runner.exec_in_container(container.container_id, ["echo", "hi"])
                )
                self.assertTrue(result["success"])
                self.assertEqual(result["return_code"], 0)


@REQUIRES_DOCKER
class TestHarnessRunnerIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = HarnessRunner()
        self._containers = []

    def tearDown(self) -> None:
        for cid in self._containers:
            self.runner.stop_container(cid)

    def test_container_starts_with_limits(self) -> None:
        container = self.runner.start_container(
            "test-agent",
            limits=HarnessLimits(memory="512m", cpus="0.5"),
        )
        self._containers.append(container.container_id)
        self.assertEqual(container.limits.memory, "512m")
        self.assertEqual(container.limits.cpus, "0.5")
        result = self.runner._docker("inspect", container.container_name)
        self.assertEqual(result.returncode, 0)

    def test_exec_runs_inside_container(self) -> None:
        container = self.runner.start_container("test-agent")
        self._containers.append(container.container_id)
        result = asyncio.run(
            self.runner.exec_in_container(
                container.container_id,
                ["hostname"],
                timeout=10,
            )
        )
        self.assertTrue(result["success"])
        hostname = result["stdout"].strip()
        self.assertTrue(len(hostname) > 0)
        self.assertNotEqual(hostname, os.uname().nodename)

    def test_network_isolation_default(self) -> None:
        container = self.runner.start_container("test-agent", network_mode="none")
        self._containers.append(container.container_id)
        result = asyncio.run(
            self.runner.exec_in_container(
                container.container_id,
                ["sh", "-c", "timeout 3 curl -s http://1.1.1.1 || echo NET_FAIL"],
                timeout=10,
            )
        )
        self.assertIn("NET_FAIL", result["stdout"])

    def test_filesystem_scope(self) -> None:
        container = self.runner.start_container("test-agent")
        self._containers.append(container.container_id)
        result = asyncio.run(
            self.runner.exec_in_container(
                container.container_id,
                ["sh", "-c", "echo test > /data/out.txt && cat /data/out.txt"],
                timeout=10,
            )
        )
        self.assertTrue(result["success"])
        self.assertIn("test", result["stdout"])
        result = asyncio.run(
            self.runner.exec_in_container(
                container.container_id,
                ["sh", "-c", "echo host > /host_write_test.txt 2>&1 || echo WRITE_BLOCKED"],
                timeout=10,
            )
        )
        self.assertIn("WRITE_BLOCKED", result["stdout"])

    def test_stop_releases_resources(self) -> None:
        container = self.runner.start_container("test-agent")
        container_id = container.container_id
        self.runner.stop_container(container_id)
        result = self.runner._docker("inspect", container.container_name)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
