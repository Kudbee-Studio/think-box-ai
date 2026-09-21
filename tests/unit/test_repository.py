"""Unit tests for thinkbox/repository.py — Think Repository."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from thinkbox.git_engine import GitEngine
from thinkbox.repository import Checkpoint, Repository, Worktree


def _make_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(path), check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "initial"], cwd=str(path), check=True)


class TestRepository(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._repo = Path(self._tmp.name) / "repo"
        self._repo.mkdir()
        _make_git_repo(self._repo)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _open(self, **kwargs) -> Repository:
        defaults = {"enforce_git": True}
        defaults.update(kwargs)
        return Repository(self._repo, **defaults)

    def test_initializes_worktree(self):
        repo = self._open()
        worktree = repo.worktree
        self.assertTrue(worktree.worktree_id.startswith("wt_"))
        self.assertEqual(worktree.path, self._repo)
        self.assertEqual(worktree.git_branch, "main")
        self.assertEqual(worktree.status, "available")
        self.assertIsNone(worktree.attached_session_id)
        self.assertIsNone(worktree.current_job_id)

    def test_persists_worktree_across_instances(self):
        repo = self._open()
        repo.attach_session("sess_alpha")
        repo2 = self._open()
        self.assertEqual(repo2.worktree.attached_session_id, "sess_alpha")

    def test_refresh_git_state(self):
        repo = self._open()
        state = repo.refresh_git_state()
        self.assertEqual(state.branch, "main")
        self.assertTrue(state.head)
        # metadata file created during initialization is untracked
        self.assertTrue(state.dirty)

    def test_attach_detach_session(self):
        repo = self._open()
        worktree = repo.attach_session("sess_1")
        self.assertEqual(worktree.attached_session_id, "sess_1")
        self.assertEqual(worktree.status, "active")
        self.assertEqual(repo.current_session(), "sess_1")

        detached = repo.detach_session()
        self.assertIsNone(detached.attached_session_id)
        self.assertEqual(detached.status, "available")
        self.assertIsNone(repo.current_session())

    def test_start_complete_job(self):
        repo = self._open()
        repo.attach_session("sess_2")
        worktree = repo.start_job("job_1", intent="fix bug")
        self.assertEqual(worktree.current_job_id, "job_1")
        self.assertEqual(worktree.metadata["intent"], "fix bug")

        completed = repo.complete_job(outcome="done")
        self.assertIsNone(completed.current_job_id)
        self.assertEqual(completed.metadata["outcome"], "done")

    def test_summary_includes_git_state(self):
        repo = self._open()
        summary = repo.summary()
        self.assertEqual(summary["repository_version"], "stage1")
        self.assertIn("worktree", summary)
        self.assertIn("git_state", summary)
        self.assertEqual(summary["git_state"]["branch"], "main")

    def test_checkpoint_roundtrip(self):
        repo = self._open()
        repo.attach_session("sess_3")
        checkpoint = repo.checkpoint("baseline", metadata={"step": 1})
        self.assertTrue(checkpoint.checkpoint_id.startswith("chk_"))
        self.assertEqual(checkpoint.git_branch, "main")
        self.assertEqual(checkpoint.attached_session_id, "sess_3")

        saved = repo.checkpoints()
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].checkpoint_id, checkpoint.checkpoint_id)

        restored = repo.restore_checkpoint(checkpoint.checkpoint_id)
        self.assertEqual(restored.attached_session_id, "sess_3")
        self.assertEqual(restored.git_branch, "main")

    def test_restore_missing_checkpoint_raises(self):
        repo = self._open()
        with self.assertRaises(FileNotFoundError):
            repo.restore_checkpoint("chk_missing")

    def test_detach_keeps_job_status(self):
        repo = self._open()
        repo.attach_session("sess_4")
        repo.start_job("job_2")
        repo.detach_session()
        self.assertEqual(repo.worktree.status, "active")
        self.assertEqual(repo.worktree.current_job_id, "job_2")


if __name__ == "__main__":
    unittest.main()
