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

    def test_list_shows_boxes(self):
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "create"],
            capture_output=True, text=True,
        )
        tb_id = result.stdout.strip()
        subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "exec", tb_id, "--", "echo", "hi"],
            capture_output=True, text=True,
        )

        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "list"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(tb_id, result.stdout)

    def test_status_shows_tokens(self):
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "create"],
            capture_output=True, text=True,
        )
        tb_id = result.stdout.strip()
        subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "exec", tb_id, "--", "echo", "hi"],
            capture_output=True, text=True,
        )

        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "status", tb_id],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout.strip())
        self.assertEqual(data["box_id"], tb_id)
        self.assertGreaterEqual(data["token_count"], 1)

    def test_status_bogus_id_returns_error(self):
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "status", "tb-bogus"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_full_workflow(self):
        """Test the complete workflow: create -> exec -> evidence -> tokens -> score."""
        import subprocess

        # Create
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "create"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        tb_id = result.stdout.strip()
        self.assertTrue(tb_id.startswith("tb-"))

        # Exec
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "exec", tb_id, "--", "echo", "workflow_test"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("workflow_test", result.stdout)

        # Evidence
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "evidence", tb_id],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        evidence = json.loads(result.stdout.strip())
        self.assertEqual(evidence["ok"], True)
        self.assertEqual(evidence["exit_code"], 0)

        # Tokens
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "tokens", tb_id],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        token = json.loads(result.stdout.strip())
        self.assertEqual(token["claim"], "echo workflow_test")
        self.assertGreater(token["s"], 1.0)  # Score increased from exec challenge

        # Token score
        token_id = token["id"]
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "token-score", token_id],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        score = json.loads(result.stdout.strip())
        self.assertEqual(score["id"], token_id)
        self.assertIsNotNone(score["last_challenge"])
        self.assertEqual(score["last_challenge"]["type"], "exec")

    def test_clear_cache_no_cache(self):
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "clear-cache"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("no snapshot cache", result.stdout)

    def test_exec_failure_no_token(self):
        """Failed exec should not mint a token."""
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "create"],
            capture_output=True, text=True,
        )
        tb_id = result.stdout.strip()

        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "exec", tb_id, "--", "false"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)  # Command failed

        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "tokens", tb_id],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)  # No tokens
        self.assertIn("no tokens", result.stderr)


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
