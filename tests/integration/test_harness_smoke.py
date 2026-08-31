"""Smoke test for the ku3bee-harness Docker sandbox.

Exercises the full isolation contract:
  1. Build/assume image ku3bee-harness:dev
  2. Start a container via the harness
  3. Run `pwd` and `id` inside -> must show /data and non-root
  4. Run `touch /data/ok.txt` -> file appears only in the work mount
  5. Run `touch /etc/pwned` -> must fail
  6. Run something dangerous -> must not mutate host
  7. After stop, container is removed
  8. With HARNESS=0, old shell_exec still works (host fallback)

If Docker is missing, the whole module skips with a clear message.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from core.foundation.logging import setup_logging
from core.runtime.harness import HarnessConfig, HarnessRunner, docker_available
from core.tools.shell_exec import _harness_enabled, shell_exec_async

setup_logging("WARNING")

DOCKER_AVAILABLE = docker_available()
REQUIRES_DOCKER = unittest.skipUnless(DOCKER_AVAILABLE, "Docker not available in this environment")


def _ensure_image() -> bool:
    """Ensure ku3bee-harness:dev image exists; build from repo root if needed."""
    result = subprocess.run(
        ["docker", "inspect", "ku3bee-harness:dev"],
        capture_output=True, timeout=10,
    )
    if result.returncode == 0:
        return True
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    dockerfile = os.path.join(repo_root, "Dockerfile")
    if not os.path.exists(dockerfile):
        return False
    result = subprocess.run(
        ["docker", "build", "-t", "ku3bee-harness:dev", "-f", dockerfile, repo_root],
        capture_output=True, timeout=120,
    )
    return result.returncode == 0


@REQUIRES_DOCKER
class TestHarnessSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not _ensure_image():
            raise unittest.SkipTest("Cannot build/verify ku3bee-harness:dev image")
        cls.runner = HarnessRunner(HarnessConfig())
        cls._container = cls.runner.start_container(agent_id="smoke")
        print(f"\n[smoke] started container: {cls._container.container_name} ({cls._container.container_id})")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.runner.stop_all()
        print("[smoke] stopped all containers")

    def _exec(self, cmd: str, timeout: int = 10) -> dict:
        return asyncio.run(
            self.runner.exec_in_container(self._container.container_id, ["sh", "-c", cmd], timeout=timeout)
        )

    def test_01_pwd_shows_data(self) -> None:
        result = self._exec("pwd")
        self.assertTrue(result["success"], f"pwd failed: {result}")
        self.assertEqual(result["stdout"].strip(), "/data")
        print("PASS: pwd shows /data")

    def test_02_id_shows_non_root(self) -> None:
        result = self._exec("id -u")
        self.assertTrue(result["success"], f"id failed: {result}")
        uid = result["stdout"].strip()
        self.assertNotEqual(uid, "0", "Running inside container as root — expected non-root")
        print(f"PASS: id shows non-root (uid={uid})")

    def test_03_touch_in_data_mount(self) -> None:
        result = self._exec("touch /data/ok.txt && ls -la /data/ok.txt")
        self.assertTrue(result["success"], f"touch failed: {result}")
        self.assertTrue(os.path.exists(os.path.join(self._container.workdir, "ok.txt")))
        print("PASS: touch /data/ok.txt appeared in work mount")

    def test_04_touch_etc_pwned_fails(self) -> None:
        result = self._exec("touch /etc/pwned 2>&1")
        self.assertFalse(result["success"], "touch /etc/pwned should have failed under non-root user")
        print("PASS: touch /etc/pwned correctly failed")

    def test_05_does_not_mutate_host(self) -> None:
        marker = "HARNESS_SMOKE_MARKER_7f3a"
        result = self._exec(f"echo {marker} > /home/evil.txt 2>&1; echo RC=$?")
        self.assertTrue(result["success"] or "Permission denied" in result.get("stderr", ""),
                        f"Unexpected result: {result}")
        host_home = os.path.expanduser("~")
        self.assertFalse(os.path.exists(os.path.join(host_home, "evil.txt")),
                         "Container wrote to host HOME — isolation breach!")
        print("PASS: dangerous write did not mutate host home")

    def test_06_stop_releases_container(self) -> None:
        runner = HarnessRunner(HarnessConfig())
        container = runner.start_container(agent_id="smoke-stop")
        cid = container.container_id
        self.assertEqual(len(runner.list_containers()), 1)
        runner.stop_container(cid)
        self.assertEqual(len(runner.list_containers()), 0)
        check = subprocess.run(
            ["docker", "inspect", container.container_name],
            capture_output=True, timeout=10,
        )
        self.assertNotEqual(check.returncode, 0, "Container still exists after stop")
        print("PASS: stop removes container")


class TestHarnessFallback(unittest.TestCase):
    """Verify HARNESS=0 falls back to host subprocess."""

    def test_shell_exec_host_fallback(self) -> None:
        os.environ["HARNESS"] = "0"
        try:
            result = asyncio.run(shell_exec_async({"command": "echo host_fallback_working", "timeout": 10}))
            self.assertTrue(result["success"], f"Host fallback failed: {result}")
            self.assertIn("host_fallback_working", result["stdout"])
            print("PASS: HARNESS=0 host fallback works for shell_exec")
        finally:
            del os.environ["HARNESS"]


class TestHarnessDefaultFlag(unittest.TestCase):
    """Verify HARNESS env var drives _harness_enabled()."""

    def test_harness_1_enables(self) -> None:
        os.environ["HARNESS"] = "1"
        try:
            self.assertTrue(_harness_enabled())
            print("PASS: HARNESS=1 enables harness")
        finally:
            del os.environ["HARNESS"]

    def test_harness_0_disables(self) -> None:
        os.environ["HARNESS"] = "0"
        try:
            self.assertFalse(_harness_enabled())
            print("PASS: HARNESS=0 disables harness")
        finally:
            del os.environ["HARNESS"]


if __name__ == "__main__":
    unittest.main(verbosity=2)
