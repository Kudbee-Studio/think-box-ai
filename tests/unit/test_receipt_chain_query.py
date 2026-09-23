"""Receipt chain query pagination (PR #155)."""

from __future__ import annotations

import unittest

from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.receipt_chain_query import (
    ReceiptChainValidationError,
    decode_cursor,
    encode_cursor,
    fetch_chain_page,
    fetch_head_receipt,
    fetch_tail_receipt,
    validate_receipt_link,
)


class TestReceiptChainQuery(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ActionReceiptStore(":memory:")
        for i in range(5):
            self.store.append(
                f"act{i}",
                "ok",
                "r",
                "simulated",
                metadata={"agent_id": "ag1" if i % 2 == 0 else "ag2"},
            )

    def test_pagination_cursor(self) -> None:
        p1 = fetch_chain_page(self.store, limit=2)
        self.assertEqual(len(p1.receipts), 2)
        self.assertIsNotNone(p1.next_cursor)
        p2 = fetch_chain_page(self.store, limit=2, cursor=p1.next_cursor)
        self.assertEqual(len(p2.receipts), 2)

    def test_filter_action(self) -> None:
        self.store.append("special", "ok", "r", "simulated")
        page = fetch_chain_page(self.store, limit=50, action="special")
        self.assertEqual(len(page.receipts), 1)

    def test_filter_agent(self) -> None:
        page = fetch_chain_page(self.store, limit=50, agent_id="ag1")
        self.assertTrue(all(r.get("agent_id") == "ag1" for r in page.receipts))

    def test_head_tail(self) -> None:
        head = fetch_head_receipt(self.store)
        tail = fetch_tail_receipt(self.store)
        self.assertIsNotNone(head)
        self.assertIsNotNone(tail)
        self.assertIsNone(head.get("prev_receipt_id"))
        self.assertIsNotNone(tail.get("prev_receipt_id"))

    def test_validate_link_ok(self) -> None:
        page = fetch_chain_page(self.store, limit=1)
        validate_receipt_link(self.store, page.receipts[0]["receipt_id"])

    def test_validate_missing(self) -> None:
        with self.assertRaises(ReceiptChainValidationError):
            validate_receipt_link(self.store, "rcpt_missing")

    def test_invalid_cursor(self) -> None:
        with self.assertRaises(ReceiptChainValidationError):
            decode_cursor("@@@")

    def test_cursor_roundtrip(self) -> None:
        self.assertEqual(decode_cursor(encode_cursor(7)), 7)

    def test_prev_receipt_id_in_metadata(self) -> None:
        tail = fetch_tail_receipt(self.store)
        meta = tail.get("metadata") or {}
        self.assertIn("prev_receipt_id", meta)


if __name__ == "__main__":
    unittest.main()
