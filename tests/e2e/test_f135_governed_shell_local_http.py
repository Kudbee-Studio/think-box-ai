"""Hermetic HTTP e2e: governed POST /api/v1/run shell path (explicit local substrate).

Exercises FastAPI router + admission + background shell task + LocalExecutionAdapter
+ Think Job status/receipt surfaces. No network, no Upstash live calls.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest import mock

from thinkbox.execution_adapter import _sha256_file
from thinkbox.governed_job_execution import SUBSTRATE_LOCAL, SUBSTRATE_UPSTASH_BOX
from thinkbox.local_execution_adapter import LOCAL_PROVIDER

from tests.e2e.api_run_hermetic import (
    auth_headers,
    drain_background_tasks,
    hermetic_run_client,
    run_payload,
)
from tests.e2e.hermetic_scaffold import assert_hermetic_blob_has_no_secrets

_SHELL_ECHO_MARKER = "THINKBOX_HTTP_SHELL_E2E"
_DEFAULT_ARTIFACT_NAME = "governed_exec.json"


class TestGovernedShellLocalHttp(unittest.TestCase):
    def test_local_shell_admitted_executes_with_receipt_evidence(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.post(
                "/api/v1/run",
                json=run_payload(
                    "governed shell local e2e",
                    execution_substrate=SUBSTRATE_LOCAL,
                    exec_command=f"echo {_SHELL_ECHO_MARKER}",
                ),
                headers=auth_headers(),
            )
            self.assertEqual(r.status_code, 200, r.text)
            body = r.json()
            engine_id = body["engine_id"]
            self.assertTrue(engine_id)
            receipt_id = body["summary"]["receipt_id"]
            self.assertTrue(receipt_id)
            self.assertTrue(body["summary"].get("governed"))

            drain_background_tasks()

            status = client.get(
                f"/api/v1/run/job/{engine_id}/status",
                headers=auth_headers(),
            )
            self.assertEqual(status.status_code, 200)
            status_body = status.json()
            self.assertEqual(status_body["status"], "completed")
            self.assertTrue(status_body["poll"]["terminal"])

            result = status_body.get("result") or {}
            self.assertTrue(result.get("governed_shell"))
            self.assertEqual(result.get("execution_substrate"), SUBSTRATE_LOCAL)
            self.assertEqual(result.get("adapter_provider"), LOCAL_PROVIDER)

            proof = result.get("execution_proof") or {}
            self.assertEqual(proof.get("provider"), LOCAL_PROVIDER)
            self.assertEqual(proof.get("status"), "COMPLETED")
            self.assertTrue(proof.get("verified"))
            self.assertFalse(proof.get("live_verified"))
            self.assertFalse(proof.get("live_api_called"))
            self.assertTrue(proof.get("checkpoint_id"))
            artifact_hash = proof.get("artifact_hash")
            self.assertTrue(artifact_hash)
            execution_id = proof.get("execution_id")
            self.assertTrue(execution_id)

            repo_root = Path(".").resolve()
            artifact_path = (
                repo_root
                / ".thinkbox"
                / "artifacts"
                / f"{execution_id}-{_DEFAULT_ARTIFACT_NAME}"
            )
            self.assertTrue(artifact_path.is_file(), f"missing artifact {artifact_path}")
            self.assertEqual(_sha256_file(artifact_path), artifact_hash)

            receipt_read = client.get(
                f"/api/v1/run/receipt/{receipt_id}",
                headers=auth_headers(),
            )
            self.assertEqual(receipt_read.status_code, 200)
            assert_hermetic_blob_has_no_secrets(json.dumps(status_body))

    def test_paired_substrate_fields_422_when_only_one_set(self) -> None:
        with hermetic_run_client() as (client, _):
            only_substrate = client.post(
                "/api/v1/run",
                json=run_payload(
                    "substrate only",
                    execution_substrate=SUBSTRATE_LOCAL,
                ),
                headers=auth_headers(),
            )
            self.assertEqual(only_substrate.status_code, 422)
            self.assertEqual(
                only_substrate.json()["detail"]["error"],
                "exec_command_and_substrate_required_together",
            )

            only_command = client.post(
                "/api/v1/run",
                json=run_payload(
                    "command only",
                    exec_command="echo nope",
                ),
                headers=auth_headers(),
            )
            self.assertEqual(only_command.status_code, 422)
            self.assertEqual(
                only_command.json()["detail"]["error"],
                "exec_command_and_substrate_required_together",
            )

    def test_upstash_box_without_credentials_fails_not_local(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with hermetic_run_client() as (client, _):
                r = client.post(
                    "/api/v1/run",
                    json=run_payload(
                        "upstash not configured",
                        execution_substrate=SUBSTRATE_UPSTASH_BOX,
                        exec_command="echo remote",
                    ),
                    headers=auth_headers(),
                )
                self.assertEqual(r.status_code, 200)
                engine_id = r.json()["engine_id"]
                drain_background_tasks()

                status = client.get(
                    f"/api/v1/run/job/{engine_id}/status",
                    headers=auth_headers(),
                )
                self.assertEqual(status.status_code, 200)
                status_body = status.json()
                self.assertEqual(status_body["status"], "failed")
                result = status_body.get("result") or {}
                self.assertEqual(result.get("error"), "remote_not_configured")
                self.assertNotEqual(result.get("adapter_provider"), LOCAL_PROVIDER)
                self.assertNotIn("execution_proof", result)


if __name__ == "__main__":
    unittest.main()
