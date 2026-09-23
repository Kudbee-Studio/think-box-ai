"""PR #133 — governed HTTP run receipts + ExperimentManager persistence (hermetic)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from backend.api.v1.run_receipts import (
    get_http_run_persistence,
    set_persist_fail_hook,
)
from thinkbox.dashboard_state import DashboardCategory, DashboardEvent

from tests.e2e.api_run_hermetic import (
    auth_headers,
    drain_background_tasks,
    events_matching,
    hermetic_run_client,
    hermetic_run_client_real_engine,
    run_payload,
)
from tests.e2e.hermetic_scaffold import (
    assert_hermetic_blob_has_no_secrets,
    isolated_dashboard_state,
    subtask_spec,
    verify_dag_proof_file,
)


class TestPostRunReceiptImmediateResponse(unittest.TestCase):
    def test_post_returns_receipt_ids(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.post(
                "/api/v1/run",
                json=run_payload("receipt ids"),
                headers=auth_headers(),
            )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("receipt_id", body["summary"])
        self.assertIn("experiment_id", body["summary"])
        self.assertTrue(body["summary"]["session_id"])


class TestVerifiedRunReceiptPersistence(unittest.TestCase):
    def test_verified_run_persists_sqlite_and_proof(self) -> None:
        subtasks = [
            subtask_spec("compute", "add_small"),
            subtask_spec("compute", "mul_small", depends_on=[0]),
        ]
        with isolated_dashboard_state():
            with hermetic_run_client_real_engine() as (client, _):
                r = client.post(
                    "/api/v1/run",
                    json=run_payload(
                        "verified receipt",
                        verified=True,
                        model="hermetic-mock",
                        subtasks=subtasks,
                    ),
                    headers=auth_headers(),
                )
                self.assertEqual(r.status_code, 200)
                receipt_id = r.json()["summary"]["receipt_id"]
                engine_id = r.json()["engine_id"]
                drain_background_tasks()
                rec = client.get(f"/api/v1/run/receipt/{receipt_id}", headers=auth_headers())
                self.assertEqual(rec.status_code, 200)
                self.assertFalse(rec.json()["live_verified"])
                by_engine = client.get(
                    f"/api/v1/run/receipt/by-engine/{engine_id}",
                    headers=auth_headers(),
                )
                self.assertEqual(by_engine.status_code, 200)
                stack = get_http_run_persistence()
                proofs = list(stack.artifacts_dir.glob("dagpath_proof_*.json"))
                self.assertTrue(proofs, "expected DAG proof artifact on disk")
                proof = verify_dag_proof_file(proofs[0])
                self.assertIn("goal_experiment_id", proof)
                blob = json.dumps(rec.json()) + proofs[0].read_text(encoding="utf-8")
                assert_hermetic_blob_has_no_secrets(blob)


class TestReceiptPersistFailClosed(unittest.TestCase):
    def test_persist_failure_marks_job_failed(self) -> None:
        set_persist_fail_hook(False)
        subtasks = [subtask_spec("compute", "add_small")]
        try:
            with isolated_dashboard_state() as st:
                with hermetic_run_client_real_engine() as (client, _):
                    set_persist_fail_hook(True)
                    r = client.post(
                        "/api/v1/run",
                        json=run_payload(
                            "persist fail",
                            verified=True,
                            model="hermetic-mock",
                            subtasks=subtasks,
                        ),
                        headers=auth_headers(),
                    )
                    engine_id = r.json()["engine_id"]
                    drain_background_tasks()
                    job = st.think_jobs.get(engine_id)
                    self.assertIsNotNone(job)
                    assert job is not None
                    self.assertEqual(job.status, "failed")
                    self.assertEqual(job.phase, "receipt_persist_failed")
                    failed = events_matching(
                        st,
                        category=DashboardCategory.THINK_JOBS,
                        event_type=DashboardEvent.TASK_FAILED,
                    )
                    self.assertTrue(failed)
        finally:
            set_persist_fail_hook(False)


class TestGovernanceStatusReceiptFields(unittest.TestCase):
    def test_status_includes_receipt_counts(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.get("/api/v1/run/governance/status", headers=auth_headers())
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body.get("receipt_persistence"), "enabled")
        self.assertIn("receipt_recent_experiments", body)
        self.assertIn("receipt_snapshot", body)
        self.assertIn("engine_index_size", body["receipt_snapshot"])


if __name__ == "__main__":
    unittest.main()
