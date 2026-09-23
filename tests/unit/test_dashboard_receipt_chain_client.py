"""Hermetic dashboard receipt-chain client tests (PR #156)."""

from __future__ import annotations

import unittest

from thinkbox.dashboard_receipt_chain_client import (
    DashboardReceiptChainClient,
    chain_api_paths,
    hermetic_fetch_chain_bind_state,
)


class TestDashboardReceiptChainClient(unittest.TestCase):
    def test_chain_paths_include_end_link_template(self) -> None:
        paths = chain_api_paths()
        self.assertIn("end_link_template", paths)
        self.assertIn("{receipt_id}", paths["end_link_template"])

    def test_hermetic_bind_state_no_live(self) -> None:
        bundle = hermetic_fetch_chain_bind_state(limit=5)
        self.assertFalse(bundle.state.live_api_called)
        self.assertIsNotNone(bundle.state.page)

    def test_client_probes(self) -> None:
        client = DashboardReceiptChainClient()
        probes = client.fetch_probes()
        self.assertFalse(probes.live_api_called)


if __name__ == "__main__":
    unittest.main()
