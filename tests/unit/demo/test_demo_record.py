"""Tests: DemoRunRecord + SQLite persistence."""

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from thinkbox.agent.control_plane.demo_record import (
    DemoRunRecord,
    create_run_table,
    save_run,
    load_run,
    last_run,
)


class TestDemoRunRecord(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = f"{self.tmpdir}/demo.db"
        self.conn = sqlite3.connect(self.db_path)
        create_run_table(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_save_and_load(self) -> None:
        record = DemoRunRecord(
            run_id="run-1",
            agent_id="demo",
            started_at=datetime.now(timezone.utc).isoformat(),
            scores={"groundedness": 0.9},
            budget_spent=0.5,
        )
        save_run(self.conn, record)
        loaded = load_run(self.conn, "run-1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["run_id"], "run-1")
        self.assertEqual(loaded["agent_id"], "demo")
        self.assertEqual(loaded["scores"]["groundedness"], 0.9)

    def test_last_run(self) -> None:
        r1 = DemoRunRecord(run_id="r1", agent_id="demo", started_at="2026-01-01T00:00:00+00:00", scores={})
        r2 = DemoRunRecord(run_id="r2", agent_id="demo", started_at="2026-01-02T00:00:00+00:00", scores={})
        save_run(self.conn, r1)
        save_run(self.conn, r2)
        last = last_run(self.conn)
        self.assertEqual(last["run_id"], "r2")

    def test_load_missing(self) -> None:
        self.assertIsNone(load_run(self.conn, "nonexistent"))

    def test_last_run_empty(self) -> None:
        self.assertIsNone(last_run(self.conn))

    def test_chain_valid_flag(self) -> None:
        record = DemoRunRecord(
            run_id="r3",
            agent_id="demo",
            started_at=datetime.now(timezone.utc).isoformat(),
            chain_valid=True,
        )
        save_run(self.conn, record)
        loaded = load_run(self.conn, "r3")
        self.assertTrue(loaded["chain_valid"])

    def test_default_fields(self) -> None:
        record = DemoRunRecord(
            run_id="r4",
            agent_id="demo",
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self.assertEqual(record.budget_spent, 0.0)
        self.assertEqual(record.burst_records, 0)
        self.assertEqual(record.grounded, 0)
        self.assertEqual(record.ungrounded, 0)
        self.assertFalse(record.chain_valid)
