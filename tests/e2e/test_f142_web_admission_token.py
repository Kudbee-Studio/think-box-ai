"""Hermetic e2e: dashboard admission token (POST /api/v1/run/admission-token).

The token is what lets the dashboard bridge pass governed admission without the
browser ever holding a governance secret. Identity and capability are fixed
server-side; the endpoint sits behind the existing API-key middleware.
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
)
from thinkbox.cloud_execution.provider import ProviderRunResult
from thinkbox.governed_job_execution import SUBSTRATE_UPCLOUD_SSH


class _FakeSSH:
    def __init__(self, cfg):
        self.cfg = cfg

    def run(self, job, limits, workspace):
        return ProviderRunResult(
            success=True, exit_code=0, summary="kudbee-hermes-worker-02",
            metadata={"stdout": "kudbee-hermes-worker-02", "stderr": "", "elapsed_s": 0.1},
        )


class TestWebAdmissionToken(unittest.TestCase):
    def test_requires_api_key(self) -> None:
        with hermetic_run_client() as (client, _):
            self.assertIn(client.post("/api/v1/run/admission-token").status_code, (401, 403))
            self.assertIn(
                client.post("/api/v1/run/admission-token", headers={"X-API-Key": "wrong"}).status_code, (401, 403)
            )

    def test_identity_and_capability_are_server_fixed(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.post(
                "/api/v1/run/admission-token",
                headers=auth_headers(),
                json={"agent_id": "attacker", "capabilities": ["goal:execute:verified"], "ttl_seconds": 999999},
            )
            self.assertEqual(r.status_code, 200)
            body = r.json()
            self.assertEqual(body["agent_id"], "web-dashboard-agent")
            self.assertEqual(body["capability"], "goal:execute")
            self.assertEqual(body["expires_in_seconds"], 300.0)
            self.assertTrue(body["governance_token"])

    def test_token_admits_upcloud_ssh_run_end_to_end(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        key = Path(tmp.name) / "id_test"
        key.write_text("x")
        env = {"UPCLOUD_SERVER_IP": "203.0.113.10", "UPCLOUD_SSH_KEY_PATH": str(key)}
        with mock.patch.dict(os.environ, env), mock.patch(
            "thinkbox.upcloud_ssh_execution_adapter.SSHCloudExecutionProvider", side_effect=_FakeSSH
        ), hermetic_run_client() as (client, _):
            adm = client.post("/api/v1/run/admission-token", headers=auth_headers()).json()
            r = client.post(
                "/api/v1/run",
                headers=auth_headers(),
                json={
                    "goal": "dashboard remote exec: hostname",
                    "agent_id": adm["agent_id"],
                    "governance_token": adm["governance_token"],
                    "execution_substrate": SUBSTRATE_UPCLOUD_SSH,
                    "exec_command": "hostname",
                },
            )
            self.assertEqual(r.status_code, 200, r.text)
            drain_background_tasks()
            st = client.get(f"/api/v1/run/job/{r.json()['engine_id']}/status", headers=auth_headers()).json()
            self.assertEqual(st["status"], "completed")
            self.assertEqual(st["result"]["execution_proof"]["provider"], "upcloud-ssh")

    def test_token_cannot_be_used_for_another_agent_or_verified_capability(self) -> None:
        with hermetic_run_client() as (client, _):
            adm = client.post("/api/v1/run/admission-token", headers=auth_headers()).json()
            other = client.post(
                "/api/v1/run",
                headers=auth_headers(),
                json={"goal": "x", "agent_id": "someone-else", "governance_token": adm["governance_token"]},
            )
            self.assertEqual(other.status_code, 403)
            verified = client.post(
                "/api/v1/run",
                headers=auth_headers(),
                json={
                    "goal": "x", "agent_id": adm["agent_id"], "governance_token": adm["governance_token"],
                    "capability": "goal:execute:verified",
                },
            )
            self.assertEqual(verified.status_code, 403)


if __name__ == "__main__":
    unittest.main()
