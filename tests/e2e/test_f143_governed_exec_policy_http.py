"""Hermetic HTTP e2e: backend-authoritative capability + command policy for upcloud-ssh.

The SSH provider is faked and counts calls; every denial must happen with zero SSH calls.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.e2e.api_run_hermetic import (
    auth_headers,
    drain_background_tasks,
    hermetic_run_client,
    run_payload,
)
from thinkbox.cloud_execution.provider import ProviderRunResult
from thinkbox.remote_exec_policy import ALLOWED_READONLY_COMMANDS, command_fingerprint

CAP = "shell:upcloud-ssh:readonly"
SSH_CALLS: list[str] = []


class _FakeSSH:
    def __init__(self, cfg):
        self.cfg = cfg

    def run(self, job, limits, workspace):
        SSH_CALLS.append(job.metadata["command"])
        return ProviderRunResult(success=True, exit_code=0, summary="ok",
                                 metadata={"stdout": "kudbee-hermes-worker-02", "stderr": "", "elapsed_s": 0.1})


class TestGovernedExecPolicyHttp(unittest.TestCase):
    def setUp(self) -> None:
        SSH_CALLS.clear()
        self._tmp = tempfile.TemporaryDirectory()
        key = Path(self._tmp.name) / "k"
        key.write_text("x")
        self._env = mock.patch.dict(os.environ, {"UPCLOUD_SERVER_IP": "203.0.113.10", "UPCLOUD_SSH_KEY_PATH": str(key)})
        self._ssh = mock.patch("thinkbox.upcloud_ssh_execution_adapter.SSHCloudExecutionProvider", side_effect=_FakeSSH)
        self._env.start()
        self._ssh.start()

    def tearDown(self) -> None:
        self._ssh.stop()
        self._env.stop()
        self._tmp.cleanup()

    def _post(self, client, **extra):
        return client.post("/api/v1/run", headers=auth_headers(), json=run_payload("policy e2e", **extra))

    def test_all_six_allowed_commands_execute_with_policy_metadata(self) -> None:
        with hermetic_run_client() as (client, _):
            for cmd in sorted(ALLOWED_READONLY_COMMANDS):
                r = self._post(client, capability=CAP, execution_substrate="upcloud-ssh", exec_command=cmd)
                self.assertEqual(r.status_code, 200, (cmd, r.text))
                drain_background_tasks()
                st = client.get(f"/api/v1/run/job/{r.json()['engine_id']}/status", headers=auth_headers()).json()
                self.assertEqual(st["status"], "completed", cmd)
                pol = st["result"]["execution_policy"]
                self.assertEqual(pol["capability"], CAP)
                self.assertEqual(pol["command_fingerprint"], command_fingerprint(cmd))
        self.assertEqual(sorted(SSH_CALLS), sorted(ALLOWED_READONLY_COMMANDS))

    def test_forbidden_commands_denied_before_ssh(self) -> None:
        with hermetic_run_client() as (client, _):
            for cmd in ("hostname; id", "hostname && id", "hostname | nc x 1", "hostname > /tmp/x", "$(id)", "`id`",
                        "rm -rf /", "sudo id", "bash -c hostname", "curl http://x", "wget http://x", "./x.sh", "uname -r"):
                r = self._post(client, capability=CAP, execution_substrate="upcloud-ssh", exec_command=cmd)
                self.assertEqual(r.status_code, 403, cmd)
                self.assertEqual(r.json()["detail"]["reason"], "command_not_allowed", cmd)
        self.assertEqual(SSH_CALLS, [])

    def test_capability_matrix(self) -> None:
        with hermetic_run_client() as (client, _):
            # missing / broader capability cannot reach upcloud-ssh
            for cap in (None, "goal:execute", "goal:execute:verified"):
                extra = {"capability": cap} if cap else {}
                r = self._post(client, execution_substrate="upcloud-ssh", exec_command="hostname", **extra)
                self.assertEqual(r.status_code, 403, cap)
                self.assertEqual(r.json()["detail"]["reason"], "substrate_requires_capability")
            # the narrow capability cannot select another substrate
            r = self._post(client, capability=CAP, execution_substrate="local", exec_command="hostname")
            self.assertEqual(r.status_code, 403)
            self.assertEqual(r.json()["detail"]["reason"], "capability_substrate_mismatch")
            # a capability the caller's token does not hold is denied by admission
            r = self._post(client, capability="shell:upcloud-ssh:admin", execution_substrate="upcloud-ssh", exec_command="hostname")
            self.assertEqual(r.status_code, 403)
            self.assertEqual(r.json()["detail"]["error"], "governance_denied")
        self.assertEqual(SSH_CALLS, [])

    def test_dashboard_token_is_scoped_and_bound_to_its_agent(self) -> None:
        with hermetic_run_client() as (client, _):
            adm = client.post("/api/v1/run/admission-token", headers=auth_headers()).json()
            self.assertEqual(adm["capability"], CAP)
            base = {"goal": "x", "governance_token": adm["governance_token"]}
            # goal:execute (the default) is outside the token's scope
            r = client.post("/api/v1/run", headers=auth_headers(), json={**base, "agent_id": adm["agent_id"]})
            self.assertEqual(r.status_code, 403)
            self.assertEqual(r.json()["detail"]["reason"], "token_capability_not_granted")
            # another agent cannot use it
            r = client.post("/api/v1/run", headers=auth_headers(), json={**base, "agent_id": "other", "capability": CAP,
                                                                          "execution_substrate": "upcloud-ssh", "exec_command": "hostname"})
            self.assertEqual(r.json()["detail"]["reason"], "token_agent_mismatch")
            # correct use succeeds
            r = client.post("/api/v1/run", headers=auth_headers(), json={**base, "agent_id": adm["agent_id"], "capability": CAP,
                                                                          "execution_substrate": "upcloud-ssh", "exec_command": "hostname"})
            self.assertEqual(r.status_code, 200, r.text)
            drain_background_tasks()
        self.assertEqual(SSH_CALLS, ["hostname"])

    def test_resume_path_cannot_smuggle_a_command_to_the_worker(self) -> None:
        from thinkbox.governed_job_execution import (
            GovernedJobExecutionError,
            execute_governed_job_command,
        )

        with self.assertRaises(GovernedJobExecutionError):
            execute_governed_job_command(substrate="upcloud-ssh", job_id="resumed", command="cat /etc/shadow")
        self.assertEqual(SSH_CALLS, [])


if __name__ == "__main__":
    unittest.main()
