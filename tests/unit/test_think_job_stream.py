"""Unit tests for thinkbox.think_job_stream (PR #137)."""

from __future__ import annotations

import json
import unittest

from thinkbox.think_job_stream import (
    MAX_SSE_FRAME_BYTES,
    build_stream_hello,
    compute_status_delta,
    format_sse_data,
    get_think_job_stream_hub,
    reset_think_job_stream_hub_for_tests,
    status_fingerprint,
    stream_hints_for_poll,
)


class TestThinkJobStreamCore(unittest.TestCase):
    def setUp(self) -> None:
        reset_think_job_stream_hub_for_tests()

    def test_fingerprint_changes_on_status(self) -> None:
        a = {"job_id": "j1", "status": "running", "phase": "x", "progress": 0.0, "tasks_total": 1, "tasks_completed": 0, "receipt": {}}
        b = dict(a, status="completed", tasks_completed=1)
        self.assertNotEqual(status_fingerprint(a), status_fingerprint(b))

    def test_delta_lists_changed_fields(self) -> None:
        prev = {"job_id": "j1", "status": "running", "phase": "a", "progress": 0.0, "tasks_total": 2, "tasks_completed": 0, "receipt": {}}
        curr = dict(prev, status="completed", tasks_completed=2, poll={"terminal": True})
        delta = compute_status_delta(prev, curr, sequence=1)
        self.assertEqual(delta["kind"], "think_job_status_delta")
        self.assertIn("status", delta["changed"])
        self.assertIn("tasks_completed", delta["changed"])
        self.assertFalse(delta["live_verified"])

    def test_sse_format_includes_data_line(self) -> None:
        frame = format_sse_data({"kind": "ping"}, event="heartbeat")
        self.assertIn("event: heartbeat", frame)
        self.assertIn("data: ", frame)
        self.assertTrue(frame.endswith("\n\n"))

    def test_sse_frame_too_large_truncates(self) -> None:
        huge = {"blob": "x" * (MAX_SSE_FRAME_BYTES + 100)}
        frame = format_sse_data(huge)
        data_line = [ln for ln in frame.splitlines() if ln.startswith("data: ")][0]
        payload = json.loads(data_line[6:])
        self.assertEqual(payload["error"], "frame_too_large")

    def test_hub_signal_bumps_generation(self) -> None:
        hub = get_think_job_stream_hub()
        g0 = hub.generation()
        hub.signal("engine_abc")
        self.assertGreater(hub.generation(), g0)
        self.assertGreater(hub.job_generation("engine_abc"), 0)

    def test_stream_hints_on_poll(self) -> None:
        hints = stream_hints_for_poll()
        self.assertTrue(hints["stream_available"])
        self.assertIn("/status/stream", hints["job_path"])

    def test_hello_redacts(self) -> None:
        summary = {
            "job_id": "j1",
            "status": "running",
            "governance_token": "secret",
            "receipt": {"receipt_id": "r1"},
        }
        hello = build_stream_hello(summary, stream_id="s1", job_id="j1")
        self.assertNotIn("secret", json.dumps(hello))


if __name__ == "__main__":
    unittest.main()
