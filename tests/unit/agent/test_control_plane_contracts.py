"""Hermetic API+UI contract tests for control-plane bind."""

import os
import sys
import types
import unittest
from types import SimpleNamespace

sys.modules["grpc"] = types.ModuleType("grpc")
sys.modules["grpc.aio"] = types.ModuleType("grpc.aio")
sys.modules["google.protobuf"] = types.ModuleType("google.protobuf")
sys.modules["thinkbox.agent.protocol"] = types.ModuleType("protocol")

# Mock receipt types from #97 (ledger.py doesn't need these)
sys.modules["thinkbox.agent.control_plane.receipt"] = types.ModuleType("receipt")
sys.modules["thinkbox.agent.control_plane.receipt"].ActionReceipt = SimpleNamespace
sys.modules["thinkbox.agent.control_plane.receipt"].ReceiptChain = SimpleNamespace

from thinkbox.agent.control_plane.ledger import ActionReceiptStore
from thinkbox.agent.control_plane.verify_chain import ChainVerifier
from thinkbox.agent.control_plane.export import ProofExporter
from thinkbox.agent.control_plane.import_bundle import ProofImporter
from thinkbox.agent.control_plane.kernel_hooks import KernelHooks
from thinkbox.agent.control_plane.budget_trip import BudgetTripHandler
from thinkbox.agent.control_plane.kill_events import KillEventStore
from thinkbox.agent.control_plane.lease_evict import LeaseEvictionHandler


class TestControlPlaneContracts(unittest.TestCase):

    def setUp(self):
        self.db_path = os.path.join("/tmp", f"cp_test_{id(self)}.db")
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_ledger_empty_verify(self):
        store = ActionReceiptStore(db_path=self.db_path)
        self.assertTrue(store.verify())
        self.assertEqual(store.count(), 0)
        store.close()

    def test_ledger_append_verify(self):
        store = ActionReceiptStore(db_path=self.db_path)
        store.append({"action_type": "X", "agent_id": "a1", "status": "OK"})
        self.assertTrue(store.verify())
        self.assertEqual(store.count(), 1)
        store.close()

    def test_ledger_tamper(self):
        store = ActionReceiptStore(db_path=self.db_path)
        store.append({"action_type": "A", "agent_id": "a1", "status": "OK"})
        conn = store._connect()
        conn.execute("UPDATE receipts SET previous_hash = 'TAMPERED' WHERE id = 1")
        conn.commit()
        self.assertFalse(store.verify())
        store.close()

    def test_chain_verifier_empty(self):
        store = ActionReceiptStore(db_path=self.db_path)
        verifier = ChainVerifier(store)
        result = verifier.verify()
        self.assertEqual(result["error_code"], "EMPTY_CHAIN")
        store.close()

    def test_chain_verifier_valid(self):
        store = ActionReceiptStore(db_path=self.db_path)
        store.append({"action_type": "A", "agent_id": "a1", "status": "OK"})
        verifier = ChainVerifier(store)
        result = verifier.verify()
        self.assertTrue(result["valid"])
        store.close()

    def test_kernel_hooks_admit(self):
        store = ActionReceiptStore(db_path=self.db_path)
        hooks = KernelHooks(store)
        hooks.bind("agent-1")
        sig = hooks.on_admit("AGENT_SPAWN", {"allowed": True, "reason": "", "conditions": {}})
        self.assertIsInstance(sig, str)
        self.assertEqual(store.count(), 1)
        store.close()

    def test_kernel_hooks_capacity(self):
        store = ActionReceiptStore(db_path=self.db_path)
        hooks = KernelHooks(store)
        hooks.bind("agent-1")
        hooks.on_capacity("alloc-1", True, "")
        self.assertEqual(store.count(), 1)
        store.close()

    def test_kernel_hooks_shutdown(self):
        store = ActionReceiptStore(db_path=self.db_path)
        hooks = KernelHooks(store)
        hooks.bind("agent-1")
        hooks.on_shutdown("NORMAL")
        self.assertEqual(store.count(), 1)
        store.close()

    def test_budget_trip_handler(self):
        store = ActionReceiptStore(db_path=self.db_path)
        handler = BudgetTripHandler(store, "agent-1")
        sig = handler.on_trip(110.0, 100.0)
        self.assertIsInstance(sig, str)
        self.assertEqual(store.count(), 1)
        store.close()

    def test_kill_event_store(self):
        store = KillEventStore(db_path="/tmp/kill_test.json")
        from thinkbox.agent.control_plane.kill_events import KillEvent
        evt = KillEvent("evt-1", "KILL", "agent-1", reason="test")
        store.record(evt)
        self.assertTrue(store.is_killed("agent-1"))
        self.assertEqual(store.count(), 1)
        if os.path.exists("/tmp/kill_test.json"):
            os.remove("/tmp/kill_test.json")

    def test_lease_eviction_handler(self):
        store = ActionReceiptStore(db_path=self.db_path)
        handler = LeaseEvictionHandler(store, None)
        sig = handler.on_expiry("agent-1", "task-1", reason="stale")
        self.assertIsInstance(sig, str)
        self.assertEqual(store.count(), 1)
        store.close()

    def test_bundle_export_import(self):
        store = ActionReceiptStore(db_path=self.db_path)
        store.append({"action_type": "A", "agent_id": "a1", "status": "OK"})
        store.close()

        exporter = ProofExporter(ActionReceiptStore(db_path=self.db_path), output_dir="/tmp")
        manifest = exporter.export("test-bundle")

        importer = ProofImporter(output_dir="/tmp")
        result = importer.import_bundle(manifest)
        self.assertTrue(result["valid"])

        for ext in [".jsonl", ".manifest.json"]:
            path = os.path.join("/tmp", f"test-bundle{ext}")
            if os.path.exists(path):
                os.remove(path)

    def test_chain_verify_after_import(self):
        store = ActionReceiptStore(db_path=self.db_path)
        store.append({"action_type": "A", "agent_id": "a1", "status": "OK"})
        store.append({"action_type": "B", "agent_id": "a1", "status": "OK"})
        store.close()
        reopened = ActionReceiptStore(db_path=self.db_path)
        self.assertTrue(reopened.verify())
        self.assertEqual(reopened.count(), 2)
        reopened.close()


if __name__ == "__main__":
    unittest.main()
