"""Hermetic tests for durable governed execution lifecycle (Repository-backed)."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from thinkbox.execution_adapter import _sha256_file
from thinkbox.governed_execution_lifecycle import (
    PHASE_ADMISSION,
    PHASE_COMPLETED,
    PHASE_FAILED,
    PHASE_QUEUED,
    PHASE_RUNNING,
    http_status_for_phase,
    lifecycle_to_status_record,
    load_lifecycle,
    open_lifecycle_repo,
    persist_lifecycle_phase,
    terminal_evidence,
)
from thinkbox.governed_job_execution import (
    SUBSTRATE_LOCAL,
    SUBSTRATE_UPSTASH_BOX,
    GovernedJobExecutionError,
    execute_governed_job_command,
    select_execution_adapter,
)
from thinkbox.repository import Repository


def _make_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(path),
        check=True,
    )
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "initial"], cwd=str(path), check=True)


class TestGovernedExecutionLifecycle(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._repo_path = Path(self._tmp.name) / "repo"
        self._repo_path.mkdir()
        _make_git_repo(self._repo_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_transitions_persist_and_survive_reload(self) -> None:
        repo = open_lifecycle_repo(self._repo_path)
        persist_lifecycle_phase(
            repo,
            "job_life_1",
            PHASE_ADMISSION,
            goal="durable admit",
            receipt_id="tb_rcpt_life",
            experiment_id="tb_exp_life",
            session_id="tb_sess_life",
            execution_substrate=SUBSTRATE_LOCAL,
        )
        persist_lifecycle_phase(repo, "job_life_1", PHASE_QUEUED)
        persist_lifecycle_phase(repo, "job_life_1", PHASE_RUNNING)
        persist_lifecycle_phase(
            repo,
            "job_life_1",
            PHASE_COMPLETED,
            verdict="COMPLETED",
            checkpoint_id="chk_1",
            artifact_path="/tmp/a.json",
            artifact_hash="abc",
            result={"governed_shell": True, "adapter_provider": "local"},
        )
        reloaded = open_lifecycle_repo(self._repo_path)
        loaded = load_lifecycle(reloaded, "job_life_1")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        phases = [t["phase"] for t in loaded["transitions"]]
        self.assertEqual(
            phases,
            [PHASE_ADMISSION, PHASE_QUEUED, PHASE_RUNNING, PHASE_COMPLETED],
        )
        self.assertEqual(loaded["receipt_id"], "tb_rcpt_life")
        record = lifecycle_to_status_record(loaded)
        self.assertEqual(record["source"], "repository_lifecycle")
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["result"]["adapter_provider"], "local")

    def test_completed_local_retains_receipt_checkpoint_artifact(self) -> None:
        repo = Repository(self._repo_path)
        persist_lifecycle_phase(
            repo,
            "job_local_ok",
            PHASE_ADMISSION,
            goal="local exec",
            receipt_id="tb_rcpt_local",
            execution_substrate=SUBSTRATE_LOCAL,
        )
        result = execute_governed_job_command(
            substrate=SUBSTRATE_LOCAL,
            job_id="job_local_ok",
            command="echo THINKBOX_LIFECYCLE_LOCAL",
            repo=repo,
        )
        persist_lifecycle_phase(
            repo,
            "job_local_ok",
            PHASE_COMPLETED,
            adapter_provider=result.adapter_provider,
            checkpoint_id=result.receipt.checkpoint_id,
            artifact_path=result.receipt.artifact_path,
            artifact_hash=result.receipt.artifact_hash,
            verdict=result.receipt.status,
            result={"execution_proof": result.public_proof},
        )
        loaded = load_lifecycle(open_lifecycle_repo(self._repo_path), "job_local_ok")
        assert loaded is not None
        evidence = terminal_evidence(loaded)
        self.assertEqual(evidence.receipt_id, "tb_rcpt_local")
        self.assertTrue(evidence.checkpoint_id)
        self.assertTrue(Path(evidence.artifact_path).is_file())
        self.assertEqual(_sha256_file(Path(evidence.artifact_path)), evidence.artifact_hash)
        self.assertEqual(evidence.verdict, "COMPLETED")
        self.assertFalse(loaded["live_verified"])

    def test_failed_state_is_honest_and_durable(self) -> None:
        repo = open_lifecycle_repo(self._repo_path)
        persist_lifecycle_phase(repo, "job_fail", PHASE_ADMISSION, goal="fail")
        persist_lifecycle_phase(
            repo,
            "job_fail",
            PHASE_FAILED,
            verdict="remote_not_configured",
            result={"error": "remote_not_configured", "message": "no fallback"},
        )
        loaded = load_lifecycle(open_lifecycle_repo(self._repo_path), "job_fail")
        assert loaded is not None
        record = lifecycle_to_status_record(loaded)
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["result"]["error"], "remote_not_configured")

    def test_upstash_does_not_fall_back_to_local(self) -> None:
        repo = Repository(self._repo_path)
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(GovernedJobExecutionError) as ctx:
                select_execution_adapter(SUBSTRATE_UPSTASH_BOX, repo)
        self.assertEqual(ctx.exception.code, "remote_not_configured")
        repo_life = open_lifecycle_repo(self._repo_path)
        persist_lifecycle_phase(
            repo_life,
            "job_remote_fail",
            PHASE_ADMISSION,
            goal="remote fail",
            execution_substrate=SUBSTRATE_UPSTASH_BOX,
        )
        persist_lifecycle_phase(
            repo_life,
            "job_remote_fail",
            PHASE_FAILED,
            execution_substrate=SUBSTRATE_UPSTASH_BOX,
            verdict=ctx.exception.code,
            result={"error": ctx.exception.code},
        )
        loaded = load_lifecycle(open_lifecycle_repo(self._repo_path), "job_remote_fail")
        assert loaded is not None
        self.assertEqual(loaded["execution_substrate"], SUBSTRATE_UPSTASH_BOX)
        self.assertNotEqual(loaded.get("adapter_provider"), "local")

    def test_http_status_mapping(self) -> None:
        self.assertEqual(http_status_for_phase(PHASE_ADMISSION), "running")
        self.assertEqual(http_status_for_phase(PHASE_QUEUED), "running")
        self.assertEqual(http_status_for_phase(PHASE_RUNNING), "running")
        self.assertEqual(http_status_for_phase(PHASE_COMPLETED), "completed")
        self.assertEqual(http_status_for_phase(PHASE_FAILED), "failed")

    def test_update_job_merges_metadata(self) -> None:
        repo = Repository(self._repo_path)
        repo.create_job(job_id="job_meta", metadata={"keep": True})
        repo.update_job("job_meta", metadata={"extra": 1})
        snap = repo.job_status("job_meta")
        assert snap is not None
        self.assertTrue(snap["metadata"]["keep"])
        self.assertEqual(snap["metadata"]["extra"], 1)


if __name__ == "__main__":
    unittest.main()
