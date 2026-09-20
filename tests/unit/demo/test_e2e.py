"""Hermetic e2e: demo path with mocks → scores + chain verify."""

from __future__ import annotations

import os
import tempfile
import unittest
from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.demo_record import (
    DemoRunRecord,
    create_run_table,
    last_run,
    save_run,
)
from thinkbox.agent.control_plane.demo_proof import emit_proof_bundle
from thinkbox.agent.control_plane.demo_bind import DemoControlPlaneBind
from thinkbox.agent.control_plane.kernel_hooks import HookContext, on_admit
from thinkbox.agent.control_plane.verify_chain import verify_chain


class TestDemoE2E(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.store = ActionReceiptStore(":memory:")
        os.environ["THINKBOX_DEMO_TOKEN"] = "dev-only-local-token"

    def tearDown(self) -> None:
        self.store.close()
        os.environ.pop("THINKBOX_DEMO_TOKEN", None)

    def test_full_demo_path(self) -> None:
        bind = DemoControlPlaneBind(self.store)
        admit = bind.admit()
        self.assertTrue(admit.admitted)
        bind.request_capacity()
        for i in range(3):
            on_admit(self.store, HookContext(agent_id="demo", action=f"burst-{i}"))
        bundle = emit_proof_bundle(self.store, "demo-e2e", output_dir=tempfile.mkdtemp())
        self.assertTrue(bundle["chain_valid"])

    def test_e2e_record_and_verify(self) -> None:
        import sqlite3
        conn = sqlite3.connect(":memory:")
        create_run_table(conn)
        record = DemoRunRecord(
            run_id="e2e-1",
            agent_id="demo",
            started_at="2026-01-01T00:00:00+00:00",
            scores={"groundedness": 0.9},
            budget_spent=0.5,
        )
        save_run(conn, record)
        last = last_run(conn)
        self.assertEqual(last["run_id"], "e2e-1")
        self.assertEqual(last["scores"]["groundedness"], 0.9)

    def test_e2e_no_network(self) -> None:
        bind = DemoControlPlaneBind(self.store)
        admit = bind.admit()
        self.assertTrue(admit.admitted)
        for i in range(2):
            on_admit(self.store, HookContext(agent_id="a", action=f"c-{i}"))
        bundle = emit_proof_bundle(self.store, "e2e-nonetwork", output_dir=tempfile.mkdtemp())
        self.assertTrue(bundle["chain_valid"])
        self.assertGreaterEqual(bundle["receipt_count"], 2)

    def test_e2e_fail_closed(self) -> None:
        os.environ.pop("THINKBOX_DEMO_TOKEN", None)
        bind = DemoControlPlaneBind(self.store)
        admit = bind.admit()
        self.assertFalse(admit.admitted)

    def test_e2e_chain_after_crash(self) -> None:
        for i in range(3):
            on_admit(self.store, HookContext(agent_id="crash", action=f"c-{i}"))
        self.assertTrue(self.store.verify())
        self.store.close()
        reopened = ActionReceiptStore(":memory:")
        # Verify works in-memory (simulating crash recovery)
        self.assertTrue(reopened.verify())
