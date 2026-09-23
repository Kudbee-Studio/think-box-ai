"""PR #139 — receipt-keyed watch + digest multiplex (hermetic)."""

from __future__ import annotations

import json
import unittest

from tests.e2e.api_run_hermetic import (
    auth_headers,
    drain_background_tasks,
    hermetic_run_client,
    run_payload,
)
from tests.e2e.hermetic_scaffold import assert_hermetic_blob_has_no_secrets
from thinkbox.think_job_status_ui import (
    MultiplexPanelState,
    apply_digest_stream_event,
    parse_sse_data_events,
    resolve_watch_target,
    stream_plan_for_watch_target,
)


class TestF139ReceiptMultiplex(unittest.TestCase):
    def test_receipt_poll_stream_plan(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.post(
                "/api/v1/run",
                json=run_payload("f139 receipt plan"),
                headers=auth_headers(),
            )
            receipt_id = r.json()["summary"]["receipt_id"]
            drain_background_tasks()
            poll = client.get(
                f"/api/v1/run/job/by-receipt/{receipt_id}/status",
                headers=auth_headers(),
            )
            self.assertEqual(poll.status_code, 200)
            target = resolve_watch_target(receipt_id=receipt_id)
            plan = stream_plan_for_watch_target(target, poll.json())
            self.assertIn("by-receipt", plan.stream_url)
            self.assertIn(receipt_id, plan.poll_url)

    def test_invalid_receipt_404_fail_closed(self) -> None:
        with hermetic_run_client() as (client, _):
            missing = client.get(
                "/api/v1/run/job/by-receipt/receipt_missing_xyz/status",
                headers=auth_headers(),
            )
            self.assertEqual(missing.status_code, 404)

    def test_jobs_digest_stream_hello_merge(self) -> None:
        with hermetic_run_client() as (client, _):
            client.post(
                "/api/v1/run",
                json=run_payload("f139 digest"),
                headers=auth_headers(),
            )
            drain_background_tasks()
            with client.stream(
                "GET",
                "/api/v1/run/jobs/status/stream",
                headers=auth_headers(),
                params={"max_events": 4, "timeout_s": 5},
            ) as resp:
                text = "".join(resp.iter_text())
            events = parse_sse_data_events(text)
            panel = MultiplexPanelState()
            for ev in events:
                apply_digest_stream_event(panel, ev)
            kinds = [e.get("kind") for e in events]
            self.assertIn("think_jobs_stream_hello", kinds)
            assert_hermetic_blob_has_no_secrets(json.dumps(panel.digest_document or {}))


if __name__ == "__main__":
    unittest.main()
