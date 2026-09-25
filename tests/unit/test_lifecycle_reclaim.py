"""Hermetic tests for RUNNING orphan reclaim via ownership lease."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from thinkbox.governed_execution_lifecycle import (
    PHASE_ADMISSION,
    PHASE_COMPLETED,
    PHASE_FAILED,
    PHASE_QUEUED,
    PHASE_RUNNING,
    load_lifecycle,
    open_lifecycle_repo,
    persist_lifecycle_phase,
)
from thinkbox.governed_job_execution import SUBSTRATE_LOCAL, SUBSTRATE_UPSTASH_BOX
from thinkbox.lifecycle_harden import recover_corrupt_lifecycle_blob
from thinkbox.lifecycle_lease import issue_lease, lease_is_expired
from thinkbox.lifecycle_reclaim import (
    ORPHAN_INCOMPLETE,
    ORPHAN_RECLAIM_KIND,
    TIMEOUT_REASON_EXPIRED,
    orphan_reclaim_count,
    reclaim_running_orphan,
)
from thinkbox.lifecycle_resume import (
    OUTCOME_CAS_LOST,
    OUTCOME_COMPLETED,
    OUTCOME_SKIPPED,
    RESUME_CLAIM_KIND,
    resume_queued_job,
)
from thinkbox.local_execution_adapter import LOCAL_PROVIDER
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


class TestLifecycleReclaim(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._repo_path = Path(self._tmp.name) / "repo"
        self._repo_path.mkdir()
        _make_git_repo(self._repo_path)
        self._t0 = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _plant_running(
        self,
        job_id: str,
        lease,
        *,
        substrate: str = SUBSTRATE_LOCAL,
        goal: str = "reclaim goal",
        receipt_id: str = "tb_rcpt_reclaim_1",
    ) -> None:
        repo = open_lifecycle_repo(self._repo_path)
        persist_lifecycle_phase(
            repo,
            job_id,
            PHASE_ADMISSION,
            goal=goal,
            receipt_id=receipt_id,
            experiment_id="tb_exp_reclaim",
            session_id="tb_sess_reclaim",
            execution_substrate=substrate,
        )
        persist_lifecycle_phase(
            repo,
            job_id,
            PHASE_QUEUED,
            receipt_id=receipt_id,
            execution_substrate=substrate,
        )
        persist_lifecycle_phase(
            repo,
            job_id,
            PHASE_RUNNING,
            goal=goal,
            receipt_id=receipt_id,
            execution_substrate=substrate,
            transition_kind=RESUME_CLAIM_KIND,
            lease_id=lease.lease_id,
            lease_started_at=lease.started_at,
            lease_expires_at=lease.expires_at,
            lease_timeout_seconds=lease.timeout_seconds,
            transition_at=lease.started_at,
        )

    def test_lease_expiry_boundary_is_persisted_timestamp(self) -> None:
        lease = issue_lease(now=self._t0, timeout_seconds=300)
        self.assertNotEqual(lease.lease_id, lease.started_at)
        just_before = self._t0 + timedelta(seconds=300) - timedelta(microseconds=1)
        at_expiry = self._t0 + timedelta(seconds=300)
        self.assertFalse(lease_is_expired(lease.expires_at, just_before))
        self.assertTrue(lease_is_expired(lease.expires_at, at_expiry))
        self._plant_running("job_bound_fresh", lease)
        fresh = reclaim_running_orphan(
            open_lifecycle_repo(self._repo_path),
            "job_bound_fresh",
            exec_command="echo NO",
            now=just_before,
        )
        self.assertEqual(fresh.outcome, OUTCOME_SKIPPED)
        self.assertEqual(fresh.error, "lease_fresh")
        self.assertFalse(fresh.executed)
        self._plant_running("job_bound_due", issue_lease(now=self._t0, timeout_seconds=300))
        due = reclaim_running_orphan(
            open_lifecycle_repo(self._repo_path),
            "job_bound_due",
            exec_command="echo BOUNDARY",
            now=at_expiry,
        )
        self.assertEqual(due.outcome, OUTCOME_COMPLETED)
        self.assertTrue(due.executed)

    def test_fresh_lease_is_not_reclaimed(self) -> None:
        lease = issue_lease(now=self._t0, timeout_seconds=300)
        self._plant_running("job_fresh", lease)
        result = reclaim_running_orphan(
            open_lifecycle_repo(self._repo_path),
            "job_fresh",
            exec_command="echo NO",
            now=self._t0 + timedelta(seconds=10),
        )
        self.assertEqual(result.error, "lease_fresh")
        loaded = load_lifecycle(open_lifecycle_repo(self._repo_path), "job_fresh")
        assert loaded is not None
        self.assertEqual(loaded["phase"], PHASE_RUNNING)
        self.assertEqual(orphan_reclaim_count(loaded["transitions"]), 0)
        self.assertEqual(loaded["lease_id"], lease.lease_id)

    def test_expired_lease_reclaims_once_on_existing_path(self) -> None:
        lease = issue_lease(now=self._t0, timeout_seconds=1)
        self._plant_running("job_due", lease)
        result = reclaim_running_orphan(
            open_lifecycle_repo(self._repo_path),
            "job_due",
            exec_command="echo ORPHAN_OK",
            now=self._t0 + timedelta(seconds=1),
        )
        self.assertEqual(result.outcome, OUTCOME_COMPLETED)
        self.assertTrue(result.executed)
        self.assertEqual(result.receipt_id, "tb_rcpt_reclaim_1")
        self.assertFalse(result.live_verified)
        loaded = load_lifecycle(open_lifecycle_repo(self._repo_path), "job_due")
        assert loaded is not None
        claims = [t for t in loaded["transitions"] if t.get("kind") == ORPHAN_RECLAIM_KIND]
        self.assertEqual(len(claims), 1)
        claim = claims[0]
        self.assertEqual(claim["prior_lease_id"], lease.lease_id)
        self.assertEqual(claim["prior_lease_started_at"], lease.started_at)
        self.assertEqual(claim["timeout_reason"], TIMEOUT_REASON_EXPIRED)
        self.assertNotEqual(claim["lease_id"], claim["at"])
        self.assertEqual(loaded["receipt_id"], "tb_rcpt_reclaim_1")
        self.assertEqual(loaded["phase"], PHASE_COMPLETED)
        second = reclaim_running_orphan(
            open_lifecycle_repo(self._repo_path),
            "job_due",
            exec_command="echo AGAIN",
            now=self._t0 + timedelta(hours=2),
        )
        self.assertEqual(second.outcome, OUTCOME_SKIPPED)
        self.assertFalse(second.executed)

    def test_concurrent_reclaim_one_execution(self) -> None:
        lease = issue_lease(now=self._t0, timeout_seconds=1)
        self._plant_running("job_race", lease)
        results: list[object] = []

        def _run() -> None:
            results.append(
                reclaim_running_orphan(
                    open_lifecycle_repo(self._repo_path),
                    "job_race",
                    exec_command="echo RACE",
                    now=self._t0 + timedelta(seconds=5),
                )
            )

        threads = [threading.Thread(target=_run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        executed = sum(1 for item in results if getattr(item, "executed", False))
        self.assertEqual(executed, 1)
        loaded = load_lifecycle(open_lifecycle_repo(self._repo_path), "job_race")
        assert loaded is not None
        self.assertEqual(orphan_reclaim_count(loaded["transitions"]), 1)

    def test_reread_not_running_stops(self) -> None:
        lease = issue_lease(now=self._t0, timeout_seconds=1)
        self._plant_running("job_gone", lease)

        def _finish() -> None:
            persist_lifecycle_phase(
                open_lifecycle_repo(self._repo_path),
                "job_gone",
                PHASE_FAILED,
                receipt_id="tb_rcpt_reclaim_1",
                verdict="operator_closed",
                result={"error": "operator_closed"},
                require_phase=PHASE_RUNNING,
                require_lease_id=lease.lease_id,
            )

        result = reclaim_running_orphan(
            open_lifecycle_repo(self._repo_path),
            "job_gone",
            exec_command="echo NO",
            now=self._t0 + timedelta(seconds=5),
            before_claim=_finish,
        )
        self.assertFalse(result.executed)
        self.assertEqual(result.error, "not_running")
        loaded = load_lifecycle(open_lifecycle_repo(self._repo_path), "job_gone")
        assert loaded is not None
        self.assertEqual(orphan_reclaim_count(loaded["transitions"]), 0)

    def test_stale_lease_claimant_stops(self) -> None:
        lease = issue_lease(now=self._t0, timeout_seconds=1)
        self._plant_running("job_stale", lease)
        replacement = issue_lease(now=self._t0 + timedelta(seconds=2), timeout_seconds=300)

        def _replace() -> None:
            persist_lifecycle_phase(
                open_lifecycle_repo(self._repo_path),
                "job_stale",
                PHASE_RUNNING,
                receipt_id="tb_rcpt_reclaim_1",
                execution_substrate=SUBSTRATE_LOCAL,
                require_phase=PHASE_RUNNING,
                require_lease_id=lease.lease_id,
                transition_kind=RESUME_CLAIM_KIND,
                lease_id=replacement.lease_id,
                lease_started_at=replacement.started_at,
                lease_expires_at=replacement.expires_at,
                lease_timeout_seconds=replacement.timeout_seconds,
                transition_at=replacement.started_at,
            )

        result = reclaim_running_orphan(
            open_lifecycle_repo(self._repo_path),
            "job_stale",
            exec_command="echo NO",
            now=self._t0 + timedelta(seconds=5),
            before_claim=_replace,
        )
        self.assertEqual(result.outcome, OUTCOME_CAS_LOST)
        self.assertFalse(result.executed)
        loaded = load_lifecycle(open_lifecycle_repo(self._repo_path), "job_stale")
        assert loaded is not None
        self.assertEqual(loaded["lease_id"], replacement.lease_id)
        self.assertEqual(orphan_reclaim_count(loaded["transitions"]), 0)

    def test_missing_inputs_fail_closed_without_artifact(self) -> None:
        lease = issue_lease(now=self._t0, timeout_seconds=1)
        self._plant_running("job_nocmd", lease, goal="keep")
        missing = reclaim_running_orphan(
            open_lifecycle_repo(self._repo_path),
            "job_nocmd",
            now=self._t0 + timedelta(seconds=5),
        )
        self.assertEqual(missing.outcome, ORPHAN_INCOMPLETE)
        self.assertEqual(missing.error, "missing_command")
        self.assertFalse(missing.executed)
        loaded = load_lifecycle(open_lifecycle_repo(self._repo_path), "job_nocmd")
        assert loaded is not None
        self.assertEqual(loaded["phase"], PHASE_FAILED)
        self.assertFalse(loaded.get("artifact_path"))

        self._plant_running("job_nogoal", lease, goal="")
        job_file = self._repo_path / ".thinkbox" / "jobs" / "job_nogoal.json"
        data = json.loads(job_file.read_text(encoding="utf-8"))
        data["intent"] = ""
        data["metadata"]["governed_lifecycle"]["goal"] = ""
        job_file.write_text(json.dumps(data), encoding="utf-8")
        no_goal = reclaim_running_orphan(
            open_lifecycle_repo(self._repo_path),
            "job_nogoal",
            exec_command="echo X",
            now=self._t0 + timedelta(seconds=5),
        )
        self.assertEqual(no_goal.error, "missing_goal")
        self.assertFalse(no_goal.executed)

    def test_worktree_mismatch_fail_closed(self) -> None:
        lease = issue_lease(now=self._t0, timeout_seconds=1)
        self._plant_running("job_wt", lease)
        job_file = self._repo_path / ".thinkbox" / "jobs" / "job_wt.json"
        data = json.loads(job_file.read_text(encoding="utf-8"))
        data["path"] = str(Path(self._tmp.name) / "other")
        job_file.write_text(json.dumps(data), encoding="utf-8")
        result = reclaim_running_orphan(
            open_lifecycle_repo(self._repo_path),
            "job_wt",
            exec_command="echo WT",
            now=self._t0 + timedelta(seconds=5),
        )
        self.assertEqual(result.error, "worktree_mismatch")
        self.assertFalse(result.executed)

    def test_unconfigured_upstash_never_local(self) -> None:
        lease = issue_lease(now=self._t0, timeout_seconds=1)
        self._plant_running("job_remote", lease, substrate=SUBSTRATE_UPSTASH_BOX)
        with mock.patch.dict(os.environ, {}, clear=True):
            result = reclaim_running_orphan(
                open_lifecycle_repo(self._repo_path),
                "job_remote",
                exec_command="echo remote",
                now=self._t0 + timedelta(seconds=5),
            )
        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.error, "remote_not_configured")
        self.assertFalse(result.executed)
        loaded = load_lifecycle(open_lifecycle_repo(self._repo_path), "job_remote")
        assert loaded is not None
        self.assertEqual(loaded.get("verdict"), "remote_not_configured")
        self.assertNotEqual(loaded.get("adapter_provider"), LOCAL_PROVIDER)
        self.assertFalse(loaded.get("live_verified"))
        self.assertEqual(orphan_reclaim_count(loaded["transitions"]), 1)

    def test_admission_queued_terminal_and_corrupt_are_not_reclaimed(self) -> None:
        repo = open_lifecycle_repo(self._repo_path)
        persist_lifecycle_phase(repo, "job_adm", PHASE_ADMISSION, goal="g", receipt_id="tb_rcpt_adm")
        admitted = reclaim_running_orphan(repo, "job_adm", exec_command="echo NO", now=self._t0)
        self.assertEqual(admitted.error, "not_reclaimable")
        self.assertEqual(load_lifecycle(repo, "job_adm")["phase"], PHASE_ADMISSION)  # type: ignore[index]

        persist_lifecycle_phase(
            repo, "job_q", PHASE_ADMISSION, goal="queued", receipt_id="tb_rcpt_q", execution_substrate=SUBSTRATE_LOCAL
        )
        persist_lifecycle_phase(
            repo, "job_q", PHASE_QUEUED, receipt_id="tb_rcpt_q", execution_substrate=SUBSTRATE_LOCAL
        )
        queued = reclaim_running_orphan(
            repo, "job_q", exec_command="echo NO", now=self._t0 + timedelta(hours=1)
        )
        self.assertEqual(queued.error, "not_reclaimable")
        resumed = resume_queued_job(repo, "job_q", exec_command="echo QUEUED_STILL")
        self.assertEqual(resumed.outcome, OUTCOME_COMPLETED)
        loaded_q = load_lifecycle(repo, "job_q")
        assert loaded_q is not None
        self.assertEqual(orphan_reclaim_count(loaded_q["transitions"]), 0)
        self.assertTrue(any(t.get("kind") == RESUME_CLAIM_KIND for t in loaded_q["transitions"]))

        persist_lifecycle_phase(
            repo, "job_term", PHASE_ADMISSION, goal="t", receipt_id="tb_rcpt_term"
        )
        persist_lifecycle_phase(
            repo, "job_term", PHASE_COMPLETED, receipt_id="tb_rcpt_term", result={"ok": True}
        )
        terminal = reclaim_running_orphan(repo, "job_term", exec_command="echo NO", now=self._t0)
        self.assertEqual(terminal.error, "not_reclaimable")
        self.assertEqual(load_lifecycle(repo, "job_term")["phase"], PHASE_COMPLETED)  # type: ignore[index]

        Repository(self._repo_path).create_job(job_id="job_bad", metadata={"governed_lifecycle": "nope"})
        with mock.patch(
            "thinkbox.lifecycle_harden.recover_corrupt_lifecycle_blob",
            wraps=recover_corrupt_lifecycle_blob,
        ) as recover:
            corrupt = reclaim_running_orphan(
                open_lifecycle_repo(self._repo_path),
                "job_bad",
                exec_command="echo NO",
                now=self._t0,
            )
            recover.assert_not_called()
        self.assertEqual(corrupt.error, "not_loadable")
        snap = Repository(self._repo_path).job_status("job_bad")
        assert snap is not None
        self.assertEqual(snap["metadata"]["governed_lifecycle"], "nope")

    def test_public_lifecycle_blob_omits_command_and_token(self) -> None:
        lease = issue_lease(now=self._t0, timeout_seconds=1)
        self._plant_running("job_redact", lease)
        command = "echo ORPHAN_SECRET_CMD"
        reclaim_running_orphan(
            open_lifecycle_repo(self._repo_path),
            "job_redact",
            exec_command=command,
            now=self._t0 + timedelta(seconds=2),
        )
        loaded = load_lifecycle(open_lifecycle_repo(self._repo_path), "job_redact")
        assert loaded is not None
        public = json.dumps({"transitions": loaded["transitions"], "result": loaded.get("result")})
        self.assertNotIn(command, public)
        self.assertNotIn("governance_token", public)
        self.assertNotIn("exec_command", public)

    def test_resume_claim_lease_is_ownership_not_timestamp(self) -> None:
        repo = open_lifecycle_repo(self._repo_path)
        persist_lifecycle_phase(
            repo,
            "job_own",
            PHASE_ADMISSION,
            goal="own",
            receipt_id="tb_rcpt_own",
            execution_substrate=SUBSTRATE_LOCAL,
        )
        persist_lifecycle_phase(
            repo, "job_own", PHASE_QUEUED, receipt_id="tb_rcpt_own", execution_substrate=SUBSTRATE_LOCAL
        )
        resume_queued_job(repo, "job_own", exec_command="echo OWN")
        loaded = load_lifecycle(repo, "job_own")
        assert loaded is not None
        claim = next(t for t in loaded["transitions"] if t.get("kind") == RESUME_CLAIM_KIND)
        self.assertTrue(claim["lease_id"])
        self.assertTrue(claim["lease_expires_at"])
        self.assertNotEqual(claim["lease_id"], claim["lease_started_at"])

    def test_does_not_open_second_receipt(self) -> None:
        lease = issue_lease(now=self._t0, timeout_seconds=1)
        self._plant_running("job_rcpt", lease)
        with mock.patch("backend.api.v1.run_receipts.begin_http_run_receipt") as opened:
            result = reclaim_running_orphan(
                open_lifecycle_repo(self._repo_path),
                "job_rcpt",
                exec_command="echo RCPT",
                now=self._t0 + timedelta(seconds=2),
            )
            opened.assert_not_called()
        self.assertEqual(result.receipt_id, "tb_rcpt_reclaim_1")


if __name__ == "__main__":
    unittest.main()
