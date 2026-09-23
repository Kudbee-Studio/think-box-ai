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


if __name__ == "__main__":
    unittest.main()
