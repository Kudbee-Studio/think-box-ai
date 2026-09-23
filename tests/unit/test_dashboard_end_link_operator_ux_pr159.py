"""Dashboard bind operator UX deepen (PR #159)."""

from __future__ import annotations

import unittest

from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.control_plane_operation_registry import reset_operation_registry
from thinkbox.control_plane_receipt_store import (
    get_control_plane_receipt_store,
    reset_control_plane_receipt_store,
)
from thinkbox.dashboard_receipt_chain_client import DashboardReceiptChainClient
from thinkbox.dashboard_receipt_chain_models import end_link_batch_panel_from_summary
from thinkbox.end_link_operator_ux import summarize_end_link_batch


class TestDashboardEndLinkOperatorUxPr159(unittest.TestCase):
    def setUp(self) -> None:
        reset_operation_registry()
        reset_control_plane_receipt_store()

    def tearDown(self) -> None:
        reset_operation_registry()
        reset_control_plane_receipt_store()

    def test_bind_state_with_filters_and_batch(self) -> None:
        store = get_control_plane_receipt_store()
        if not isinstance(store, ActionReceiptStore):
            self.skipTest("in-memory store required")
        store.append("cp.demo", "OK", "r", "simulated", metadata={})
        client = DashboardReceiptChainClient()
        page = client.fetch_page(limit=1, status_filter="OK", evidence_label="simulated")
        self.assertGreaterEqual(page.total, 1)
        rid = page.receipts[0]["receipt_id"]
        summary = client.summarize_batch_for_panel([rid, "missing"])
        panel = end_link_batch_panel_from_summary(summary)
        self.assertEqual(panel.valid_count, 1)
        self.assertTrue(panel.fail_closed)
        state = client.bind_state(
            limit=5,
            status_filter="OK",
            evidence_label="simulated",
            end_link_receipt_id=rid,
            end_link_batch_ids=[rid, "missing"],
        )
        self.assertIsNotNone(state.end_link)
        self.assertIsNotNone(state.end_link_batch)
        self.assertIsNotNone(state.chain_filters)
        self.assertFalse(state.live_api_called)
        self.assertIsNotNone(state.end_link.failure_code or state.end_link.valid)

    def test_batch_summary_rows_have_integrity_fields(self) -> None:
        store = get_control_plane_receipt_store()
        if not isinstance(store, ActionReceiptStore):
            self.skipTest("in-memory store required")
        store.append("act", "OK", "r", "simulated", metadata={})
        client = DashboardReceiptChainClient()
        page = client.fetch_page(limit=1)
        rid = page.receipts[0]["receipt_id"]
        summary = summarize_end_link_batch(client.validate_end_link_batch([rid]))
        row = summary.rows[0]
        self.assertEqual(row.link_integrity, "ok")
        self.assertIsNone(row.failure_code)


if __name__ == "__main__":
    unittest.main()
