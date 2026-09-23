"""Receipt chain in-page prev link validation (PR #157)."""

from __future__ import annotations

import unittest

from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.receipt_chain_query import (
    ReceiptChainValidationError,
    fetch_chain_page,
    validate_page_prev_receipt_links,
)


class TestReceiptChainPageLinks(unittest.TestCase):
    def test_validate_page_links_ok(self) -> None:
        receipts = [
            {"receipt_id": "a", "prev_receipt_id": None},
            {"receipt_id": "b", "prev_receipt_id": "a"},
        ]
        validate_page_prev_receipt_links(receipts)

    def test_validate_page_links_fail(self) -> None:
        receipts = [
            {"receipt_id": "a", "prev_receipt_id": None},
            {"receipt_id": "b", "prev_receipt_id": "wrong"},
        ]
        with self.assertRaises(ReceiptChainValidationError):
            validate_page_prev_receipt_links(receipts)

    def test_fetch_chain_page_validates(self) -> None:
        store = ActionReceiptStore(":memory:")
        store.append("act", "OK", "r", "simulated", metadata={})
        store.append("act", "OK", "r", "simulated", metadata={})
        page = fetch_chain_page(store, limit=10)
        self.assertEqual(len(page.receipts), 2)


if __name__ == "__main__":
    unittest.main()
