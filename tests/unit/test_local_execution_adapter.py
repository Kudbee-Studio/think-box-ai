"""Unit tests for local Think Box execution adapter."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from thinkbox.execution_adapter import _sha256_file
from thinkbox.local_execution_adapter import (
    LOCAL_PROVIDER,
    LocalExecutionAdapter,
    intent_fingerprint,
    receipt_to_public_dict,
)
from thinkbox.repository import Repository

REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(path),
        check=True,
    )
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "initial"], cwd=str(path), check=True)


class TestLocalExecutionAdapter(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._repo_path = Path(self._tmp.name) / "repo"
        self._repo_path.mkdir()
        _make_git_repo(self._repo_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_intent_fingerprint_stable(self) -> None:
        a = intent_fingerprint("echo proof")
        b = intent_fingerprint("echo proof")
        self.assertEqual(a, b)
        self.assertNotEqual(a, intent_fingerprint("echo other"))

    def test_execute_completed_with_artifact_and_checkpoint(self) -> None:
        adapter = LocalExecutionAdapter(repo=Repository(self._repo_path))
        receipt = adapter.execute(
            job_id="job_local_1",
            command="echo THINKBOX_LOCAL_EXECUTION_PROOF",
            artifact_name="local_proof.json",
        )
        self.assertEqual(receipt.provider, LOCAL_PROVIDER)
        self.assertEqual(receipt.status, "COMPLETED")
        self.assertTrue(receipt.verified)
        self.assertEqual(receipt.exit_code, 0)
        self.assertTrue(receipt.artifact_path)
        self.assertTrue(Path(receipt.artifact_path).exists())
        self.assertEqual(receipt.artifact_hash, _sha256_file(Path(receipt.artifact_path)))
        self.assertTrue(receipt.checkpoint_id)
        self.assertTrue(receipt.receipt_path)
        self.assertTrue(adapter.verify(receipt))
        body = json.loads(Path(receipt.artifact_path).read_text(encoding="utf-8"))
        self.assertIn("THINKBOX_LOCAL_EXECUTION_PROOF", body["stdout"])
        self.assertEqual(body["provider"], LOCAL_PROVIDER)

    def test_fail_closed_empty_command(self) -> None:
        adapter = LocalExecutionAdapter(repo=Repository(self._repo_path))
        receipt = adapter.execute(job_id="job_empty", command="   ")
        self.assertEqual(receipt.status, "INVALID_COMMAND")
        self.assertFalse(receipt.verified)

    def test_public_dict_never_claims_live(self) -> None:
        adapter = LocalExecutionAdapter(repo=Repository(self._repo_path))
        receipt = adapter.execute(job_id="job_pub", command="echo ok")
        public = receipt_to_public_dict(receipt)
        dumped = json.dumps(public)
        self.assertFalse(public["live_verified"])
        self.assertFalse(public["live_api_called"])
        self.assertEqual(public["provider"], LOCAL_PROVIDER)
        self.assertNotIn("echo ok", dumped)


if __name__ == "__main__":
    unittest.main()
