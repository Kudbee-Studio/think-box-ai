"""Hermetic load-path tests (PR #135) — cache hits, digest, revision."""

from __future__ import annotations

import unittest

from backend.api.v1.run_receipts import (
    begin_http_run_receipt,
    read_run_receipt,
    reset_http_run_persistence_for_tests,
)
from backend.api.v1.run_job_status import (
    build_think_job_status_summary,
    list_think_job_status_digest,
)
from thinkbox.dashboard_state import ThinkJobEntry, get_dashboard_state
from thinkbox.read_cache import receipt_cache, reset_read_caches_for_tests


class TestReceiptReadCache(unittest.TestCase):
    def setUp(self) -> None:
        reset_read_caches_for_tests()
        reset_http_run_persistence_for_tests()

    def test_second_read_uses_cache(self) -> None:
        binding = begin_http_run_receipt(
            engine_id="eng_cache",
            goal="g",
            agent_id="a",
            verified=False,
            capability="goal:execute",
        )
        receipt_cache().clear()
        first = read_run_receipt(binding.receipt_id)
        self.assertIsNotNone(first)
        entry = receipt_cache().get(f"receipt:{binding.receipt_id}")
        self.assertIsNotNone(entry)
        second = read_run_receipt(binding.receipt_id)
        self.assertEqual(first, second)


class TestJobStatusDigest(unittest.TestCase):
    def setUp(self) -> None:
        dash = get_dashboard_state()
        dash.think_jobs.clear()
        dash.upsert_think_job(
            ThinkJobEntry(
                job_id="j1",
                goal="g",
                status="running",
                engine_id="j1",
            )
        )

    def test_digest_counts_running(self) -> None:
        digest = list_think_job_status_digest(limit=10)
        self.assertEqual(digest["count"], 1)
        self.assertEqual(digest["running"], 1)

    def test_summary_smaller_than_full_card(self) -> None:
        record = {
            "job_id": "j1",
            "status": "running",
            "receipt_id": "r",
            "experiment_id": "e",
            "session_id": "s",
        }
        summary = build_think_job_status_summary(record)
        self.assertNotIn("receipt_card", summary)


if __name__ == "__main__":
    unittest.main()
