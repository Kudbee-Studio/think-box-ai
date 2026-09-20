"""Edge case tests for hardened demo modules."""

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
from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.demo_bind import (
    DemoConfig,
    DemoControlPlaneBind,
)


class TestDemoRecordDuplicates(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = f"{self.tmpdir}/demo.db"
        self.conn = sqlite3.connect(self.db_path)
        create_run_table(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_save_duplicate_run_id(self) -> None:
        """Saving a duplicate run_id should not crash — it replaces."""
        record = DemoRunRecord(
            run_id="dup",
            agent_id="demo",
            started_at=datetime.now(timezone.utc).isoformat(),
            scores={"v": 1},
        )
        save_run(self.conn, record)
        record2 = DemoRunRecord(
            run_id="dup",
            agent_id="demo",
            started_at=datetime.now(timezone.utc).isoformat(),
            scores={"v": 2},
        )
        save_run(self.conn, record2)
        loaded = load_run(self.conn, "dup")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["scores"]["v"], 2)

    def test_load_corrupted_scores(self) -> None:
        """If scores JSON is corrupted, load_run returns empty dict."""
        self.conn.execute(
            "INSERT INTO demo_runs (run_id, agent_id, started_at, finished_at, scores, budget_spent, burst_records, grounded, ungrounded, chain_valid, evidence_label) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "corrupt",
                "demo",
                datetime.now(timezone.utc).isoformat(),
                None,
                "not-valid-json{{{",
                0.0,
                0,
                0,
                0,
                0,
                "simulated",
            ),
        )
        self.conn.commit()
        loaded = load_run(self.conn, "corrupt")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["scores"], {})

    def test_last_run_corrupted_scores(self) -> None:
        """If scores JSON is corrupted, last_run returns empty dict."""
        self.conn.execute(
            "INSERT INTO demo_runs (run_id, agent_id, started_at, finished_at, scores, budget_spent, burst_records, grounded, ungrounded, chain_valid, evidence_label) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "last-corrupt",
                "demo",
                datetime.now(timezone.utc).isoformat(),
                None,
                "invalid json",
                0.0,
                0,
                0,
                0,
                0,
                "simulated",
            ),
        )
        self.conn.commit()
        last = last_run(self.conn)
        self.assertIsNotNone(last)
        self.assertEqual(last["run_id"], "last-corrupt")
        self.assertEqual(last["scores"], {})


class TestDemoBindEmptyToken(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ActionReceiptStore(":memory:")
        self.config = DemoConfig(agent_id="test-edge")

    def tearDown(self) -> None:
        self.store.close()

    def test_empty_string_token_rejected(self) -> None:
        """Empty string token must be rejected — not a valid token."""
        import os
        os.environ["THINKBOX_DEMO_TOKEN"] = ""
        bind = DemoControlPlaneBind(self.store, self.config)
        result = bind.admit()
        self.assertFalse(result.admitted)

    def test_empty_env_var_rejected(self) -> None:
        """Missing env var must be rejected."""
        import os
        os.environ.pop("THINKBOX_DEMO_TOKEN", None)
        bind = DemoControlPlaneBind(self.store, self.config)
        result = bind.admit()
        self.assertFalse(result.admitted)

    def test_denied_admit_stays_cached(self) -> None:
        """Once admit() returns denied, it stays denied (cached by design)."""
        import os
        os.environ["THINKBOX_DEMO_TOKEN"] = ""
        bind = DemoControlPlaneBind(self.store, self.config)
        bind.admit()  # rejected
        # Changing token after admit should re-check
        os.environ["THINKBOX_DEMO_TOKEN"] = "dev-only-local-token"
        # But admit() caches — this is by design
        result = bind.admit()
        self.assertFalse(result.admitted)


if __name__ == "__main__":
    unittest.main()
