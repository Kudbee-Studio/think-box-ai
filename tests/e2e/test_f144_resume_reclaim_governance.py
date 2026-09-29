"""Resume and reclaim must not be a governance bypass.

Classification: hermetic. Resume is exercised over real HTTP through the real ``api_v1_router``
(auth middleware, admission, policy, lifecycle store); reclaim is exercised directly because it has
no HTTP route (asserted below). The SSH provider is faked and *counts calls*: every denial must
happen with zero SSH calls and must leave the job untouched.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

from tests.e2e.api_run_hermetic import auth_headers, hermetic_run_client
from thinkbox.cloud_execution.provider import ProviderRunResult
from thinkbox.execution_authorization import authorization_record, check_bound_execution
from thinkbox.governed_execution_lifecycle import (
    PHASE_ADMISSION,
    PHASE_QUEUED,
    PHASE_RUNNING,
    load_lifecycle,
    open_lifecycle_repo,
    persist_lifecycle_phase,
)
from thinkbox.lifecycle_lease import issue_lease
from thinkbox.lifecycle_reclaim import reclaim_running_orphan
from thinkbox.lifecycle_resume import RESUME_CLAIM_KIND

CAP = "shell:upcloud-ssh:readonly"
AGENT = "web-dashboard-agent"
SSH_CALLS: list[str] = []


class _FakeSSH:
    def __init__(self, cfg):
        self.cfg = cfg

    def run(self, job, limits, workspace):
        SSH_CALLS.append(job.metadata["command"])
        return ProviderRunResult(success=True, exit_code=0, summary="ok",
                                 metadata={"stdout": "kudbee-hermes-worker-02", "stderr": "", "elapsed_s": 0.1})


def _git_repo(path: Path) -> None:
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "config", "user.name", "T"], ["git", "config", "user.email", "t@e.x"],
                ["git", "commit", "-q", "--allow-empty", "-m", "i"]):
        subprocess.run(cmd, cwd=str(path), check=True)


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        SSH_CALLS.clear()
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.repo_path = root / "repo"
        self.repo_path.mkdir()
        _git_repo(self.repo_path)
        key = root / "k"
        key.write_text("x")
        self._patches = [
            mock.patch.dict(os.environ, {"THINKBOX_LIFECYCLE_WORKTREE": str(self.repo_path), "UPCLOUD_SERVER_IP": "203.0.113.10",
                                         "UPCLOUD_SSH_KEY_PATH": str(key)}),
            mock.patch("thinkbox.upcloud_ssh_execution_adapter.SSHCloudExecutionProvider", side_effect=_FakeSSH),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self) -> None:
        for p in reversed(self._patches):
            p.stop()
        self._tmp.cleanup()

    def seed_queued(self, job_id: str, *, command: str | None = "hostname", agent: str = AGENT, capability: str = CAP,
                    substrate: str = "upcloud-ssh", persisted_substrate: str | None = None) -> None:
        binding = None if command is None else authorization_record(
            agent_id=agent, capability=capability, execution_substrate=substrate, exec_command=command)
        repo = open_lifecycle_repo(self.repo_path)
        sub = persisted_substrate or substrate
        persist_lifecycle_phase(repo, job_id, PHASE_ADMISSION, goal="dashboard remote exec", receipt_id=f"tb_rcpt_{job_id}",
                                experiment_id="tb_exp", session_id="tb_sess", execution_substrate=sub, admission_binding=binding)
        persist_lifecycle_phase(repo, job_id, PHASE_QUEUED, receipt_id=f"tb_rcpt_{job_id}", execution_substrate=sub)

    def phase(self, job_id: str) -> str:
        return str((load_lifecycle(open_lifecycle_repo(self.repo_path), job_id) or {}).get("phase"))


class TestResumeHttpGovernance(_Base):
    def _resume(self, client, job_id: str, **body):
        return client.post(f"/api/v1/run/job/{job_id}/resume", headers=auth_headers(), json=body)

    def _token(self, client) -> str:
        return client.post("/api/v1/run/admission-token", headers=auth_headers()).json()["governance_token"]

    def _denied(self, resp, job_id: str, *, error: str, reason: str | None = None) -> None:
        self.assertEqual(resp.status_code, 403, resp.text)
        detail = resp.json()["detail"]
        self.assertEqual(detail["error"], error)
        if reason:
            self.assertEqual(detail["reason"], reason)
        self.assertEqual(SSH_CALLS, [], "SSH must never be reached on a denial")
        self.assertEqual(self.phase(job_id), "queued", "a denied resume must not claim or mutate the job")

    def test_unauthenticated_resume_fails(self) -> None:
        with hermetic_run_client() as (client, _):
            self.seed_queued("job_unauth")
            r = client.post("/api/v1/run/job/job_unauth/resume", json={"exec_command": "hostname"})
            self.assertIn(r.status_code, (401, 403))
            self.assertEqual(SSH_CALLS, [])

    def test_missing_and_invalid_token_fail(self) -> None:
        with hermetic_run_client() as (client, _):
            self.seed_queued("job_tok")
            self._denied(self._resume(client, "job_tok", exec_command="hostname"), "job_tok", error="governance_denied")
            self._denied(self._resume(client, "job_tok", exec_command="hostname", governance_token="forged"), "job_tok",
                         error="governance_denied", reason="token_invalid_or_expired")

    def test_wrong_identity_fails(self) -> None:
        with hermetic_run_client() as (client, _):
            self.seed_queued("job_id")
            tok = self._token(client)
            self._denied(self._resume(client, "job_id", exec_command="hostname", governance_token=tok, agent_id="someone-else"),
                         "job_id", error="resume_denied", reason="agent_mismatch")

    def test_privileged_capability_cannot_be_substituted(self) -> None:
        with hermetic_run_client() as (client, _):
            self.seed_queued("job_priv")
            tok = self._token(client)
            self._denied(self._resume(client, "job_priv", exec_command="hostname", governance_token=tok, capability="goal:execute"),
                         "job_priv", error="resume_denied", reason="capability_mismatch")

    def test_another_identity_with_a_privileged_token_cannot_resume(self) -> None:
        from backend.api.v1.run_governed import get_api_run_governance

        with hermetic_run_client() as (client, _):
            self.seed_queued("job_other")
            other = get_api_run_governance().register_agent("other-agent", ["goal:execute", CAP])
            self._denied(self._resume(client, "job_other", exec_command="hostname", governance_token=other), "job_other",
                         error="governance_denied", reason="token_agent_mismatch")

    def test_caller_cannot_change_the_command(self) -> None:
        with hermetic_run_client() as (client, _):
            self.seed_queued("job_cmd")
            tok = self._token(client)
            # an allowed command, but not the one this job was admitted for
            self._denied(self._resume(client, "job_cmd", exec_command="uptime", governance_token=tok), "job_cmd",
                         error="resume_denied", reason="command_not_authorized_for_job")

    def test_forbidden_command_fails_before_ssh(self) -> None:
        with hermetic_run_client() as (client, _):
            for cmd in ("hostname; id", "rm -rf /", "$(id)", "bash -c hostname", ""):
                self.seed_queued(f"job_f{abs(hash(cmd)) % 10**6}", command=cmd if cmd else "hostname")
            tok = self._token(client)
            for cmd in ("hostname; id", "rm -rf /", "$(id)", "bash -c hostname"):
                jid = f"job_f{abs(hash(cmd)) % 10**6}"
                r = self._resume(client, jid, exec_command=cmd, governance_token=tok)
                self.assertEqual(r.status_code, 403, cmd)
                self.assertEqual(r.json()["detail"]["error"], "execution_policy_denied", cmd)
        self.assertEqual(SSH_CALLS, [])

    def test_job_without_admission_binding_cannot_be_resumed(self) -> None:
        with hermetic_run_client() as (client, _):
            self.seed_queued("job_legacy", command=None)
            tok = self._token(client)
            self._denied(self._resume(client, "job_legacy", exec_command="hostname", governance_token=tok), "job_legacy",
                         error="resume_denied", reason="missing_authorization_context")

    def test_authorized_resume_succeeds_and_preserves_provenance(self) -> None:
        with hermetic_run_client() as (client, _):
            self.seed_queued("job_ok")
            tok = self._token(client)
            r = self._resume(client, "job_ok", exec_command="hostname", governance_token=tok)
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(r.json()["outcome"], "completed")
            self.assertEqual(r.json()["receipt_id"], "tb_rcpt_job_ok")
            self.assertEqual(SSH_CALLS, ["hostname"])
            st = client.get("/api/v1/run/job/job_ok/status", headers=auth_headers()).json()
            res = st["result"]
            self.assertEqual(res["execution_proof"]["provider"], "upcloud-ssh")
            self.assertTrue(res["execution_attempt"]["lease_id"])
            binding = res["admission_binding"]
            self.assertEqual((binding["agent_id"], binding["capability"], binding["execution_substrate"], binding["policy_id"]),
                             (AGENT, CAP, "upcloud-ssh", "upcloud-ssh-readonly"))
            self.assertEqual(len(binding["command_fingerprint"]), 16)
            blob = str(st)
            self.assertNotIn(tok, blob)
            self.assertNotIn("governance_token", blob)
            # a second resume of the now-terminal job does not execute again
            again = self._resume(client, "job_ok", exec_command="hostname", governance_token=tok)
            self.assertEqual(again.status_code, 409)
            self.assertEqual(SSH_CALLS, ["hostname"])

    def test_reclaim_has_no_http_route(self) -> None:
        with hermetic_run_client() as (client, _):
            paths = {getattr(r, "path", "") for r in client.app.routes}
            flat = repr(sorted(paths))
            self.assertNotIn("reclaim", flat.lower())
            self.assertEqual(client.post("/api/v1/run/job/x/reclaim", headers=auth_headers(), json={}).status_code, 404)


class TestSubstrateBindingAndReclaim(_Base):
    def test_persisted_substrate_cannot_be_swapped_after_admission(self) -> None:
        from thinkbox.lifecycle_resume import resume_queued_job

        self.seed_queued("job_swap", substrate="upcloud-ssh", persisted_substrate="local")
        r = resume_queued_job(open_lifecycle_repo(self.repo_path), "job_swap", exec_command="hostname")
        self.assertEqual(r.outcome, "skipped")
        self.assertEqual(r.error, "authorization_substrate_mismatch")
        self.assertEqual(SSH_CALLS, [])
        self.assertEqual(self.phase("job_swap"), "queued")

    def _plant_running(self, job_id: str, lease, **kw) -> None:
        self.seed_queued(job_id, **kw)
        persist_lifecycle_phase(open_lifecycle_repo(self.repo_path), job_id, PHASE_RUNNING, goal="dashboard remote exec",
                                receipt_id=f"tb_rcpt_{job_id}", execution_substrate="upcloud-ssh", transition_kind=RESUME_CLAIM_KIND,
                                lease_id=lease.lease_id, lease_started_at=lease.started_at, lease_expires_at=lease.expires_at,
                                lease_timeout_seconds=lease.timeout_seconds)

    def test_reclaim_enforces_the_same_binding(self) -> None:
        from datetime import datetime, timezone

        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        later = t0 + timedelta(hours=1)
        for jid, kw, cmd, err in [
            ("rc_cmd", {}, "uptime", "command_not_authorized_for_job"),          # allowed by policy, not what was admitted
            ("rc_forbid", {}, "hostname; id", "command_not_authorized_for_job"),  # never matches the admitted fingerprint
            ("rc_legacy", {"command": None}, "hostname", "missing_authorization_context"),
        ]:
            lease = issue_lease(now=t0, timeout_seconds=1)
            self._plant_running(jid, lease, **kw)
            r = reclaim_running_orphan(open_lifecycle_repo(self.repo_path), jid, exec_command=cmd, now=later)
            self.assertEqual((r.outcome, r.error), ("skipped", err), jid)
            self.assertEqual(self.phase(jid), "running", "a refused reclaim must not take over the job")
        self.assertEqual(SSH_CALLS, [])

    def test_reclaim_of_the_admitted_command_still_works(self) -> None:
        from datetime import datetime, timezone

        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        lease = issue_lease(now=t0, timeout_seconds=1)
        self._plant_running("rc_ok", lease)
        r = reclaim_running_orphan(open_lifecycle_repo(self.repo_path), "rc_ok", exec_command="hostname", now=t0 + timedelta(hours=1))
        self.assertEqual(r.outcome, "completed", (r.error, r.outcome))
        self.assertEqual(SSH_CALLS, ["hostname"])
        res = (load_lifecycle(open_lifecycle_repo(self.repo_path), "rc_ok") or {}).get("result") or {}
        self.assertTrue(res.get("reclaimed"))
        self.assertEqual(res["admission_binding"]["capability"], CAP)

    def test_binding_is_immutable_and_pure_checks(self) -> None:
        from thinkbox.lifecycle_harden import LifecycleError

        self.seed_queued("job_imm")
        with self.assertRaises(LifecycleError) as ctx:
            persist_lifecycle_phase(open_lifecycle_repo(self.repo_path), "job_imm", PHASE_QUEUED, receipt_id="x",
                                    execution_substrate="upcloud-ssh",
                                    admission_binding=authorization_record(agent_id=AGENT, capability="goal:execute",
                                                                           execution_substrate="upcloud-ssh", exec_command="hostname"))
        self.assertEqual(ctx.exception.code, "admission_binding_immutable")
        good = authorization_record(agent_id=AGENT, capability=CAP, execution_substrate="upcloud-ssh", exec_command="hostname")
        self.assertTrue(check_bound_execution(good, execution_substrate="upcloud-ssh", exec_command="hostname").allowed)
        self.assertEqual(check_bound_execution(None, execution_substrate="upcloud-ssh", exec_command="hostname").reason,
                         "missing_authorization_context")
        self.assertEqual(check_bound_execution({**good, "capability": "goal:execute"}, execution_substrate="upcloud-ssh",
                                               exec_command="hostname").reason, "substrate_requires_capability")


if __name__ == "__main__":
    unittest.main()
