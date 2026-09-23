"""Dashboard view model tests (PR #156)."""

from __future__ import annotations

import unittest

from thinkbox.dashboard_receipt_chain_models import (
    end_link_panel_from_result,
    chain_page_from_payload,
)


class TestDashboardReceiptChainModels(unittest.TestCase):
    def test_chain_page_from_payload(self) -> None:
        view = chain_page_from_payload(
            {"receipts": [{"receipt_id": "r1"}], "total": 1, "chain_valid": True},
        )
        self.assertEqual(view.total, 1)
        self.assertTrue(view.chain_valid)

    def test_end_link_412_label(self) -> None:
        panel = end_link_panel_from_result("r1", valid=False, http_status=412)
        self.assertIn("412", panel.status_label)


if __name__ == "__main__":
    unittest.main()
