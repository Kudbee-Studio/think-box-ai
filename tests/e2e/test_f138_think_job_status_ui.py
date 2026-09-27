"""PR #138 — control-plane Think Job status UI + client parity (hermetic)."""

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
    apply_status_event,
    parse_sse_data_events,
    stream_url_from_poll_payload,
    ThinkJobWatchState,
)


class TestThinkJobStatusUiHermetic(unittest.TestCase):
    def test_poll_plan_matches_api_hints(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.post(
                "/api/v1/run",
                json=run_payload("ui plan"),
                headers=auth_headers(),
            )
            engine_id = r.json()["engine_id"]
            drain_background_tasks()
            poll = client.get(
                f"/api/v1/run/job/{engine_id}/status",
                headers=auth_headers(),
            )
            doc = poll.json()
            plan = stream_url_from_poll_payload(doc)
            self.assertIn(engine_id, plan.stream_url)
            self.assertIn("/status/stream", plan.stream_url)

    def test_fetch_sse_frames_merge_into_watch_state(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.post(
                "/api/v1/run",
                json=run_payload("ui sse merge"),
                headers=auth_headers(),
            )
            engine_id = r.json()["engine_id"]
            drain_background_tasks()
            with client.stream(
                "GET",
                f"/api/v1/run/job/{engine_id}/status/stream",
                headers=auth_headers(),
                params={"max_events": 8, "timeout_s": 8},
            ) as resp:
                text = "".join(resp.iter_text())
            events = parse_sse_data_events(text)
            state = ThinkJobWatchState(engine_id=engine_id)
            for ev in events:
                apply_status_event(state, ev)
            kinds = [e.get("kind") for e in events]
            self.assertIn("think_job_stream_hello", kinds)
            assert_hermetic_blob_has_no_secrets(json.dumps(state.summary or {}))

    def test_static_page_served_not_required(self) -> None:
        """UI is static under public/ — contract covered in unit static tests."""
        from pathlib import Path

        self.assertTrue(Path("public/control-plane/think_job_status.html").is_file())


if __name__ == "__main__":
    unittest.main()
