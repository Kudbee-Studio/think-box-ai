"""Receipt-keyed watch helpers (PR #139)."""

from __future__ import annotations

import unittest

from thinkbox.think_job_status_ui import (
    WatchKeyKind,
    assert_receipt_watch_consistency,
    format_receipt_poll_path,
    normalize_receipt_key,
    poll_path_for_target,
    resolve_watch_target,
    stream_plan_for_watch_target,
)


class TestReceiptKeyNormalization(unittest.TestCase):
    def test_reject_empty(self) -> None:
        with self.assertRaises(ValueError):
            normalize_receipt_key("  ")

    def test_reject_missing_prefix(self) -> None:
        with self.assertRaises(ValueError):
            normalize_receipt_key("receipt_missing_xyz")

    def test_accepts_valid(self) -> None:
        self.assertEqual(normalize_receipt_key(" rcpt_abc "), "rcpt_abc")


class TestResolveWatchTarget(unittest.TestCase):
    def test_receipt_wins_over_engine(self) -> None:
        target = resolve_watch_target(engine_id="eng1", receipt_id="rcpt_1")
        self.assertEqual(target.kind, WatchKeyKind.RECEIPT)
        self.assertEqual(target.key, "rcpt_1")

    def test_engine_only(self) -> None:
        target = resolve_watch_target(engine_id="eng1", receipt_id="")
        self.assertEqual(target.kind, WatchKeyKind.ENGINE)

    def test_poll_path_receipt(self) -> None:
        target = resolve_watch_target(receipt_id="r1")
        self.assertIn("r1", poll_path_for_target(target))
        self.assertIn("by-receipt", format_receipt_poll_path("r1"))


class TestReceiptStreamPlan(unittest.TestCase):
    def test_receipt_stream_plan(self) -> None:
        target = resolve_watch_target(receipt_id="rcpt_x")
        doc = {
            "engine_id": "eng_x",
            "receipt": {"receipt_id": "rcpt_x", "linked": True},
            "poll": {
                "recommended_interval_ms": 4000,
                "stream": {
                    "stream_available": True,
                    "job_path": "/api/v1/run/job/{engine_id}/status/stream",
                    "receipt_path": "/api/v1/run/job/by-receipt/{receipt_id}/status/stream",
                },
            },
        }
        plan = stream_plan_for_watch_target(target, doc)
        self.assertIn("rcpt_x", plan.stream_url)
        self.assertIn("by-receipt", plan.poll_url)

    def test_mismatch_fail_closed(self) -> None:
        target = resolve_watch_target(receipt_id="rcpt_a")
        doc = {"receipt": {"receipt_id": "rcpt_b"}}
        with self.assertRaises(ValueError):
            assert_receipt_watch_consistency(target, doc)


if __name__ == "__main__":
    unittest.main()
