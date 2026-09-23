"""Unit tests for END LINK deepen helpers (PR #158)."""

from __future__ import annotations

import unittest

from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.end_link_deepen import (
    BATCH_VALIDATE_MAX_IDS,
    evaluate_end_link_batch_body,
    run_end_link_batch_validate,
    run_end_link_validate_detailed,
)
from thinkbox.end_link_api import EndLinkViolation, normalize_end_link_receipt_id


class TestEndLinkDeepen(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ActionReceiptStore(":memory:")
        self.receipt = self.store.append("cp.demo", "OK", "ok", "simulated", metadata={})

    def test_validate_detailed_ok(self) -> None:
        detail = run_end_link_validate_detailed(self.store, self.receipt.receipt_id)
        self.assertTrue(detail.valid)
        self.assertEqual(detail.link_integrity, "ok")

    def test_validate_detailed_missing(self) -> None:
        detail = run_end_link_validate_detailed(self.store, "rcpt_missing_xyz")
        self.assertFalse(detail.valid)
        self.assertEqual(detail.failure_code, "receipt_not_found")

    def test_batch_mixed(self) -> None:
        batch = run_end_link_batch_validate(
            self.store,
            [self.receipt.receipt_id, "rcpt_missing_xyz"],
        )
        self.assertEqual(batch.total, 2)
        self.assertEqual(batch.valid_count, 1)
        self.assertEqual(batch.invalid_count, 1)

    def test_batch_body_parse(self) -> None:
        ids, errors = evaluate_end_link_batch_body({"receipt_ids": ["a", "b"]})
        self.assertEqual(errors, [])
        self.assertEqual(ids, ["a", "b"])

    def test_batch_body_rejects_empty(self) -> None:
        _, errors = evaluate_end_link_batch_body({"receipt_ids": []})
        self.assertIn("receipt_ids_empty", errors)

    def test_batch_cap(self) -> None:
        many = [f"r{i}" for i in range(BATCH_VALIDATE_MAX_IDS + 5)]
        _, errors = evaluate_end_link_batch_body({"receipt_ids": many})
        self.assertIn("receipt_ids_too_many", errors)
        batch = run_end_link_batch_validate(self.store, many)
        self.assertLessEqual(batch.total, BATCH_VALIDATE_MAX_IDS)

    def test_normalize_still_fail_closed(self) -> None:
        with self.assertRaises(EndLinkViolation):
            normalize_end_link_receipt_id("")


if __name__ == "__main__":
    unittest.main()
