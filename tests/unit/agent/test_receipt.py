"""Tests for ActionReceipt and ReceiptChain (commit 2: hash chain)."""

import sys
import types
import unittest
from types import SimpleNamespace

sys.modules["grpc"] = types.ModuleType("grpc")
sys.modules["grpc.aio"] = types.ModuleType("grpc.aio")
sys.modules["google.protobuf"] = types.ModuleType("google.protobuf")
sys.modules["thinkbox.agent.protocol"] = types.ModuleType("protocol")

from thinkbox.agent.control_plane.receipt import ActionReceipt, ReceiptChain


class TestActionReceipt(unittest.TestCase):

    def test_receipt_compute_hash(self):
        r = ActionReceipt(
            action_type="CAPACITY_REQUEST",
            agent_id="a1",
            status="OK",
            metadata={"allocation_id": "alloc-1"},
        )
        h = r.compute_hash()
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)

    def test_receipt_deterministic_hash(self):
        r1 = ActionReceipt("CAPACITY", "a1", "OK", metadata={"k": "v"})
        r2 = ActionReceipt("CAPACITY", "a1", "OK", metadata={"k": "v"})
        self.assertEqual(r1.compute_hash(), r2.compute_hash())

    def test_receipt_status_failed(self):
        r = ActionReceipt("SECRET", "a1", "FAILED", metadata={})
        self.assertEqual(r.status, "FAILED")


class TestReceiptChain(unittest.TestCase):

    def setUp(self):
        self.chain = ReceiptChain()

    def test_empty_chain_verify(self):
        self.assertTrue(self.chain.verify())

    def test_append_and_verify(self):
        r1 = ActionReceipt("CAPACITY", "a1", "OK")
        h1 = self.chain.append(r1)
        r2 = ActionReceipt("SECRET", "a1", "OK")
        h2 = self.chain.append(r2)
        self.assertTrue(self.chain.verify())
        self.assertEqual(self.chain.size(), 2)
        self.assertNotEqual(h1, h2)

    def test_hash_chain_links(self):
        r1 = ActionReceipt("A", "a1", "OK")
        self.chain.append(r1)
        r2 = ActionReceipt("B", "a1", "OK")
        self.chain.append(r2)
        receipts = self.chain.receipts
        self.assertEqual(receipts[1].previous_hash, receipts[0].signature)

    def test_tamper_detection(self):
        r1 = ActionReceipt("A", "a1", "OK")
        self.chain.append(r1)
        receipts = self.chain.receipts
        receipts[0].status = "TAMPERED"
        self.assertFalse(self.chain.verify())

    def test_chain_continues_after_tamper(self):
        r1 = ActionReceipt("A", "a1", "OK")
        self.chain.append(r1)
        r2 = ActionReceipt("B", "a1", "OK")
        self.chain.append(r2)
        receipts = self.chain.receipts
        receipts[0].status = "TAMPERED"
        self.assertFalse(self.chain.verify())

    def test_last_hash(self):
        r = ActionReceipt("X", "a1", "OK")
        self.chain.append(r)
        self.assertEqual(self.chain.last_hash, r.signature)


if __name__ == "__main__":
    unittest.main()
