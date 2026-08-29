"""CLI tests for thinkbox create/exec/evidence."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from think_box_ai import cli


class TestThinkboxCLI(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._env = os.environ.copy()
        self._env["THINKBOX_DB_PATH"] = os.path.join(self._tmpdir, "test.db")
        self._env["THINKBOX_EVIDENCE_DIR"] = os.path.join(self._tmpdir, "evidence")

    def tearDown(self):
        pass

    def _run(self, args):
        """Run CLI with test environment."""
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

        result = self._run(["exec", tb_id, "--", "echo", "KUDBEE_LOCAL_OK"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("KUDBEE_LOCAL_OK", result.stdout)

    def test_evidence_shows_ok(self):
        result = self._run(["create"])
        tb_id = result.stdout.strip()

        self._run(["exec", tb_id, "--", "echo", "KUDBEE_LOCAL_OK"])

        result = self._run(["evidence", tb_id])
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout.strip())
        self.assertEqual(data["ok"], True)
        self.assertEqual(data["exit_code"], 0)
        self.assertEqual(data["provider"], "local")

    def test_bogus_id_returns_error(self):
        result = self._run(["evidence", "tb-nonexistent"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no evidence", result.stderr)

    def test_challenge_jury_no_url_exits_2(self):
        # Ensure no URL is set for this test
        env = self._env.copy()
        env.pop("OPENAI_BASE_URL", None)
        env.pop("THINKBOX_JURY_URL", None)
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "challenge-jury", "tt-any"],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("JURY_UNAVAILABLE", result.stderr)

    def test_list_shows_boxes(self):
        result = self._run(["create"])
        tb_id = result.stdout.strip()
        self._run(["exec", tb_id, "--", "echo", "test"])

        result = self._run(["list"])
        self.assertEqual(result.returncode, 0)
        self.assertIn(tb_id, result.stdout)

    def test_status_shows_tokens(self):
        result = self._run(["create"])
        tb_id = result.stdout.strip()
        self._run(["exec", tb_id, "--", "echo", "test"])

        result = self._run(["status", tb_id])
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout.strip())
        self.assertEqual(data["box_id"], tb_id)
        self.assertGreaterEqual(data["token_count"], 1)

    def test_status_bogus_id_returns_error(self):
        result = self._run(["status", "tb-bogus"])
        self.assertNotEqual(result.returncode, 0)

    def test_export_import_roundtrip(self):
        result = self._run(["create"])
        tb_id = result.stdout.strip()
        self._run(["exec", tb_id, "--", "echo", "roundtrip"])

        export_path = os.path.join(self._tmpdir, "export.json")
        result = self._run(["export", tb_id, "-o", export_path])
        self.assertEqual(result.returncode, 0)

        self._run(["delete", tb_id])

        result = self._run(["import", export_path])
        self.assertEqual(result.returncode, 0)
        self.assertIn(tb_id, result.stdout)

        result = self._run(["tokens", tb_id])
        self.assertEqual(result.returncode, 0)
        self.assertIn("roundtrip", result.stdout)

    def test_delete_removes_data(self):
        result = self._run(["create"])
        tb_id = result.stdout.strip()
        self._run(["exec", tb_id, "--", "echo", "delete_me"])

        result = self._run(["delete", tb_id])
        self.assertEqual(result.returncode, 0)

        result = self._run(["tokens", tb_id])
        self.assertEqual(result.returncode, 1)

    def test_full_workflow(self):
        """Test the complete workflow: create -> exec -> evidence -> tokens -> score."""
        result = self._run(["create"])
        self.assertEqual(result.returncode, 0)
        tb_id = result.stdout.strip()
        self.assertTrue(tb_id.startswith("tb-"))

        result = self._run(["exec", tb_id, "--", "echo", "workflow_test"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("workflow_test", result.stdout)

        result = self._run(["evidence", tb_id])
        self.assertEqual(result.returncode, 0)
        evidence = json.loads(result.stdout.strip())
        self.assertEqual(evidence["ok"], True)
        self.assertEqual(evidence["exit_code"], 0)

        result = self._run(["tokens", tb_id])
        self.assertEqual(result.returncode, 0)
        token = json.loads(result.stdout.strip())
        self.assertEqual(token["claim"], "echo workflow_test")
        self.assertGreater(token["s"], 1.0)

        token_id = token["id"]
        result = self._run(["token-score", token_id])
        self.assertEqual(result.returncode, 0)
        score = json.loads(result.stdout.strip())
        self.assertEqual(score["id"], token_id)
        self.assertIsNotNone(score["last_challenge"])
        self.assertEqual(score["last_challenge"]["type"], "exec")

    def test_clear_cache_no_cache(self):
        result = self._run(["clear-cache"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("no snapshot cache", result.stdout)

    def test_exec_failure_no_token(self):
        """Failed exec should not mint a token."""
        result = self._run(["create"])
        tb_id = result.stdout.strip()

        result = self._run(["exec", tb_id, "--", "false"])
        self.assertEqual(result.returncode, 1)  # Command failed

        result = self._run(["tokens", tb_id])
        self.assertEqual(result.returncode, 1)  # No tokens
        self.assertIn("no tokens", result.stderr)


class TestThinkboxCLIJuryMocked(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._env = os.environ.copy()
        self._env["THINKBOX_DB_PATH"] = os.path.join(self._tmpdir, "test.db")
        self._env["THINKBOX_EVIDENCE_DIR"] = os.path.join(self._tmpdir, "evidence")

    def tearDown(self):
        pass

    def _run(self, args):
        return subprocess.run(
            ["python3", "-m", "think_box_ai.cli"] + args,
            capture_output=True, text=True, env=self._env,
        )

    def test_challenge_jury_no_url_exits_2(self):
        # Ensure no URL is set for this test
        env = self._env.copy()
        env.pop("OPENAI_BASE_URL", None)
        env.pop("THINKBOX_JURY_URL", None)
        result = subprocess.run(
            ["python3", "-m", "think_box_ai.cli", "challenge-jury", "tt-any"],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("JURY_UNAVAILABLE", result.stderr)

    def test_challenge_jury_mocked_yes_via_cli(self):
        # Create a token first
        result = self._run(["create"])
        tb_id = result.stdout.strip()
        self._run(["exec", tb_id, "--", "echo", "hello"])

        result = self._run(["tokens", tb_id])
        token_id = json.loads(result.stdout.strip())["id"]

        # Test the store directly with mock
        from core.memory.store import MemoryStore
        store = MemoryStore(self._env["THINKBOX_DB_PATH"])
        token_before = store.get_token(token_id)["s"]

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                "choices": [{"message": {"content": "YES"}}]
            }).encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = lambda s, *a: None
            mock_urlopen.return_value = mock_resp

            challenge_id = store.challenge_jury(token_id, "http://localhost:9999")

        self.assertIsNotNone(challenge_id)
        token_after = store.get_token(token_id)["s"]
        self.assertGreater(token_after, token_before)


if __name__ == "__main__":
    unittest.main()
