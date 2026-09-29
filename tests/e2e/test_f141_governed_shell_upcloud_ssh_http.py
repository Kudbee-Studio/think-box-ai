"""Hermetic HTTP e2e: governed POST /api/v1/run shell path on the ``upcloud-ssh`` substrate.

Router + admission + background shell task + UpCloudSSHExecutionAdapter + Think Job
status/receipt surfaces. The SSH provider is faked, so there is no network. The
live proof against the real worker is recorded separately in docs/CONTINUITY.md.
"""

from __future__ import annotations

import json
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
from tests.e2e.hermetic_scaffold import assert_hermetic_blob_has_no_secrets
from thinkbox.cloud_execution.provider import ProviderRunResult
from thinkbox.execution_adapter import _sha256_file
from thinkbox.governed_job_execution import SUBSTRATE_UPCLOUD_SSH
from thinkbox.upcloud_ssh_execution_adapter import UPCLOUD_SSH_PROVIDER

_WORKER_HOSTNAME = "kudbee-hermes-worker-02"
_ARTIFACT_NAME = "governed_exec.json"


class _FakeSSH:
    def __init__(self, cfg, *, exit_code=0, stdout=_WORKER_HOSTNAME, stderr=""):
        self.cfg, self.exit_code, self.stdout, self.stderr = cfg, exit_code, stdout, stderr

    def run(self, job, limits, workspace):
        return ProviderRunResult(
            success=self.exit_code == 0,
            exit_code=self.exit_code,
            summary=self.stdout if self.exit_code == 0 else self.stderr,
            metadata={"stdout": self.stdout, "stderr": self.stderr, "elapsed_s": 0.4},
        )


class TestGovernedShellUpcloudSshHttp(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.key = Path(self._tmp.name) / "id_test"
        self.key.write_text("not-a-real-key")
        self.env = {"UPCLOUD_SERVER_IP": "203.0.113.10", "UPCLOUD_SSH_KEY_PATH": str(self.key)}

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, client, command="hostname"):
        r = client.post(
            "/api/v1/run",
            json=run_payload("governed shell upcloud-ssh e2e", capability="shell:upcloud-ssh:readonly",
                             execution_substrate=SUBSTRATE_UPCLOUD_SSH, exec_command=command),
            headers=auth_headers(),
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        drain_background_tasks()
        status = client.get(f"/api/v1/run/job/{body['engine_id']}/status", headers=auth_headers())
        self.assertEqual(status.status_code, 200)
        return body, status.json()

    def test_upcloud_ssh_admitted_executes_with_receipt_evidence(self) -> None:
        with mock.patch.dict(os.environ, self.env), mock.patch(
            "thinkbox.upcloud_ssh_execution_adapter.SSHCloudExecutionProvider", side_effect=_FakeSSH
        ), hermetic_run_client() as (client, _):
            body, status = self._run(client)
            self.assertTrue(body["summary"].get("governed"))
            self.assertEqual(status["status"], "completed")
            result = status.get("result") or {}
            self.assertEqual(result.get("execution_substrate"), SUBSTRATE_UPCLOUD_SSH)
            self.assertEqual(result.get("adapter_provider"), UPCLOUD_SSH_PROVIDER)
            proof = result.get("execution_proof") or {}
            self.assertEqual(proof.get("provider"), UPCLOUD_SSH_PROVIDER)
            self.assertEqual(proof.get("status"), "COMPLETED")
            self.assertTrue(proof.get("verified"))
            self.assertTrue(proof.get("checkpoint_id"))
            self.assertTrue(proof.get("live_api_called"))
            self.assertFalse(proof.get("live_verified"))

            artifact_path = Path.cwd() / ".thinkbox" / "artifacts" / f"{proof['execution_id']}-{_ARTIFACT_NAME}"
            self.assertTrue(artifact_path.is_file(), f"missing artifact {artifact_path}")
            self.assertEqual(_sha256_file(artifact_path), proof.get("artifact_hash"))
            artifact = json.loads(artifact_path.read_text())
            self.assertEqual(artifact["stdout"], _WORKER_HOSTNAME)
            self.assertNotIn(str(self.key), artifact_path.read_text())

            receipt = client.get(f"/api/v1/run/receipt/{body['summary']['receipt_id']}", headers=auth_headers())
            self.assertEqual(receipt.status_code, 200)
            assert_hermetic_blob_has_no_secrets(json.dumps(status))

    def test_upcloud_ssh_without_config_fails_and_never_runs_locally(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True), hermetic_run_client() as (client, _):
            _, status = self._run(client, command="hostname")
            self.assertEqual(status["status"], "failed")
            self.assertEqual((status.get("result") or {}).get("error"), "remote_not_configured")

    def test_ssh_auth_failure_surfaces_as_failed_job(self) -> None:
        def deny(cfg):
            return _FakeSSH(cfg, exit_code=255, stdout="", stderr="Permission denied (publickey).")

        with mock.patch.dict(os.environ, self.env), mock.patch(
            "thinkbox.upcloud_ssh_execution_adapter.SSHCloudExecutionProvider", side_effect=deny
        ), hermetic_run_client() as (client, _):
            _, status = self._run(client)
            self.assertEqual(status["status"], "failed")
            proof = (status.get("result") or {}).get("execution_proof") or {}
            self.assertEqual(proof.get("status"), "SSH_FAILED")


if __name__ == "__main__":
    unittest.main()
