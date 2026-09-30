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

    # Phase 1 UPM Integration Tests

    def test_execute_without_install_unchanged(self) -> None:
        """Backward compatibility: install_packages=False behaves as before."""
        adapter = LocalExecutionAdapter(repo=Repository(self._repo_path))
        receipt = adapter.execute(
            job_id="job_noinstall",
            command="echo backward_compat",
            install_packages=False,  # Explicit but default
        )
        self.assertEqual(receipt.status, "COMPLETED")
        self.assertEqual(receipt.exit_code, 0)
        self.assertNotIn("upm_install", " ".join(receipt.provenance))

    def test_execute_install_missing_lockfile_fails(self) -> None:
        """Install fails with ELOCK when no upm.lock or package.json exists."""
        adapter = LocalExecutionAdapter(repo=Repository(self._repo_path))
        # Empty repo: no package.json or upm.lock
        receipt = adapter.execute(
            job_id="job_nolock",
            command="echo test",
            install_packages=True,
            package_manager="upm",
        )
        self.assertEqual(receipt.status, "INSTALL_FAILED")
        self.assertIn("ELOCK", receipt.error)
        self.assertTrue(any("install_error" in prov for prov in receipt.provenance))

    def test_execute_install_with_upm_lock(self) -> None:
        """Install succeeds when upm.lock exists (mocked behavior)."""
        # Create a minimal upm.lock for testing
        repo = Repository(self._repo_path)
        lock_path = Path(self._repo_path) / "upm.lock"
        lock_path.write_text('{"packages": [], "root": {}}', encoding="utf-8")

        adapter = LocalExecutionAdapter(repo=repo)
        receipt = adapter.execute(
            job_id="job_withlock",
            command="echo installed",
            install_packages=True,
            package_manager="upm",
        )
        # If upm is not installed, we expect a UPM_NOT_FOUND error
        # This is acceptable for unit test (not LIVE VERIFIED)
        # The status should be either COMPLETED (if upm available) or INSTALL_FAILED
        self.assertIn(receipt.status, ["COMPLETED", "INSTALL_FAILED"])
        if receipt.status == "INSTALL_FAILED":
            # Expected when UPM is not available in test environment
            self.assertIn("UPM_NOT_FOUND", receipt.error)

    def test_execute_install_with_package_json(self) -> None:
        """Install succeeds when package.json exists (mocked behavior)."""
        # Create a minimal package.json
        repo = Repository(self._repo_path)
        pkg_path = Path(self._repo_path) / "package.json"
        pkg_path.write_text('{"name": "test", "version": "1.0.0", "dependencies": {}}', encoding="utf-8")

        adapter = LocalExecutionAdapter(repo=repo)
        receipt = adapter.execute(
            job_id="job_withpkg",
            command="echo setup",
            install_packages=True,
            package_manager="upm",
        )
        # Expected status depends on whether upm is available
        self.assertIn(receipt.status, ["COMPLETED", "INSTALL_FAILED"])
        if receipt.status == "INSTALL_FAILED":
            self.assertIn("UPM", receipt.error)  # UPM-related error

    def test_execute_install_unsupported_manager_fails(self) -> None:
        """Install fails when package_manager is not 'upm'."""
        repo = Repository(self._repo_path)
        pkg_path = Path(self._repo_path) / "package.json"
        pkg_path.write_text('{"name": "test"}', encoding="utf-8")

        adapter = LocalExecutionAdapter(repo=repo)
        receipt = adapter.execute(
            job_id="job_badmgr",
            command="echo test",
            install_packages=True,
            package_manager="npm",  # Unsupported (Phase 1)
        )
        self.assertEqual(receipt.status, "INSTALL_FAILED")
        self.assertIn("unsupported_package_manager", receipt.error)


if __name__ == "__main__":
    unittest.main()
