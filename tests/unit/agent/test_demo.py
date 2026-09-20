"""Tests for agent control-plane demo (subprocess-safe, repair #4)."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from thinkbox.agent.control_plane.receipt import ActionReceipt


class TestAgentControlPlaneDemoSubprocess(unittest.TestCase):
    """Demo must run in a fresh interpreter; parent must stay unpolluted."""

    def test_import_does_not_inject_demo_stubs(self) -> None:
        before_grpc = sys.modules.get("grpc")
        before_proto = sys.modules.get("thinkbox.agent.protocol")

        import thinkbox.agent.control_plane.demo as demo_module  # noqa: F401

        self.assertTrue(hasattr(demo_module, "demo"))
        after_grpc = sys.modules.get("grpc")
        after_proto = sys.modules.get("thinkbox.agent.protocol")
        self.assertIs(after_grpc, before_grpc)
        self.assertIs(after_proto, before_proto)

    def test_receipt_module_real_after_demo_import(self) -> None:
        import thinkbox.agent.control_plane.demo  # noqa: F401

        receipt = ActionReceipt("CAPACITY", "a1", "OK")
        self.assertEqual(receipt.action_type, "CAPACITY")

    def test_module_main_exit_zero_subprocess(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "thinkbox.agent.control_plane.demo"],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertIn("Demo complete — all 6 phases green.", proc.stdout)
        self.assertIn("Admit AGENT_SPAWN: True", proc.stdout)

    def test_demo_script_runs_subprocess(self) -> None:
        path = Path("scripts/demo_in_10_agent_control_plane.sh")
        self.assertTrue(path.exists())
        self.assertTrue(path.stat().st_mode & 0o111)
        proc = subprocess.run(
            ["bash", str(path)],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertIn("Subprocess demo complete", proc.stdout)

    def test_subprocess_parent_unpolluted_after_demo_run(self) -> None:
        before_grpc = sys.modules.get("grpc")
        proc = subprocess.run(
            [sys.executable, "-m", "thinkbox.agent.control_plane.demo"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIs(sys.modules.get("grpc"), before_grpc)
        receipt = ActionReceipt("SECRET", "a2", "OK")
        self.assertEqual(receipt.status, "OK")


if __name__ == "__main__":
    unittest.main()
