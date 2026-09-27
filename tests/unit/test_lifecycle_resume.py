"""Hermetic tests for durable QUEUED resume after process reload."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

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
from thinkbox.governed_job_execution import SUBSTRATE_LOCAL, SUBSTRATE_UPSTASH_BOX
from thinkbox.lifecycle_harden import recover_corrupt_lifecycle_blob
from thinkbox.lifecycle_resume import (
    OUTCOME_CAS_LOST,
    OUTCOME_COMPLETED,
    OUTCOME_INCOMPLETE,
    OUTCOME_SKIPPED,
    RESUME_CLAIM_KIND,
    RESUME_INCOMPLETE,
    resume_claim_count,
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


class TestLifecycleResume(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._repo_path = Path(self._tmp.name) / "repo"
        self._repo_path.mkdir()
        _make_git_repo(self._repo_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _queue(
        self,
        job_id: str,
        *,
        goal: str = "resume goal",
        receipt_id: str = "tb_rcpt_resume_1",
        substrate: str = SUBSTRATE_LOCAL,
    ) -> None:
        repo = open_lifecycle_repo(self._repo_path)
        persist_lifecycle_phase(
            repo,
            job_id,
            PHASE_ADMISSION,
            goal=goal,
            receipt_id=receipt_id,
            experiment_id="tb_exp_resume",
            session_id="tb_sess_resume",
            execution_substrate=substrate,
        )
        persist_lifecycle_phase(
            repo,
            job_id,
            PHASE_QUEUED,
            receipt_id=receipt_id,
            execution_substrate=substrate,
        )

    def test_reload_queued_resume_completes(self) -> None:
        self._queue("job_reload")
        reopened = open_lifecycle_repo(self._repo_path)
        result = resume_queued_job(
            reopened,
            "job_reload",
            exec_command="echo THINKBOX_QUEUED_RESUME",
        )
        self.assertEqual(result.outcome, OUTCOME_COMPLETED)
        self.assertTrue(result.claimed)
        self.assertTrue(result.executed)
        self.assertEqual(result.receipt_id, "tb_rcpt_resume_1")
        self.assertFalse(result.live_verified)
        loaded = load_lifecycle(open_lifecycle_repo(self._repo_path), "job_reload")
        assert loaded is not None
        phases = [t["phase"] for t in loaded["transitions"]]
        self.assertEqual(
            phases,
            [PHASE_ADMISSION, PHASE_QUEUED, PHASE_RUNNING, PHASE_COMPLETED],
        )
        self.assertEqual(resume_claim_count(loaded["transitions"]), 1)
        self.assertEqual(loaded["receipt_id"], "tb_rcpt_resume_1")
        self.assertTrue(loaded.get("artifact_path"))
        self.assertTrue(Path(loaded["artifact_path"]).is_file())
        record = lifecycle_to_status_record(loaded)
        self.assertEqual(record["lifecycle_phase"], PHASE_COMPLETED)
        self.assertFalse(record["resume_eligible"])
        public = loaded.get("result") or {}
        self.assertNotIn("exec_command", public)
        self.assertNotIn("command", public)
        self.assertNotIn("governance_token", public)

    def test_sequential_second_resume_does_not_execute(self) -> None:
        self._queue("job_once")
        repo = open_lifecycle_repo(self._repo_path)
        first = resume_queued_job(repo, "job_once", exec_command="echo FIRST")
        second = resume_queued_job(repo, "job_once", exec_command="echo SECOND")
        self.assertEqual(first.outcome, OUTCOME_COMPLETED)
        self.assertEqual(second.outcome, OUTCOME_SKIPPED)
        self.assertFalse(second.executed)
        loaded = load_lifecycle(repo, "job_once")
        assert loaded is not None
        self.assertEqual(resume_claim_count(loaded["transitions"]), 1)

    def test_concurrent_resume_single_claim(self) -> None:
        self._queue("job_race")
        results: list[object] = []

        def _run() -> None:
            results.append(
                resume_queued_job(
                    open_lifecycle_repo(self._repo_path),
                    "job_race",
                    exec_command="echo RACE",
                )
            )

        threads = [threading.Thread(target=_run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        outcomes = {item.outcome for item in results}  # type: ignore[attr-defined]
        self.assertIn(OUTCOME_COMPLETED, outcomes)
        self.assertTrue(outcomes <= {OUTCOME_COMPLETED, OUTCOME_CAS_LOST, OUTCOME_SKIPPED})
        executed = sum(1 for item in results if getattr(item, "executed", False))
        self.assertEqual(executed, 1)
        loaded = load_lifecycle(open_lifecycle_repo(self._repo_path), "job_race")
        assert loaded is not None
        self.assertEqual(resume_claim_count(loaded["transitions"]), 1)

    def test_admission_only_never_executes(self) -> None:
        repo = open_lifecycle_repo(self._repo_path)
        persist_lifecycle_phase(
            repo, "job_adm", PHASE_ADMISSION, goal="g", receipt_id="tb_rcpt_adm"
        )
        result = resume_queued_job(repo, "job_adm", exec_command="echo NO")
        self.assertEqual(result.outcome, OUTCOME_SKIPPED)
        self.assertFalse(result.executed)
        loaded = load_lifecycle(repo, "job_adm")
        assert loaded is not None
        self.assertEqual(loaded["phase"], PHASE_ADMISSION)
        self.assertEqual(resume_claim_count(loaded["transitions"]), 0)

    def test_running_never_resumes(self) -> None:
        self._queue("job_run")
        repo = open_lifecycle_repo(self._repo_path)
        persist_lifecycle_phase(repo, "job_run", PHASE_RUNNING, receipt_id="tb_rcpt_resume_1")
        result = resume_queued_job(repo, "job_run", exec_command="echo NO")
        self.assertEqual(result.outcome, OUTCOME_SKIPPED)
        loaded = load_lifecycle(repo, "job_run")
        assert loaded is not None
        self.assertEqual(loaded["phase"], PHASE_RUNNING)

    def test_terminal_never_resumes(self) -> None:
        repo = open_lifecycle_repo(self._repo_path)
        persist_lifecycle_phase(
            repo, "job_term", PHASE_ADMISSION, goal="g", receipt_id="tb_rcpt_term"
        )
        persist_lifecycle_phase(
            repo,
            "job_term",
            PHASE_COMPLETED,
            receipt_id="tb_rcpt_term",
            result={"ok": True},
        )
        result = resume_queued_job(repo, "job_term", exec_command="echo NO")
        self.assertEqual(result.outcome, OUTCOME_SKIPPED)
        loaded = load_lifecycle(repo, "job_term")
        assert loaded is not None
        self.assertEqual(loaded["phase"], PHASE_COMPLETED)

    def test_missing_inputs_fail_closed_no_artifact(self) -> None:
        repo = open_lifecycle_repo(self._repo_path)
        persist_lifecycle_phase(repo, "job_miss", PHASE_ADMISSION, execution_substrate=SUBSTRATE_LOCAL)
        persist_lifecycle_phase(repo, "job_miss", PHASE_QUEUED, execution_substrate=SUBSTRATE_LOCAL)
        result = resume_queued_job(repo, "job_miss", exec_command="echo X")
        self.assertEqual(result.outcome, OUTCOME_INCOMPLETE)
        self.assertEqual(result.verdict, RESUME_INCOMPLETE)
        loaded = load_lifecycle(repo, "job_miss")
        assert loaded is not None
        self.assertEqual(loaded["phase"], PHASE_FAILED)
        self.assertFalse(loaded.get("artifact_path"))

        self._queue("job_nocmd")
        missing_cmd = resume_queued_job(open_lifecycle_repo(self._repo_path), "job_nocmd")
        self.assertEqual(missing_cmd.outcome, OUTCOME_INCOMPLETE)
        self.assertEqual(missing_cmd.error, "missing_command")
        after = load_lifecycle(open_lifecycle_repo(self._repo_path), "job_nocmd")
        assert after is not None
        self.assertFalse(after.get("artifact_path"))

    def test_does_not_read_command_from_public_result(self) -> None:
        self._queue("job_leak")
        job_file = self._repo_path / ".thinkbox" / "jobs" / "job_leak.json"
        data = json.loads(job_file.read_text(encoding="utf-8"))
        life = data["metadata"]["governed_lifecycle"]
        life["result"] = {"exec_command": "echo LEAKED", "governance_token": "secret"}
        job_file.write_text(json.dumps(data), encoding="utf-8")
        result = resume_queued_job(open_lifecycle_repo(self._repo_path), "job_leak")
        self.assertEqual(result.outcome, OUTCOME_INCOMPLETE)
        self.assertEqual(result.error, "missing_command")

    def test_unconfigured_upstash_fails_without_local(self) -> None:
        self._queue("job_remote", substrate=SUBSTRATE_UPSTASH_BOX)
        with mock.patch.dict(os.environ, {}, clear=True):
            result = resume_queued_job(
                open_lifecycle_repo(self._repo_path),
                "job_remote",
                exec_command="echo remote",
            )
        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.error, "remote_not_configured")
        loaded = load_lifecycle(open_lifecycle_repo(self._repo_path), "job_remote")
        assert loaded is not None
        self.assertEqual(loaded["phase"], PHASE_FAILED)
        self.assertEqual(loaded.get("verdict"), "remote_not_configured")
        self.assertNotEqual(loaded.get("adapter_provider"), LOCAL_PROVIDER)
        self.assertFalse(loaded.get("live_verified"))

    def test_corrupt_blob_skips_without_h13(self) -> None:
        Repository(self._repo_path).create_job(
            job_id="job_bad",
            metadata={"governed_lifecycle": "nope"},
        )
        with mock.patch(
            "thinkbox.lifecycle_harden.recover_corrupt_lifecycle_blob",
            wraps=recover_corrupt_lifecycle_blob,
        ) as recover:
            result = resume_queued_job(
                open_lifecycle_repo(self._repo_path),
                "job_bad",
                exec_command="echo NO",
            )
            recover.assert_not_called()
        self.assertEqual(result.outcome, OUTCOME_SKIPPED)
        self.assertFalse(result.executed)
        loaded = load_lifecycle(open_lifecycle_repo(self._repo_path), "job_bad")
        self.assertIsNone(loaded)
        snap = Repository(self._repo_path).job_status("job_bad")
        assert snap is not None
        self.assertEqual(snap["metadata"]["governed_lifecycle"], "nope")

    def test_queued_status_fields_before_resume(self) -> None:
        self._queue("job_stat")
        loaded = load_lifecycle(open_lifecycle_repo(self._repo_path), "job_stat")
        assert loaded is not None
        record = lifecycle_to_status_record(loaded)
        self.assertEqual(record["lifecycle_phase"], PHASE_QUEUED)
        self.assertTrue(record["resume_eligible"])

    def test_does_not_open_second_receipt(self) -> None:
        self._queue("job_rcpt")
        with mock.patch("backend.api.v1.run_receipts.begin_http_run_receipt") as opened:
            result = resume_queued_job(
                open_lifecycle_repo(self._repo_path),
                "job_rcpt",
                exec_command="echo RCPT",
            )
            opened.assert_not_called()
        self.assertEqual(result.receipt_id, "tb_rcpt_resume_1")
        loaded = load_lifecycle(open_lifecycle_repo(self._repo_path), "job_rcpt")
        assert loaded is not None
        self.assertEqual(loaded["receipt_id"], "tb_rcpt_resume_1")

    def test_worktree_mismatch_fail_closed(self) -> None:
        self._queue("job_wt")
        job_file = self._repo_path / ".thinkbox" / "jobs" / "job_wt.json"
        data = json.loads(job_file.read_text(encoding="utf-8"))
        data["path"] = str(Path(self._tmp.name) / "other-tree")
        job_file.write_text(json.dumps(data), encoding="utf-8")
        result = resume_queued_job(
            open_lifecycle_repo(self._repo_path),
            "job_wt",
            exec_command="echo WT",
        )
        self.assertEqual(result.outcome, OUTCOME_INCOMPLETE)
        self.assertEqual(result.error, "worktree_mismatch")


class TestLifecycleResumeHttp(unittest.TestCase):
    def test_http_resume_reuses_receipt_and_status(self) -> None:
        from tests.e2e.api_run_hermetic import auth_headers, hermetic_run_client

        tmp = tempfile.TemporaryDirectory()
        repo_path = Path(tmp.name) / "repo"
        repo_path.mkdir()
        _make_git_repo(repo_path)
        try:
            with mock.patch.dict(os.environ, {"THINKBOX_LIFECYCLE_WORKTREE": str(repo_path)}):
                repo = open_lifecycle_repo(repo_path)
                persist_lifecycle_phase(
                    repo,
                    "engine_http_resume1",
                    PHASE_ADMISSION,
                    goal="http resume",
                    receipt_id="tb_rcpt_http_resume",
                    execution_substrate=SUBSTRATE_LOCAL,
                )
                persist_lifecycle_phase(
                    repo,
                    "engine_http_resume1",
                    PHASE_QUEUED,
                    receipt_id="tb_rcpt_http_resume",
                    execution_substrate=SUBSTRATE_LOCAL,
                )
                with hermetic_run_client() as (client, _):
                    queued = load_lifecycle(open_lifecycle_repo(repo_path), "engine_http_resume1")
                    assert queued is not None
                    record = lifecycle_to_status_record(queued)
                    self.assertTrue(record["resume_eligible"])
                    response = client.post(
                        "/api/v1/run/job/engine_http_resume1/resume",
                        json={"exec_command": "echo HTTP_RESUME"},
                        headers=auth_headers(),
                    )
                    self.assertEqual(response.status_code, 200, response.text)
                    body = response.json()
                    self.assertEqual(body["outcome"], OUTCOME_COMPLETED)
                    self.assertEqual(body["receipt_id"], "tb_rcpt_http_resume")
                    self.assertFalse(body["live_verified"])
                    status = client.get(
                        "/api/v1/run/job/engine_http_resume1/status",
                        headers=auth_headers(),
                    )
                    self.assertEqual(status.status_code, 200)
                    payload = status.json()
                    self.assertEqual(payload["lifecycle_phase"], PHASE_COMPLETED)
                    self.assertFalse(payload["resume_eligible"])
                    result = payload.get("result") or {}
                    self.assertNotIn("exec_command", result)
                    self.assertNotIn("governance_token", result)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
