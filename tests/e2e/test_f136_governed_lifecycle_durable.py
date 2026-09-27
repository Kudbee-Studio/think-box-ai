"""Hermetic HTTP e2e: durable governed lifecycle survives dashboard/process reload."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

from thinkbox.dashboard_state import get_dashboard_state
from thinkbox.execution_adapter import _sha256_file
from thinkbox.governed_execution_lifecycle import (
    PHASE_ADMISSION,
    PHASE_COMPLETED,
    PHASE_FAILED,
    PHASE_QUEUED,
    PHASE_RUNNING,
    load_lifecycle,
    open_lifecycle_repo,
    terminal_evidence,
)
from thinkbox.governed_job_execution import SUBSTRATE_LOCAL, SUBSTRATE_UPSTASH_BOX
from thinkbox.local_execution_adapter import LOCAL_PROVIDER

from tests.e2e.api_run_hermetic import (
    auth_headers,
    drain_background_tasks,
    hermetic_run_client,
    run_payload,
)
from tests.e2e.hermetic_scaffold import assert_hermetic_blob_has_no_secrets


def _clear_dashboard_jobs() -> None:
    get_dashboard_state().think_jobs.clear()


class TestGovernedLifecycleDurableHttp(unittest.TestCase):
    def test_local_shell_status_survives_dashboard_clear(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.post(
                "/api/v1/run",
                json=run_payload(
                    "durable lifecycle local",
                    execution_substrate=SUBSTRATE_LOCAL,
                    exec_command="echo THINKBOX_LIFECYCLE_HTTP",
                ),
                headers=auth_headers(),
            )
            self.assertEqual(r.status_code, 200, r.text)
            engine_id = r.json()["engine_id"]
            receipt_id = r.json()["summary"]["receipt_id"]
            drain_background_tasks()

            loaded = load_lifecycle(open_lifecycle_repo(), engine_id)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            phases = [t["phase"] for t in loaded["transitions"]]
            for required in (
                PHASE_ADMISSION,
                PHASE_QUEUED,
                PHASE_RUNNING,
                PHASE_COMPLETED,
            ):
                self.assertIn(required, phases)

            _clear_dashboard_jobs()
            status = client.get(
                f"/api/v1/run/job/{engine_id}/status",
                headers=auth_headers(),
            )
            self.assertEqual(status.status_code, 200)
            body = status.json()
            self.assertEqual(body["status"], "completed")
            self.assertTrue(body["poll"]["terminal"])
            result = body.get("result") or {}
            self.assertTrue(result.get("governed_shell"))
            self.assertEqual(result.get("adapter_provider"), LOCAL_PROVIDER)
            proof = result.get("execution_proof") or {}
            self.assertTrue(proof.get("verified"))
            self.assertFalse(proof.get("live_verified"))

            evidence = terminal_evidence(loaded)
            self.assertEqual(evidence.receipt_id, receipt_id)
            self.assertTrue(evidence.checkpoint_id)
            artifact = Path(evidence.artifact_path)
            self.assertTrue(artifact.is_file())
            self.assertEqual(_sha256_file(artifact), evidence.artifact_hash)
            assert_hermetic_blob_has_no_secrets(status.text)

    def test_failed_remote_substrate_survives_reload_without_fallback(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with hermetic_run_client() as (client, _):
                r = client.post(
                    "/api/v1/run",
                    json=run_payload(
                        "durable remote fail",
                        execution_substrate=SUBSTRATE_UPSTASH_BOX,
                        exec_command="echo remote",
                    ),
                    headers=auth_headers(),
                )
                self.assertEqual(r.status_code, 200)
                engine_id = r.json()["engine_id"]
                drain_background_tasks()
                loaded = load_lifecycle(open_lifecycle_repo(), engine_id)
                self.assertIsNotNone(loaded)
                assert loaded is not None
                self.assertEqual(loaded["phase"], PHASE_FAILED)
                self.assertEqual(loaded.get("verdict"), "remote_not_configured")
                self.assertNotEqual(loaded.get("adapter_provider"), LOCAL_PROVIDER)

                _clear_dashboard_jobs()
                status = client.get(
                    f"/api/v1/run/job/{engine_id}/status",
                    headers=auth_headers(),
                )
                self.assertEqual(status.status_code, 200)
                body = status.json()
                self.assertEqual(body["status"], "failed")
                self.assertEqual((body.get("result") or {}).get("error"), "remote_not_configured")


if __name__ == "__main__":
    unittest.main()
