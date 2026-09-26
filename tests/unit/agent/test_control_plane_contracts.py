"""Hermetic contract tests for control-plane store, hooks, and proof bundles."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

# Contract tests must not mutate sys.modules["thinkbox.agent.control_plane.receipt"].
# A failed import after module-level receipt stubs poisoned test_receipt (repair #2).

from thinkbox.agent.control_plane.budget_trip import BudgetBreaker, BudgetBreakerConfig
from thinkbox.agent.control_plane.export import export_proof_bundle
from thinkbox.agent.control_plane.import_bundle import import_bundle
from thinkbox.agent.control_plane.kernel_hooks import HookContext, on_admit, on_capacity, on_shutdown
from thinkbox.agent.control_plane.kill_events import KillSwitch
from thinkbox.agent.control_plane.lease_evict import Lease, LeaseEvictor
from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.verify_chain import verify_chain


class TestControlPlaneContracts(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="cp_contract_")
        self.db_path = os.path.join(self._tmpdir, "receipts.db")

    def tearDown(self) -> None:
        for name in os.listdir(self._tmpdir):
            path = os.path.join(self._tmpdir, name)
            if os.path.isfile(path):
                os.remove(path)
        os.rmdir(self._tmpdir)

    def test_ledger_empty_verify(self) -> None:
        store = ActionReceiptStore(db_path=self.db_path)
        self.assertTrue(store.verify())
        self.assertEqual(store.count(), 0)
        store.close()

    def test_ledger_append_verify(self) -> None:
        store = ActionReceiptStore(db_path=self.db_path)
        store.append(
            action="test",
            status="OK",
            reason="ok",
            evidence_label="simulated",
        )
        self.assertTrue(store.verify())
        self.assertEqual(store.count(), 1)
        store.close()

    def test_ledger_tamper(self) -> None:
        store = ActionReceiptStore(db_path=self.db_path)
        store.append(
            action="A",
            status="OK",
            reason="ok",
            evidence_label="simulated",
        )
        conn = store._conn
        conn.execute("UPDATE receipts SET entry_hash = 'TAMPERED' WHERE receipt_id IS NOT NULL")
        conn.commit()
        self.assertFalse(store.verify())
        store.close()

    def test_chain_verifier_empty(self) -> None:
        store = ActionReceiptStore(db_path=self.db_path)
        result = verify_chain(store)
        self.assertTrue(result.valid)
        self.assertEqual(result.receipts, 0)
        store.close()

    def test_chain_verifier_valid(self) -> None:
        store = ActionReceiptStore(db_path=self.db_path)
        store.append(
            action="A",
            status="OK",
            reason="ok",
            evidence_label="simulated",
        )
        result = verify_chain(store)
        self.assertTrue(result.valid)
        store.close()

    def test_kernel_hooks_admit(self) -> None:
        store = ActionReceiptStore(db_path=self.db_path)
        on_admit(
            store,
            HookContext(agent_id="agent-1", action="AGENT_SPAWN", reason="admitted"),
        )
        self.assertEqual(store.count(), 1)
        store.close()

    def test_kernel_hooks_capacity(self) -> None:
        store = ActionReceiptStore(db_path=self.db_path)
        on_capacity(
            store,
            HookContext(agent_id="agent-1", action="capacity", reason="granted"),
        )
        self.assertEqual(store.count(), 1)
        store.close()

    def test_kernel_hooks_shutdown(self) -> None:
        store = ActionReceiptStore(db_path=self.db_path)
        on_shutdown(
            store,
            HookContext(agent_id="agent-1", action="shutdown", reason="normal"),
        )
        self.assertEqual(store.count(), 1)
        store.close()

    def test_budget_trip_handler(self) -> None:
        store = ActionReceiptStore(db_path=self.db_path)
        config = BudgetBreakerConfig(max_calls=1, max_spend=0.0, calls=1, spend=0.0)
        breaker = BudgetBreaker(store, config=config)
        result = breaker.trip("agent-1")
        self.assertTrue(result["tripped"])
        self.assertGreaterEqual(store.count(), 1)
        store.close()

    def test_kill_event_store(self) -> None:
        store = ActionReceiptStore(db_path=self.db_path)
        ks = KillSwitch(store)
        evt = ks.kill("agent-1", reason="test")
        self.assertEqual(evt.agent_id, "agent-1")
        self.assertGreaterEqual(store.count(), 1)
        store.close()

    def test_lease_eviction_handler(self) -> None:
        store = ActionReceiptStore(db_path=self.db_path)
        evictor = LeaseEvictor(store)
        past = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
        evictor.register_lease(
            Lease(agent_id="agent-1", lease_id="lease-1", expires_at=past),
        )
        evictions = evictor.check_expired()
        self.assertEqual(len(evictions), 1)
        self.assertGreaterEqual(store.count(), 1)
        store.close()

    def test_bundle_export_import(self) -> None:
        store = ActionReceiptStore(db_path=self.db_path)
        store.append(
            action="A",
            status="OK",
            reason="ok",
            evidence_label="simulated",
        )
        bundle = export_proof_bundle(store, output_dir=self._tmpdir, prefix="test-bundle")
        self.assertTrue(bundle["chain_valid"])

        imported_store = ActionReceiptStore(db_path=os.path.join(self._tmpdir, "imported.db"))
        result = import_bundle(imported_store, bundle["jsonl"])
        self.assertEqual(result["imported"], 1)
        self.assertTrue(imported_store.verify())
        store.close()
        imported_store.close()

    def test_chain_verify_after_import(self) -> None:
        store = ActionReceiptStore(db_path=self.db_path)
        store.append(
            action="A",
            status="OK",
            reason="ok",
            evidence_label="simulated",
        )
        store.append(
            action="B",
            status="OK",
            reason="ok",
            evidence_label="simulated",
        )
        store.close()
        reopened = ActionReceiptStore(db_path=self.db_path)
        self.assertTrue(reopened.verify())
        self.assertEqual(reopened.count(), 2)
        reopened.close()

    def test_receipt_module_not_stubbed_in_sys_modules(self) -> None:
        """Guard: contract tests must never replace the real receipt module."""
        import importlib

        importlib.import_module("thinkbox.agent.control_plane.receipt")
        mod = sys.modules.get("thinkbox.agent.control_plane.receipt")
        self.assertIsNotNone(mod)
        self.assertTrue(str(getattr(mod, "__file__", "")).endswith("receipt.py"))
        from thinkbox.agent.control_plane.receipt import ActionReceipt

        receipt = ActionReceipt("CAPACITY", "a1", "OK")
        self.assertEqual(receipt.action_type, "CAPACITY")


if __name__ == "__main__":
    unittest.main()
