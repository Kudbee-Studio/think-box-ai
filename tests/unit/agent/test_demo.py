"""Tests for Demo-in-10 (commit 10: demo-in-60s)."""

import subprocess
import sys
import unittest
from pathlib import Path


class TestDemo(unittest.TestCase):

    def test_demo_imports(self):
        from thinkbox.agent.control_plane import demo as demo_module

        self.assertTrue(hasattr(demo_module, "main"))

    def test_demo_runs(self):
        """Demo should run as a module without importing grpc/protobuf."""
        result = subprocess.run(
            [sys.executable, "-m", "thinkbox.agent.control_plane.demo"],
            cwd=str(Path(__file__).resolve().parents[3]),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Demo complete", result.stdout)


if __name__ == "__main__":
    unittest.main()
