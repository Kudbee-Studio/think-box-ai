"""CLI tests for thinkbox create/exec/evidence."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from think_box_ai import cli


class TestThinkboxCLI(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._orig_dir = cli.EVIDENCE_DIR
        cli.EVIDENCE_DIR = os.path.join(self._tmpdir, "evidence")

    def tearDown(self):
        cli.EVIDENCE_DIR = self._orig_dir

    def test_create_returns_id(self):
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "create"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout.strip().startswith("tb-"))

    def test_exec_echoes_output(self):
        import subprocess
        # Create a Think Box
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "create"],
            capture_output=True, text=True,
        )
        tb_id = result.stdout.strip()

        # Execute echo
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "exec", tb_id, "--", "echo", "KUDBEE_LOCAL_OK"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("KUDBEE_LOCAL_OK", result.stdout)

    def test_evidence_shows_ok(self):
        import subprocess
        # Create + exec
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "create"],
            capture_output=True, text=True,
        )
        tb_id = result.stdout.strip()

        subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "exec", tb_id, "--", "echo", "KUDBEE_LOCAL_OK"],
            capture_output=True, text=True,
        )

        # Check evidence
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "evidence", tb_id],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout.strip())
        self.assertEqual(data["ok"], True)
        self.assertEqual(data["exit_code"], 0)
        self.assertEqual(data["provider"], "local")

    def test_bogus_id_returns_error(self):
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "evidence", "tb-nonexistent"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no evidence", result.stderr)


if __name__ == "__main__":
    unittest.main()
