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

    def test_challenge_jury_no_url_exits_2(self):
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "challenge-jury", "tt-any"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("JURY_UNAVAILABLE", result.stderr)


class TestThinkboxCLIJuryMocked(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._orig_dir = cli.EVIDENCE_DIR
        cli.EVIDENCE_DIR = os.path.join(self._tmpdir, "evidence")
        self._orig_db = cli.DB_PATH
        cli.DB_PATH = os.path.join(self._tmpdir, "test.db")

    def tearDown(self):
        cli.EVIDENCE_DIR = self._orig_dir
        cli.DB_PATH = self._orig_db

    def test_challenge_jury_no_url_exits_2(self):
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "challenge-jury", "tt-any"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("JURY_UNAVAILABLE", result.stderr)

    def test_challenge_jury_mocked_yes_via_cli(self):
        import subprocess
        # Create a token first
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "create"],
            capture_output=True, text=True,
        )
        tb_id = result.stdout.strip()

        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "exec", tb_id, "--", "echo", "hello"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)

        # Get token id
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "tokens", tb_id],
            capture_output=True, text=True,
        )
        token_id = json.loads(result.stdout.strip())["id"]

        # Test the store directly with mock
        import importlib
        import think_box_ai.cli as cli_mod
        importlib.reload(cli_mod)
        from core.memory.store import MemoryStore
        store = MemoryStore(cli_mod.DB_PATH)
        token_before = store.get_token(token_id)["s"]

        with unittest.mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = unittest.mock.MagicMock()
            mock_resp.read.return_value = json.dumps({
                "choices": [{"message": {"content": "YES"}}]
            }).encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = lambda s, *a: None
            mock_urlopen.return_value = mock_resp

            challenge_id = store.challenge_jury(token_id, "http://localhost:9999")

        self.assertIsNotNone(challenge_id)
        token_after = store.get_token(token_id)["s"]
        self.assertGreater(token_after, token_before)  # YES should increase score


if __name__ == "__main__":
    unittest.main()
