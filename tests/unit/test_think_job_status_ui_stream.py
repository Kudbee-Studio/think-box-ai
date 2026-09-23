"""SSE parse + event merge for Think Job status UI (PR #138)."""

from __future__ import annotations

import unittest

from thinkbox.think_job_status_ui import (
    ThinkJobWatchState,
    apply_status_event,
    parse_sse_buffer_incremental,
    parse_sse_data_events,
)


class TestSseParse(unittest.TestCase):
    def test_parse_incremental(self) -> None:
        chunk = 'data: {"kind":"think_job_stream_hello","sequence":1}\n\n'
        events, rest = parse_sse_buffer_incremental(chunk)
        self.assertEqual(len(events), 1)
        self.assertEqual(rest, "")

    def test_parse_multiblock(self) -> None:
        raw = (
            'data: {"kind":"think_job_stream_heartbeat"}\n\n'
            'data: {"kind":"think_job_status_delta","sequence":2,"status":"running"}\n\n'
        )
        events = parse_sse_data_events(raw)
        self.assertEqual(len(events), 2)


class TestApplyEvents(unittest.TestCase):
    def test_hello_then_delta(self) -> None:
        state = ThinkJobWatchState(engine_id="e1")
        apply_status_event(
            state,
            {"kind": "think_job_stream_hello", "sequence": 1, "snapshot": {"status": "running"}},
        )
        apply_status_event(
            state,
            {"kind": "think_job_status_delta", "sequence": 2, "status": "completed"},
        )
        self.assertEqual(state.summary["status"], "completed")
        self.assertEqual(state.last_sequence, 2)

    def test_close_sets_error(self) -> None:
        state = ThinkJobWatchState(engine_id="e1")
        apply_status_event(state, {"kind": "think_job_stream_close", "reason": "timeout"})
        self.assertIn("stream_close", state.telemetry.last_error)


if __name__ == "__main__":
    unittest.main()
