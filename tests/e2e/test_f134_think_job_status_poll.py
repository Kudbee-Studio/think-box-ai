"""PR #134 — Think Job status polling + receipt-linked dashboard card (hermetic)."""

from __future__ import annotations

import json
import unittest

from thinkbox.dashboard_state import DashboardCategory, DashboardEvent

from tests.e2e.api_run_hermetic import (
    auth_headers,
    drain_background_tasks,
    events_matching,
    hermetic_run_client,
    run_payload,
)
from tests.e2e.hermetic_scaffold import assert_hermetic_blob_has_no_secrets, isolated_dashboard_state


class TestThinkJobStatusPoll(unittest.TestCase):
    def test_post_then_poll_until_completed(self) -> None:
        with isolated_dashboard_state():
            with hermetic_run_client() as (client, _):
                r = client.post(
                    "/api/v1/run",
                    json=run_payload("poll status"),
                    headers=auth_headers(),
                )
                self.assertEqual(r.status_code, 200)
                body = r.json()
                engine_id = body["engine_id"]
                receipt_id = body["summary"]["receipt_id"]
                running = client.get(
                    f"/api/v1/run/job/{engine_id}/status",
                    headers=auth_headers(),
                )
                self.assertEqual(running.status_code, 200)
                self.assertIn(running.json()["status"], ("running", "started", "completed"))
                drain_background_tasks()
                done = client.get(
                    f"/api/v1/run/job/{engine_id}/status",
                    headers=auth_headers(),
                )
                self.assertEqual(done.status_code, 200)
                status_body = done.json()
                self.assertEqual(status_body["status"], "completed")
                self.assertTrue(status_body["poll"]["terminal"])
                self.assertTrue(status_body["receipt"]["linked"])
                self.assertEqual(status_body["receipt"]["receipt_id"], receipt_id)
                assert_hermetic_blob_has_no_secrets(json.dumps(status_body))

    def test_status_by_receipt_id(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.post(
                "/api/v1/run",
                json=run_payload("by receipt"),
                headers=auth_headers(),
            )
            receipt_id = r.json()["summary"]["receipt_id"]
            drain_background_tasks()
            by_receipt = client.get(
                f"/api/v1/run/job/by-receipt/{receipt_id}/status",
                headers=auth_headers(),
            )
            self.assertEqual(by_receipt.status_code, 200)
            self.assertEqual(by_receipt.json()["receipt"]["receipt_id"], receipt_id)

    def test_unknown_receipt_404(self) -> None:
        with hermetic_run_client() as (client, _):
            missing = client.get(
                "/api/v1/run/job/by-receipt/receipt_missing_xyz/status",
                headers=auth_headers(),
            )
            self.assertEqual(missing.status_code, 404)

    def test_unknown_job_404(self) -> None:
        with hermetic_run_client() as (client, _):
            missing = client.get(
                "/api/v1/run/job/engine_does_not_exist/status",
                headers=auth_headers(),
            )
            self.assertEqual(missing.status_code, 404)
            self.assertEqual(missing.json()["detail"], "think_job_not_found")

    def test_receipt_card_endpoint(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.post(
                "/api/v1/run",
                json=run_payload("card"),
                headers=auth_headers(),
            )
            engine_id = r.json()["engine_id"]
            drain_background_tasks()
            card = client.get(
                f"/api/v1/dashboard/think-job/{engine_id}/receipt-card",
                headers=auth_headers(),
            )
            self.assertEqual(card.status_code, 200)
            self.assertEqual(card.json()["kind"], "think_job_receipt_card")
            self.assertTrue(card.json()["receipt_linked"])

    def test_list_jobs_status(self) -> None:
        with hermetic_run_client() as (client, _):
            client.post(
                "/api/v1/run",
                json=run_payload("list"),
                headers=auth_headers(),
            )
            drain_background_tasks()
            listed = client.get("/api/v1/run/jobs/status?limit=10", headers=auth_headers())
            self.assertEqual(listed.status_code, 200)
            self.assertGreaterEqual(listed.json()["count"], 1)

    def test_openapi_lists_status_routes(self) -> None:
        with hermetic_run_client() as (client, _):
            spec = client.get("/openapi.json", headers=auth_headers())
        self.assertEqual(spec.status_code, 200)
        paths = spec.json().get("paths", {})
        self.assertIn("/api/v1/run/job/{engine_id}/status", paths)

    def test_governance_status_includes_job_snapshot(self) -> None:
        with hermetic_run_client() as (client, _):
            gov = client.get("/api/v1/run/governance/status", headers=auth_headers())
            self.assertEqual(gov.status_code, 200)
            self.assertIn("think_job_status", gov.json())

    def test_job_completed_event_includes_receipt_card(self) -> None:
        with isolated_dashboard_state() as dash:
            with hermetic_run_client() as (client, _):
                client.post(
                    "/api/v1/run",
                    json=run_payload("event card"),
                    headers=auth_headers(),
                )
                drain_background_tasks()
                completed = events_matching(
                    dash,
                    category=DashboardCategory.THINK_JOBS,
                    event_type=DashboardEvent.JOB_COMPLETED,
                )
                self.assertTrue(completed)
                data = completed[-1].data
                self.assertIn("receipt_card", data)
                self.assertEqual(data["receipt_card"]["kind"], "think_job_receipt_card")


if __name__ == "__main__":
    unittest.main()
