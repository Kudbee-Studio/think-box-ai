"""Fallback policy + URL builders for Think Job status UI (PR #138)."""

from __future__ import annotations

import unittest

from thinkbox.think_job_status_ui import (
    TransportMode,
    append_query_api_key,
    backoff_delay_ms,
    build_stream_url,
    classify_transport_after_error,
    digest_row_label,
    format_job_stream_path,
    select_jobs_from_digest,
    should_enter_poll_fallback,
    stream_url_from_poll_payload,
    terminal_from_summary,
)


class TestStreamUrlBuilders(unittest.TestCase):
    def test_append_query_api_key(self) -> None:
        url = append_query_api_key("/stream?max_events=1", "k")
        self.assertIn("api_key=k", url)

    def test_build_stream_url_includes_defaults(self) -> None:
        url = build_stream_url(format_job_stream_path("eng1"))
        self.assertIn("max_events=", url)
        self.assertIn("/status/stream", url)

    def test_stream_plan_from_poll(self) -> None:
        doc = {
            "engine_id": "eng_a",
            "poll": {
                "recommended_interval_ms": 3000,
                "stream": {
                    "stream_available": True,
                    "job_path": "/api/v1/run/job/{engine_id}/status/stream",
                },
            },
        }
        plan = stream_url_from_poll_payload(doc)
        self.assertIn("eng_a", plan.stream_url)
        self.assertEqual(plan.recommended_interval_ms, 3000)


class TestFallbackPolicy(unittest.TestCase):
    def test_poll_when_no_sse(self) -> None:
        self.assertTrue(
            should_enter_poll_fallback(sse_supported=False, sse_failed=False, stream_available=True)
        )

    def test_classify_degraded(self) -> None:
        mode = classify_transport_after_error(TransportMode.SSE, sse_recoverable=False)
        self.assertEqual(mode, TransportMode.DEGRADED_POLL)

    def test_backoff_caps(self) -> None:
        self.assertLessEqual(backoff_delay_ms(20), 30_000)
        self.assertGreaterEqual(backoff_delay_ms(0), 500)

    def test_terminal_from_poll_hint(self) -> None:
        self.assertTrue(terminal_from_summary({"poll": {"terminal": True}}))


class TestDigestHelpers(unittest.TestCase):
    def test_digest_row_label(self) -> None:
        self.assertIn("running", digest_row_label({"job_id": "j", "status": "running"}))

    def test_select_jobs_from_digest(self) -> None:
        rows = select_jobs_from_digest({"jobs": [{"job_id": "a"}, {"job_id": "b"}]}, limit=1)
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
