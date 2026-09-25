"""Hermetic tests for PR #202 durable lifecycle hardens."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from thinkbox.governed_execution_lifecycle import (
    PHASE_ADMISSION,
    PHASE_COMPLETED,
    PHASE_FAILED,
    PHASE_QUEUED,
    PHASE_RUNNING,
    lifecycle_to_status_record,
    load_lifecycle,
    open_lifecycle_repo,
    persist_lifecycle_phase,
)
from thinkbox.lifecycle_harden import (
    EXPECTED_HARDEN_COUNT,
    HARDENS,
    LifecycleError,
    bound_goal,
    bound_transitions,
    harden_ids,
    list_durable_jobs,
    redact_lifecycle_result,
    redacted_audit_snapshot,
    reject_remote_local_fallback,
    reject_terminal_regression,
    reject_unknown_phase,
    resume_eligibility,
    validate_artifact_hash,
    validate_job_id,
    validate_substrate,
    verify_terminal_artifact_hash,
    worktree_must_be_directory,
)
from thinkbox.governed_job_execution import SUBSTRATE_LOCAL, execute_governed_job_command
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


class TestLifecycleHarden(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._repo_path = Path(self._tmp.name) / "repo"
        self._repo_path.mkdir()
        _make_git_repo(self._repo_path)
        self.repo = open_lifecycle_repo(self._repo_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_h01_invalid_job_id(self) -> None:
        with self.assertRaises(LifecycleError) as ctx:
            validate_job_id("../escape")
        self.assertEqual(ctx.exception.code, "invalid_job_id")

    def test_h02_h03_unknown_phase(self) -> None:
        with self.assertRaises(LifecycleError) as ctx:
            reject_unknown_phase("paused")
        self.assertEqual(ctx.exception.code, "unknown_phase")

    def test_h04_terminal_regression(self) -> None:
        persist_lifecycle_phase(self.repo, "j_term", PHASE_ADMISSION, goal="g", receipt_id="r1")
        persist_lifecycle_phase(
            self.repo,
            "j_term",
            PHASE_COMPLETED,
            receipt_id="r1",
            result={"ok": True},
        )
        with self.assertRaises(LifecycleError) as ctx:
            persist_lifecycle_phase(self.repo, "j_term", PHASE_RUNNING)
        self.assertEqual(ctx.exception.code, "terminal_immutable")
        with self.assertRaises(LifecycleError):
            reject_terminal_regression(PHASE_FAILED, PHASE_QUEUED)

    def test_h05_bound_transitions(self) -> None:
        clipped = bound_transitions([{"phase": "x"}] * 40)
        self.assertEqual(len(clipped), 32)

    def test_h06_h23_redact_command_and_token(self) -> None:
        out = redact_lifecycle_result(
            {"exec_command": "echo secret", "governance_token": "tok", "ok": True}
        )
        self.assertIsNotNone(out)
        assert out is not None
        self.assertNotIn("exec_command", out)
        self.assertNotIn("governance_token", out)
        self.assertTrue(out["ok"])

    def test_h07_invalid_hash(self) -> None:
        with self.assertRaises(LifecycleError):
            validate_artifact_hash("not-hex")
        self.assertEqual(validate_artifact_hash("ab" * 8), "ab" * 8)

    def test_h08_unknown_substrate(self) -> None:
        with self.assertRaises(LifecycleError):
            validate_substrate("aws")
        self.assertEqual(validate_substrate("local"), "local")

    def test_h09_remote_local_fallback_forbidden(self) -> None:
        with self.assertRaises(LifecycleError) as ctx:
            reject_remote_local_fallback("upstash-box", "local")
        self.assertEqual(ctx.exception.code, "remote_local_fallback_forbidden")

    def test_h10_live_flags_false(self) -> None:
        persist_lifecycle_phase(self.repo, "j_live", PHASE_ADMISSION, goal="g")
        loaded = load_lifecycle(self.repo, "j_live")
        assert loaded is not None
        self.assertFalse(loaded["live_verified"])
        self.assertFalse(loaded["live_api_called"])

    def test_h11_timestamps(self) -> None:
        persist_lifecycle_phase(self.repo, "j_ts", PHASE_ADMISSION, goal="g", receipt_id="r")
        persist_lifecycle_phase(self.repo, "j_ts", PHASE_COMPLETED, receipt_id="r", result={})
        loaded = load_lifecycle(self.repo, "j_ts")
        assert loaded is not None
        self.assertTrue(loaded["started_at"])
        self.assertTrue(loaded["completed_at"])

    def test_h12_skip_duplicate_phase(self) -> None:
        persist_lifecycle_phase(self.repo, "j_dup", PHASE_ADMISSION, goal="g")
        persist_lifecycle_phase(self.repo, "j_dup", PHASE_QUEUED)
        persist_lifecycle_phase(self.repo, "j_dup", PHASE_QUEUED)
        loaded = load_lifecycle(self.repo, "j_dup")
        assert loaded is not None
        phases = [t["phase"] for t in loaded["transitions"]]
        self.assertEqual(phases, [PHASE_ADMISSION, PHASE_QUEUED])

    def test_h13_corrupt_blob_recovers(self) -> None:
        Repository(self._repo_path).create_job(job_id="j_bad", metadata={"governed_lifecycle": "nope"})
        persist_lifecycle_phase(self.repo, "j_bad", PHASE_ADMISSION, goal="recover")
        loaded = load_lifecycle(open_lifecycle_repo(self._repo_path), "j_bad")
        self.assertIsNotNone(loaded)

    def test_h14_list_durable_jobs(self) -> None:
        persist_lifecycle_phase(self.repo, "j_list", PHASE_ADMISSION, goal="g")
        self.assertIn("j_list", list_durable_jobs(self.repo))

    def test_h15_verify_artifact_hash(self) -> None:
        persist_lifecycle_phase(
            self.repo, "j_art", PHASE_ADMISSION, goal="local", receipt_id="r_art"
        )
        result = execute_governed_job_command(
            substrate=SUBSTRATE_LOCAL,
            job_id="j_art",
            command="echo HARDEN",
            repo=Repository(self._repo_path),
        )
        persist_lifecycle_phase(
            self.repo,
            "j_art",
            PHASE_COMPLETED,
            receipt_id="r_art",
            artifact_path=result.receipt.artifact_path,
            artifact_hash=result.receipt.artifact_hash,
            checkpoint_id=result.receipt.checkpoint_id,
            result={"execution_proof": result.public_proof},
        )
        loaded = load_lifecycle(self.repo, "j_art")
        assert loaded is not None
        self.assertTrue(verify_terminal_artifact_hash(loaded))

    def test_h16_completed_requires_receipt(self) -> None:
        persist_lifecycle_phase(self.repo, "j_noreceipt", PHASE_ADMISSION, goal="g")
        with self.assertRaises(LifecycleError) as ctx:
            persist_lifecycle_phase(self.repo, "j_noreceipt", PHASE_COMPLETED, result={})
        self.assertEqual(ctx.exception.code, "completed_missing_receipt")

    def test_h17_admission_must_be_first(self) -> None:
        with self.assertRaises(LifecycleError) as ctx:
            persist_lifecycle_phase(self.repo, "j_first", PHASE_QUEUED)
        self.assertEqual(ctx.exception.code, "admission_required")

    def test_h19_bound_goal(self) -> None:
        self.assertEqual(len(bound_goal("x" * 500)), 200)

    def test_h20_resume_only_queued(self) -> None:
        self.assertTrue(resume_eligibility(PHASE_QUEUED))
        self.assertFalse(resume_eligibility(PHASE_RUNNING))

    def test_h21_failed_requires_error(self) -> None:
        persist_lifecycle_phase(self.repo, "j_fail", PHASE_ADMISSION, goal="g")
        with self.assertRaises(LifecycleError) as ctx:
            persist_lifecycle_phase(self.repo, "j_fail", PHASE_FAILED, result={})
        self.assertEqual(ctx.exception.code, "failed_missing_error")

    def test_h22_worktree_must_exist(self) -> None:
        with self.assertRaises(LifecycleError):
            worktree_must_be_directory(self._repo_path / "missing")

    def test_h24_status_includes_lifecycle_phase(self) -> None:
        persist_lifecycle_phase(self.repo, "j_st", PHASE_ADMISSION, goal="g")
        persist_lifecycle_phase(self.repo, "j_st", PHASE_QUEUED)
        loaded = load_lifecycle(self.repo, "j_st")
        assert loaded is not None
        record = lifecycle_to_status_record(loaded)
        self.assertEqual(record["lifecycle_phase"], PHASE_QUEUED)
        self.assertTrue(record["resume_eligible"])

    def test_h25_audit_snapshot_redacted(self) -> None:
        persist_lifecycle_phase(
            self.repo,
            "j_aud",
            PHASE_ADMISSION,
            goal="g",
            receipt_id="r",
            result={"exec_command": "echo x", "ok": True},
        )
        loaded = load_lifecycle(self.repo, "j_aud")
        assert loaded is not None
        snap = redacted_audit_snapshot(loaded)
        self.assertFalse(snap["live_verified"])
        self.assertNotIn("exec_command", snap["result_keys"])

    def test_harden_count_is_25(self) -> None:
        self.assertEqual(len(HARDENS), EXPECTED_HARDEN_COUNT)
        self.assertEqual(len(harden_ids()), 25)


if __name__ == "__main__":
    unittest.main()
