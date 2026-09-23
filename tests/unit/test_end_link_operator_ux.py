"""END LINK operator UX helpers (PR #159)."""

from __future__ import annotations

import unittest

from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.end_link_deepen import run_end_link_batch_validate
from thinkbox.end_link_operator_ux import (
    ChainFilterParams,
    build_chain_filter_query,
    four_state_honesty_copy,
    summarize_end_link_batch,
)


class TestEndLinkOperatorUx(unittest.TestCase):
    def test_summarize_batch_fail_closed(self) -> None:
        store = ActionReceiptStore(":memory:")
        receipt = store.append("act", "OK", "r", "simulated", metadata={})
        batch = run_end_link_batch_validate(store, [receipt.receipt_id, "missing"])
        summary = summarize_end_link_batch(batch.to_dict())
        self.assertEqual(summary.valid_count, 1)
        self.assertEqual(summary.invalid_count, 1)
        self.assertTrue(summary.fail_closed)
        self.assertEqual(len(summary.rows), 2)
        self.assertFalse(summary.live_api_called)

    def test_chain_filter_query(self) -> None:
        q = build_chain_filter_query(
            ChainFilterParams(status_filter="OK", evidence_label="simulated"),
        )
        self.assertIn("status=OK", q)
        self.assertIn("evidence_label=simulated", q)

    def test_honesty_copy(self) -> None:
        copy = four_state_honesty_copy()
        self.assertEqual(copy["four_state_max"], "TEST_VERIFIED")
        self.assertEqual(copy["live_api_called"], "false")


if __name__ == "__main__":
    unittest.main()
