"""Tests: demo runs API."""

import unittest
from thinkbox.agent.control_plane.demo_record import (
    DemoRunRecord,
    create_run_table,
    save_run,
)
from thinkbox.agent.control_plane.demo_record import last_run
import sqlite3


class TestDemoRunsAPI(unittest.TestCase):
    def test_list_runs_empty(self) -> None:
        conn = sqlite3.connect(":memory:")
        create_run_table(conn)
        rows = conn.execute("SELECT run_id FROM demo_runs ORDER BY started_at DESC").fetchall()
        conn.close()
        self.assertEqual(len(rows), 0)

    def test_list_runs_nonempty(self) -> None:
        conn = sqlite3.connect(":memory:")
        create_run_table(conn)
        r1 = DemoRunRecord(run_id="run-1", agent_id="demo", started_at="2026-01-01T00:00:00+00:00", scores={})
        r2 = DemoRunRecord(run_id="run-2", agent_id="demo", started_at="2026-01-02T00:00:00+00:00", scores={})
        save_run(conn, r1)
        save_run(conn, r2)
        rows = conn.execute("SELECT run_id FROM demo_runs ORDER BY started_at DESC").fetchall()
        conn.close()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], "run-2")

    def test_get_run(self) -> None:
        conn = sqlite3.connect(":memory:")
        create_run_table(conn)
        record = DemoRunRecord(run_id="run-1", agent_id="demo", started_at="2026-01-01T00:00:00+00:00", scores={"score": 0.9})
        save_run(conn, record)
        loaded = last_run(conn)
        conn.close()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["run_id"], "run-1")
        self.assertEqual(loaded["scores"]["score"], 0.9)

    def test_get_run_not_found(self) -> None:
        conn = sqlite3.connect(":memory:")
        create_run_table(conn)
        loaded = last_run(conn)
        conn.close()
        self.assertIsNone(loaded)

    def test_get_run_proof_structure(self) -> None:
        from thinkbox.agent.control_plane.store import ActionReceiptStore
        from thinkbox.agent.control_plane.kernel_hooks import HookContext, on_admit
        from thinkbox.agent.control_plane.demo_proof import emit_proof_bundle
        store = ActionReceiptStore(":memory:")
        on_admit(store, HookContext(agent_id="run-1", action="admit"))
        bundle = emit_proof_bundle(store, "run-1", output_dir="data/proofs/run-1")
        self.assertIn("jsonl", bundle)
        self.assertIn("manifest", bundle)
        self.assertIn("sha256", bundle)
        self.assertIn("chain_valid", bundle)
