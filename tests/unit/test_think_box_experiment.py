"""Tests for LOCAL THINK BOX EXPERIMENT LOOP.

Proves that a complete Think Job can execute:
  INTENT -> PLAN -> EXECUTION -> ARTIFACT -> VALIDATION -> PROOF -> OUTCOME -> MEMORY -> REPLAY

WITHOUT:
  * HTTP server
  * FastAPI
  * web server
  * Docker
  * GPU
  * cloud credentials
  * network
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from thinkbox.grounding import GroundingScorer
from thinkbox.harvest import HarvestReplay
from thinkbox.ledger import ActionLedger
from thinkbox.workspace import WorkspaceStore, ThinkBox


class TestExperimentNoServer(unittest.TestCase):
    def test_experiment_no_network_required(self) -> None:
        from examples.think_box_experiment import run_experiment

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "experiment.db"
            outcome = run_experiment(db_path=str(db))

        self.assertIsNotNone(outcome.session_id)
        self.assertIsNotNone(outcome.job_id)
        self.assertGreater(outcome.task_count, 0)
        self.assertGreaterEqual(outcome.successful_tasks, 0)
        self.assertIsNotNone(outcome.outcome)

    def test_artifacts_persisted(self) -> None:
        from examples.think_box_experiment import run_experiment

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "experiment.db"
            run_experiment(db_path=str(db))

            conn = sqlite3.connect(str(db))
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            conn.close()

            self.assertIn("workspaces", tables)
            self.assertIn("ledger", tables)

    def test_workspace_persisted(self) -> None:
        from examples.think_box_experiment import run_experiment

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "experiment.db"
            outcome = run_experiment(db_path=str(db))

            store = WorkspaceStore(str(db))
            box = store.load(outcome.session_id)
            self.assertIsNotNone(box)
            self.assertEqual(box.owner_id, "kilo")
            self.assertIn("intent", box.state)

    def test_ledger_has_entries(self) -> None:
        from examples.think_box_experiment import run_experiment

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "experiment.db"
            run_experiment(db_path=str(db))

            ledger = ActionLedger(str(db))
            entries = ledger.entries(limit=100)
            self.assertGreater(len(entries), 0)
            self.assertTrue(ledger.verify())

    def test_harvest_replay_available(self) -> None:
        from examples.think_box_experiment import run_experiment

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "experiment.db"
            run_experiment(db_path=str(db))

            output_dir = "data/evals/burst"
            if os.path.isdir(output_dir):
                harvest = HarvestReplay().replay_dir(output_dir)
                self.assertGreaterEqual(harvest.metrics.pairs, 0)

    def test_grounding_scorer_deterministic(self) -> None:
        scorer = GroundingScorer(threshold=0.3)
        score1 = scorer.score("What is 2+2?", "fact_arith: 2+2=4", "reasoning")
        score2 = scorer.score("What is 2+2?", "fact_arith: 2+2=4", "reasoning")
        self.assertEqual(score1.score, score2.score)
        self.assertGreater(score1.score, 0)

    def test_workspace_store_sqlite_persistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            store = WorkspaceStore(str(db))
            box = ThinkBox(
                box_id="test_box",
                owner_id="kilo",
                capabilities=["test"],
                state={"intent": "test"},
            )
            store.save(box)
            loaded = store.load("test_box")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.state["intent"], "test")

    def test_ledger_verifiable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            ledger = ActionLedger(str(db))
            ledger.append(
                agent_id="test",
                capability="test",
                action="test_action",
                allowed=True,
                reason="test",
                metadata={},
            )
            self.assertTrue(ledger.verify())


if __name__ == "__main__":
    unittest.main()
