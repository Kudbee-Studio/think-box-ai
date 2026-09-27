"""Dashboard client END LINK deepen (PR #158)."""

from __future__ import annotations

import unittest

from thinkbox.control_plane_operation_registry import reset_operation_registry
from thinkbox.control_plane_receipt_store import reset_control_plane_receipt_store
from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.control_plane_receipt_store import get_control_plane_receipt_store
from thinkbox.dashboard_receipt_chain_client import DashboardReceiptChainClient


class TestDashboardEndLinkDeepenPr158(unittest.TestCase):
    def setUp(self) -> None:
        reset_operation_registry()
        reset_control_plane_receipt_store()

    def tearDown(self) -> None:
        reset_operation_registry()
        reset_control_plane_receipt_store()

    def test_batch_validate_hermetic(self) -> None:
        store = get_control_plane_receipt_store()
        if not isinstance(store, ActionReceiptStore):
            self.skipTest("in-memory store required")
        store.append("cp.demo", "OK", "r", "simulated", metadata={})
        client = DashboardReceiptChainClient()
        page = client.fetch_page(limit=1)
        rid = page.receipts[0]["receipt_id"]
        batch = client.validate_end_link_batch([rid, "missing"])
        self.assertEqual(batch["valid_count"], 1)
        self.assertFalse(batch["live_api_called"])


if __name__ == "__main__":
    unittest.main()
