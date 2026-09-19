"""Tests for ActionReceiptStore — append-only + hash-chain continuity."""

import json
import sqlite3
import unittest
from thinkbox.agent.control_plane.store import ActionReceiptStore, Receipt


class TestActionReceiptStore(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ActionReceiptStore(":memory:")

    def tearDown(self) -> None:
        self.store.close()

    def test_append_single_receipt(self) -> None:
        r = self.store.append("admit", "allowed", "admission granted", "verified")
        self.assertIsInstance(r, Receipt)
        self.assertTrue(r.receipt_id.startswith("rcpt_"))
        self.assertEqual(r.action, "admit")
        self.assertEqual(r.status, "allowed")
        self.assertEqual(r.prev_hash, "GENESIS")

    def test_append_multiple_receipts(self) -> None:
        r1 = self.store.append("admit", "allowed", "ok", "verified")
        r2 = self.store.append("capacity", "allowed", "capacity granted", "simulated")
        self.assertEqual(r2.prev_hash, r1.entry_hash)

    def test_verify_empty(self) -> None:
        self.assertTrue(self.store.verify())

    def test_verify_intact_chain(self) -> None:
        self.store.append("admit", "allowed", "ok", "verified")
        self.store.append("capacity", "allowed", "ok", "simulated")
        self.store.append("secret", "allowed", "ok", "simulated")
        self.assertTrue(self.store.verify())

    def test_verify_detects_hash_tamper(self) -> None:
        import tempfile
        path = tempfile.mktemp(suffix=".db")
        store = ActionReceiptStore(path)
        store.append("admit", "allowed", "ok", "verified")
        store.append("capacity", "allowed", "ok", "simulated")
        conn = sqlite3.connect(path)
        conn.execute("UPDATE receipts SET reason='tampered' WHERE action='capacity'")
        conn.commit()
        conn.close()
        self.assertFalse(store.verify())
        store.close()

    def test_verify_detects_gap(self) -> None:
        import tempfile
        path = tempfile.mktemp(suffix=".db")
        store = ActionReceiptStore(path)
        store.append("admit", "allowed", "ok", "verified")
        r2 = store.append("capacity", "allowed", "ok", "simulated")
        conn = sqlite3.connect(path)
        conn.execute("UPDATE receipts SET prev_hash='FORGED' WHERE receipt_id=?", (r2.receipt_id,))
        conn.commit()
        conn.close()
        self.assertFalse(store.verify())
        store.close()

    def test_verify_detects_fork(self) -> None:
        import tempfile
        path = tempfile.mktemp(suffix=".db")
        store = ActionReceiptStore(path)
        store.append("admit", "allowed", "ok", "verified")
        r1 = store.append("capacity", "allowed", "ok", "simulated")
        r2 = store.append("secret", "allowed", "ok", "simulated")
        conn = sqlite3.connect(path)
        conn.execute("UPDATE receipts SET prev_hash='GENESIS' WHERE receipt_id=?", (r2.receipt_id,))
        conn.commit()
        conn.close()
        self.assertFalse(store.verify())
        store.close()

    def test_latest_returns_n_entries(self) -> None:
        for i in range(5):
            self.store.append(f"action-{i}", "allowed", f"reason-{i}", "simulated")
        latest = self.store.latest(3)
        self.assertEqual(len(latest), 3)
        self.assertEqual(latest[0]["action"], "action-4")

    def test_count(self) -> None:
        self.assertEqual(self.store.count(), 0)
        self.store.append("admit", "allowed", "ok", "verified")
        self.store.append("capacity", "allowed", "ok", "simulated")
        self.assertEqual(self.store.count(), 2)

    def test_metadata_preserved(self) -> None:
        meta = {"agent_id": "a1", "task_id": "t1"}
        r = self.store.append("admit", "allowed", "ok", "verified", metadata=meta)
        self.assertEqual(r.metadata, meta)

    def test_evidence_label_any_string(self) -> None:
        r = self.store.append("admit", "allowed", "ok", "simulated")
        self.assertEqual(r.evidence_label, "simulated")
        r2 = self.store.append("shutdown", "denied", "no token", "_demo")
        self.assertEqual(r2.evidence_label, "_demo")
