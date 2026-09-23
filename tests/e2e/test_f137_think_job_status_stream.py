"""PR #137 — Think Job status SSE stream (hermetic poll → push)."""

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


def _parse_sse_events(text: str) -> list[dict]:
    events: list[dict] = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        data_line = next((ln for ln in block.splitlines() if ln.startswith("data: ")), "")
        if data_line:
            events.append(json.loads(data_line[6:]))
    return events


class TestThinkJobStatusStream(unittest.TestCase):
    def test_stream_after_run_hello_and_terminal(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.post(
                "/api/v1/run",
                json=run_payload("stream path"),
                headers=auth_headers(),
            )
            self.assertEqual(r.status_code, 200)
            engine_id = r.json()["engine_id"]
            drain_background_tasks()
            with client.stream(
                "GET",
                f"/api/v1/run/job/{engine_id}/status/stream",
                headers=auth_headers(),
                params={"max_events": 16, "timeout_s": 10, "heartbeat_s": 60},
            ) as resp:
                self.assertEqual(resp.status_code, 200)
                self.assertIn("text/event-stream", resp.headers.get("content-type", ""))
                text = "".join(resp.iter_text())
            events = _parse_sse_events(text)
            kinds = [e.get("kind") for e in events]
            self.assertIn("think_job_stream_hello", kinds)
            self.assertIn("think_job_stream_close", kinds)
            assert_hermetic_blob_has_no_secrets(text)

    def test_poll_includes_stream_hints(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.post(
                "/api/v1/run",
                json=run_payload("hints"),
                headers=auth_headers(),
            )
            engine_id = r.json()["engine_id"]
            drain_background_tasks()
            poll = client.get(
                f"/api/v1/run/job/{engine_id}/status",
                headers=auth_headers(),
            )
            stream = poll.json()["poll"]["stream"]
            self.assertTrue(stream["stream_available"])
            self.assertIn("status/stream", stream["job_path"])

    def test_unknown_job_stream_404(self) -> None:
        with hermetic_run_client() as (client, _):
            missing = client.get(
                "/api/v1/run/job/engine_missing_sse/status/stream",
                headers=auth_headers(),
            )
            self.assertEqual(missing.status_code, 404)

    def test_openapi_lists_stream_route(self) -> None:
        with hermetic_run_client() as (client, _):
            spec = client.get("/openapi.json", headers=auth_headers())
        paths = spec.json().get("paths", {})
        self.assertIn("/api/v1/run/job/{engine_id}/status/stream", paths)

    def test_stream_by_receipt_after_run(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.post(
                "/api/v1/run",
                json=run_payload("receipt stream"),
                headers=auth_headers(),
            )
            receipt_id = r.json()["summary"]["receipt_id"]
            drain_background_tasks()
            with client.stream(
                "GET",
                f"/api/v1/run/job/by-receipt/{receipt_id}/status/stream",
                headers=auth_headers(),
                params={"max_events": 8, "timeout_s": 10},
            ) as resp:
                self.assertEqual(resp.status_code, 200)
                text = "".join(resp.iter_text())
            self.assertIn("think_job_stream_hello", text)

    def test_jobs_digest_stream_hello(self) -> None:
        with hermetic_run_client() as (client, _):
            client.post(
                "/api/v1/run",
                json=run_payload("digest stream"),
                headers=auth_headers(),
            )
            drain_background_tasks()
            with client.stream(
                "GET",
                "/api/v1/run/jobs/status/stream",
                headers=auth_headers(),
                params={"limit": 5, "max_events": 4, "timeout_s": 2},
            ) as resp:
                self.assertEqual(resp.status_code, 200)
                text = "".join(resp.iter_text())
            self.assertIn("think_jobs_stream_hello", text)

    def test_governance_includes_stream_snapshot(self) -> None:
        with hermetic_run_client() as (client, _):
            gov = client.get("/api/v1/run/governance/status", headers=auth_headers())
            stream = gov.json()["think_job_status"]["stream"]
            self.assertIn("stream_schema_version", stream)


if __name__ == "__main__":
    unittest.main()
