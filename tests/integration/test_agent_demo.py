"""Tests for the agent demo command."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest


class TestAgentDemo(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._env = os.environ.copy()
        self._env["THINKBOX_DB_PATH"] = os.path.join(self._tmpdir, "test.db")
        self._env["THINKBOX_EVIDENCE_DIR"] = os.path.join(self._tmpdir, "evidence")

    def _run(self, args):
        return subprocess.run(
            ["python3", "-m", "think_box_ai.cli"] + args,
            capture_output=True, text=True, env=self._env,
        )

    def test_create_returns_id(self):
        result = self._run(["create"])
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout.strip().startswith("tb-"))

    def test_exec_echoes_output(self):
        result = self._run(["create"])
        self.assertEqual(result.returncode, 0)
        tb_id = result.stdout.strip()

        result = self._run(["exec", tb_id, "--", "echo", "test_output"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("test_output", result.stdout)

    def test_agent_demo_full_flow(self):
        result = self._run(["agent", "echo hello_demo"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("KUDBEE", result.stdout)
        self.assertIn("Execution: ✓", result.stdout)
        self.assertIn("Think Token:", result.stdout)
        self.assertIn("Confidence:", result.stdout)

    def test_tokens_listed(self):
        result = self._run(["agent", "echo token_test"])
        self.assertIn("tb-", result.stdout)

        # Extract box ID from output
        for line in result.stdout.split("\n"):
            if "Think Box:" in line:
                tb_id = line.split(":")[-1].strip()
                break
        else:
            self.fail("Could not find Think Box ID")

        result = self._run(["tokens", tb_id])
        self.assertEqual(result.returncode, 0)
        self.assertIn("echo token_test", result.stdout)


if __name__ == "__main__":
    unittest.main()
