"""E2e hermetic: run → crash (reopen store) → chain verifies + Demo-in-10 emits bundle path."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.export import export_proof_bundle
from thinkbox.agent.control_plane.import_bundle import import_bundle, verify_bundle_offline
from thinkbox.agent.control_plane.verify_chain import verify_chain
from thinkbox.agent.control_plane.kernel_hooks import HookContext, on_admit
from thinkbox.agent.control_plane.budget_trip import BudgetBreaker, BudgetBreakerConfig
from thinkbox.agent.control_plane.kill_events import KillSwitch
from thinkbox.agent.control_plane.lease_evict import Lease, LeaseEvictor


class TestDurableE2E(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "proofs.db")
        self.store = ActionReceiptStore(self.db_path)

    def tearDown(self) -> None:
        self.store.close()

    def test_run_then_reopen_chain_verifies(self) -> None:
        """Run: write receipts. Crash: close/reopen store. Verify: chain still valid."""
        for i in range(5):
            on_admit(
                self.store,
                HookContext(agent_id=f"a{i}", action=f"step-{i}"),
            )
        self.assertTrue(self.store.verify())
        self.store.close()
        reopened = ActionReceiptStore(self.db_path)
        try:
            self.assertTrue(reopened.verify())
            self.assertEqual(reopened.count(), 5)
        finally:
            reopened.close()

    def test_export_bundle_emits_path(self) -> None:
        """Demo-in-10 pattern: receipts → export → bundle path under data/proofs/."""
        for i in range(3):
            on_admit(
                self.store,
                HookContext(agent_id="demo", action=f"burst-{i}"),
            )
        bundle = export_proof_bundle(self.store, output_dir=self.tmpdir, prefix="demo")
        self.assertTrue(Path(bundle["jsonl"]).exists())
        self.assertTrue(Path(bundle["manifest"]).exists())
        self.assertEqual(bundle["receipt_count"], 3)

    def test_bundle_offline_verify_no_network(self) -> None:
        """Import + verify bundle with no network calls."""
        for i in range(4):
            on_admit(
                self.store,
                HookContext(agent_id="offline", action=f"call-{i}"),
            )
        bundle = export_proof_bundle(self.store, output_dir=self.tmpdir, prefix="offline")
        self.store.close()
        reopened = ActionReceiptStore(self.db_path)
        try:
            import_bundle(reopened, bundle["jsonl"])
            result = verify_bundle_offline(bundle["jsonl"])
            self.assertTrue(result["chain_valid"])
            self.assertEqual(result["receipt_count"], 4)
            self.assertTrue(result["offline"])
        finally:
            reopened.close()

    def test_budget_breaker_trips_terminal_receipt(self) -> None:
        config = BudgetBreakerConfig(max_calls=2, cost_per_call=0.01)
        breaker = BudgetBreaker(self.store, config)
        breaker.config.calls = 2
        breaker.config.spend = 0.02
        result = breaker.trip("agent-budget")
        self.assertTrue(result["tripped"])
        self.assertEqual(self.store.count(), 1)
        self.assertTrue(self.store.verify())

    def test_kill_switch_durable(self) -> None:
        ks = KillSwitch(self.store)
        event = ks.kill("agent-kill", reason="test kill")
        self.assertIsNotNone(event.event_id)
        events = ks.query_events(agent_id="agent-kill")
        self.assertEqual(len(events), 1)
        self.assertTrue(self.store.verify())

    def test_lease_expiry_eviction_receipt(self) -> None:
        evictor = LeaseEvictor(self.store)
        lease = Lease(
            agent_id="agent-lease",
            lease_id="lease-1",
            expires_at="2020-01-01T00:00:00+00:00",
        )
        evictor.register_lease(lease)
        self.assertEqual(len(evictor.active_leases()), 0)
        evictions = evictor.check_expired()
        self.assertEqual(len(evictions), 1)
        self.assertTrue(self.store.verify())
        self.assertEqual(self.store.count(), 1)

    def test_durable_across_crash_all_modules(self) -> None:
        """Full e2e: write via all modules, close, reopen, verify all."""
        on_admit(self.store, HookContext(agent_id="a1", action="admit"))
        ks = KillSwitch(self.store)
        ks.kill("a1", reason="crash test")
        self.store.close()
        reopened = ActionReceiptStore(self.db_path)
        try:
            self.assertTrue(reopened.verify())
            self.assertGreaterEqual(reopened.count(), 2)
        finally:
            reopened.close()
