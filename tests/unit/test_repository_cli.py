"""Unit tests for thinkbox/repository_cli.py — Think CLI harness."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHONPATH = str(REPO_ROOT)


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "thinkbox.repository_cli", *args],
        cwd=str(cwd),
        env={**os.environ, "PYTHONPATH": PYTHONPATH},
        capture_output=True,
        text=True,
        timeout=30,
    )


def _make_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(path), check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "initial"], cwd=str(path), check=True)


class TestRepositoryCLI(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._repo = Path(self._tmp.name) / "repo"
        self._repo.mkdir()
        _make_git_repo(self._repo)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _output(self, *args: str) -> str:
        result = _run(list(args), self._repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_repo_inspect(self):
        output = self._output("repo", "inspect")
        self.assertIn("repository_version: stage1", output)
        self.assertIn("git_branch: main", output)
        self.assertIn("git_head:", output)
        self.assertIn("status: available", output)

    def test_box_inspect(self):
        self._output("repo", "inspect")
        output = self._output("box", "inspect")
        self.assertIn("box_id:", output)
        self.assertIn("status: available", output)
        self.assertIn("current_job_id: None", output)

    def test_job_create(self):
        output = self._output("job", "create", "--intent", "test intent", "--name", "myjob")
        self.assertRegex(output, r"job_id: job_[a-z0-9]+")
        self.assertIn("status: pending", output)
        self.assertIn("next_action: run", output)

    def test_job_status_persists_across_invocations(self):
        create = self._output("job", "create", "--job-id", "job_persist", "--intent", "persist")
        self.assertIn("job_id: job_persist", create)
        status = self._output("job", "status", "--job-id", "job_persist")
        self.assertIn("status: pending", status)
        self.assertIn("intent: persist", status)

    def test_checkpoint_survives_process_boundary(self):
        self._output("job", "create", "--job-id", "job_ckpt", "--intent", "checkpoint")
        result = self._output("job", "checkpoint", "--job-id", "job_ckpt", "--name", "first")
        self.assertIn("checkpoint_id: chk_", result)
        path = result.split("checkpoint_path: ")[-1].splitlines()[0].strip()
        self.assertTrue(Path(path).exists())

    def test_receipt_located_and_verified(self):
        self._output("job", "create", "--job-id", "job_rcpt", "--intent", "receipt")
        self._output("job", "checkpoint", "--job-id", "job_rcpt", "--name", "rcpt")
        result = self._output("job", "receipt", "--job-id", "job_rcpt")
        self.assertIn("receipt_path:", result)
        self.assertIn("verified: True", result)
        path = result.split("receipt_path: ")[-1].splitlines()[0].strip()
        data = json.loads(Path(path).read_text())
        self.assertIn("checkpoint_id", data)

    def test_git_remains_clean_under_metadata(self):
        self._output("job", "create", "--job-id", "job_git", "--intent", "git")
        proc = subprocess.run(
            ["git", "diff", "--quiet"],
            cwd=str(self._repo),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(self._repo),
            capture_output=True,
            text=True,
            timeout=10,
        )
        tracked = [line for line in status.stdout.splitlines() if line.startswith("M ") or line.startswith("D ") or line.startswith("A ")]
        self.assertEqual(tracked, [])

    def test_no_secrets_printed(self):
        output = self._output("repo", "inspect")
        for secret in ("THINKBOX_API_KEY", "SECRET", "API_KEY", "TOKEN"):
            self.assertNotIn(secret, output)


if __name__ == "__main__":
    unittest.main()
