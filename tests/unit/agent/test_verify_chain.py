"""Tests for verify_chain — gap/tamper/fork detection."""

import unittest
from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.verify_chain import verify_chain, ChainResult


class TestVerifyChain(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ActionReceiptStore(":memory:")

    def tearDown(self) -> None:
        self.store.close()

    def test_empty_chain_valid(self) -> None:
        result = verify_chain(self.store)
        self.assertTrue(result.valid)
        self.assertEqual(result.receipts, 0)

    def test_valid_chain(self) -> None:
        self.store.append("admit", "allowed", "ok", "verified")
        self.store.append("capacity", "allowed", "ok", "simulated")
        result = verify_chain(self.store)
        self.assertTrue(result.valid)
        self.assertEqual(result.receipts, 2)

    def test_detects_hash_tamper(self) -> None:
        import sqlite3, tempfile
        path = tempfile.mktemp(suffix=".db")
        store = ActionReceiptStore(path)
        store.append("admit", "allowed", "ok", "verified")
        store.append("capacity", "allowed", "ok", "simulated")
        conn = sqlite3.connect(path)
        conn.execute("UPDATE receipts SET reason='tampered' WHERE action='capacity'")
        conn.commit()
        conn.close()
        result = verify_chain(store)
        self.assertFalse(result.valid)
        self.assertTrue(len(result.tampered_positions) > 0)
        store.close()

    def test_detects_gap(self) -> None:
        import sqlite3, tempfile
        path = tempfile.mktemp(suffix=".db")
        store = ActionReceiptStore(path)
        store.append("admit", "allowed", "ok", "verified")
        r2 = store.append("capacity", "allowed", "ok", "simulated")
        conn = sqlite3.connect(path)
        conn.execute("UPDATE receipts SET prev_hash='FORGED' WHERE receipt_id=?", (r2.receipt_id,))
        conn.commit()
        conn.close()
        result = verify_chain(store)
        self.assertFalse(result.valid)
        self.assertTrue(len(result.gap_positions) > 0)
        store.close()

    def test_detects_fork(self) -> None:
        import sqlite3, tempfile
        path = tempfile.mktemp(suffix=".db")
        store = ActionReceiptStore(path)
        store.append("admit", "allowed", "ok", "verified")
        r1 = store.append("capacity", "allowed", "ok", "simulated")
        r2 = store.append("secret", "allowed", "ok", "simulated")
        conn = sqlite3.connect(path)
        conn.execute("UPDATE receipts SET prev_hash='GENESIS' WHERE receipt_id=?", (r2.receipt_id,))
        conn.commit()
        conn.close()
        result = verify_chain(store)
        self.assertFalse(result.valid)
        store.close()

    def test_issue_messages_present(self) -> None:
        import sqlite3, tempfile
        path = tempfile.mktemp(suffix=".db")
        store = ActionReceiptStore(path)
        store.append("admit", "allowed", "ok", "verified")
        store.append("capacity", "allowed", "ok", "simulated")
        conn = sqlite3.connect(path)
        conn.execute("UPDATE receipts SET reason='x' WHERE action='capacity'")
        conn.commit()
        conn.close()
        result = verify_chain(store)
        self.assertTrue(any("tampered" in msg for msg in result.issues))
        store.close()

    def test_chain_result_dataclass(self) -> None:
        result = ChainResult(valid=True, receipts=0)
        self.assertTrue(result.valid)
        self.assertEqual(result.receipts, 0)
