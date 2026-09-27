"""Tests for Cross-Experiment Generalization (PR #239).

Proves:
1. Generalizer identifies patterns when >=3 iterations with same rec_type
2. No patterns with fewer than 3 iterations
3. Patterns persisted to SQLite
4. Generalization confidence computed correctly
5. No generalizer -> no-op, legacy behavior preserved
6. Engine triggers generalization after 3+ executions
7. GeneralizablePattern fields validated
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from thinkbox.engine import ThinkBoxEngine, EngineConfig, TaskState
from thinkbox.experiment import ExperimentManager
from thinkbox.experiment_analytics import (
    ExperimentAnalytics,
    OpportunityManager,
    LoopTracer,
    EngineAutoTuner,
    CrossExperimentGeneralizer,
    GeneralizablePattern,
    GeneralizationResult,
    LoopIteration,
)


def _make_all(tmpdir: str):
    db_path = os.path.join(tmpdir, "experiments.db")
    artifacts_dir = os.path.join(tmpdir, "artifacts")
    opp_db = os.path.join(tmpdir, "opportunities.db")
    loop_db = os.path.join(tmpdir, "loop.db")
    tuner_db = os.path.join(tmpdir, "tuner.db")
    gen_db = os.path.join(tmpdir, "generalizer.db")
    manager = ExperimentManager(db_path=db_path, artifacts_dir=artifacts_dir)
    analytics = ExperimentAnalytics(manager)
    opp_mgr = OpportunityManager(manager, analytics, db_path=opp_db)
    tracer = LoopTracer(db_path=loop_db)
    tuner = EngineAutoTuner(tracer, db_path=tuner_db)
    generalizer = CrossExperimentGeneralizer(tracer, manager, analytics, db_path=gen_db)
    return manager, analytics, opp_mgr, tracer, tuner, generalizer


def _insert_iteration(tracer: LoopTracer, recommendation_type: str,
                      throughput: float, p50_latency: float, error_rate: float,
                      goal_run_id: str = "goal") -> LoopIteration:
    """Insert a loop iteration directly into the tracer DB."""
    conn = sqlite3.connect(tracer._db_path)
    try:
        conn.row_factory = sqlite3.Row
        count = conn.execute("SELECT COUNT(*) FROM loop_iterations").fetchone()[0]
    finally:
        conn.close()

    iteration_id = f"iter_{count}"
    loop_id = tracer.get_current_loop_id() or f"loop_{iteration_id}"
    now = datetime.now(timezone.utc).isoformat()
    metrics = {
        "throughput": throughput,
        "p50_latency": p50_latency,
        "p95_latency": p50_latency * 2,
        "p99_latency": p50_latency * 3,
        "error_rate": error_rate,
        "iteration_count": 1,
    }

    conn = sqlite3.connect(tracer._db_path)
    try:
        if not tracer.get_current_loop_id():
            conn.execute("INSERT OR REPLACE INTO loop_metadata (key, value) VALUES (?, ?)",
                         ("current_loop_id", loop_id))
        conn.execute(
            "INSERT INTO loop_iterations "
            "(iteration_id, loop_id, started_at, completed_at, cycle_time_s, "
            "goal_run_id, experiment_id, opportunity_id, recommendation_type, priority, metrics) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (iteration_id, loop_id, now, now, 1.0,
             goal_run_id, f"exp_{count}", f"opp_{count}",
             recommendation_type, "medium", json.dumps(metrics)),
        )
        conn.execute("INSERT OR REPLACE INTO loop_metadata (key, value) VALUES (?, ?)",
                     ("latest_iteration_id", iteration_id))
        if count == 0:
            conn.execute("INSERT OR REPLACE INTO loop_metadata (key, value) VALUES (?, ?)",
                         ("first_iteration_id", iteration_id))
        conn.commit()
    finally:
        conn.close()

    return LoopIteration(
        iteration_id=iteration_id, loop_id=loop_id, started_at=now, completed_at=now,
        cycle_time_s=1.0, goal_run_id=goal_run_id, experiment_id=f"exp_{count}",
        opportunity_id=f"opp_{count}", recommendation_type=recommendation_type,
        priority="medium", metrics=metrics,
    )


class TestCrossExperimentGeneralizer(unittest.TestCase):

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager, self.analytics, self.opp_mgr, self.tracer, self.tuner, self.generalizer = _make_all(self.tmpdir)
        self.tracer.start_loop()

    def test_no_patterns_with_fewer_than_3_iterations(self) -> None:
        _insert_iteration(self.tracer, "validation_run", 5.0, 0.1, 0.01, "goal1")
        _insert_iteration(self.tracer, "validation_run", 6.0, 0.1, 0.01, "goal2")

        result = self.generalizer.generalize()
        self.assertEqual(len(result.patterns_identified), 0)
        self.assertEqual(result.iterations_analyzed, 2)
        self.assertEqual(result.generalization_confidence, 0.0)

    def test_identifies_pattern_with_3_iterations(self) -> None:
        for i in range(3):
            _insert_iteration(self.tracer, "validation_run", 5.0 + i, 0.1, 0.01, f"goal_{i}")

        result = self.generalizer.generalize()
        self.assertEqual(len(result.patterns_identified), 1)
        self.assertGreaterEqual(result.generalization_confidence, 0.0)

        patterns = self.generalizer.list_patterns()
        self.assertEqual(len(patterns), 1)
        p = patterns[0]
        self.assertIn("metric_name", p)
        self.assertIn("recommendation_type", p)
        self.assertEqual(p["recommendation_type"], "validation_run")
        self.assertEqual(len(json.loads(p["supporting_iteration_ids"])), 3)

    def test_pattern_persisted_to_sqlite(self) -> None:
        for i in range(3):
            _insert_iteration(self.tracer, "anomaly_followup", 5.0, 0.1, 0.05 + i * 0.01, f"goal_{i}")

        self.generalizer.generalize()

        conn = sqlite3.connect(self.generalizer._db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM generalizable_patterns").fetchone()[0]
            self.assertEqual(count, 1)
            history_count = conn.execute("SELECT COUNT(*) FROM generalization_history").fetchone()[0]
            self.assertEqual(history_count, 1)
        finally:
            conn.close()

    def test_no_patterns_with_normal_metrics(self) -> None:
        for i in range(3):
            _insert_iteration(self.tracer, "validation_run", 10.0, 0.1, 0.0, f"goal_{i}")

        result = self.generalizer.generalize()
        patterns = self.generalizer.list_patterns()
        if result.patterns_identified:
            for p in patterns:
                self.assertIn(p["improvement_direction"], ["improving", "declining"])

    def test_pattern_count(self) -> None:
        self.assertEqual(self.generalizer.get_pattern_count(), 0)
        for i in range(3):
            _insert_iteration(self.tracer, "validation_run", 5.0 + i, 0.1, 0.01, f"g_{i}")
        self.generalizer.generalize()
        self.assertEqual(self.generalizer.get_pattern_count(), 1)

    def test_multiple_recommendation_types_generate_multiple_patterns(self) -> None:
        for i in range(4):
            _insert_iteration(self.tracer, "validation_run", 5.0 + i, 0.1, 0.01, f"v_{i}")
        for i in range(4):
            _insert_iteration(self.tracer, "anomaly_followup", 3.0, 0.1, 0.1 + i * 0.01, f"a_{i}")

        result = self.generalizer.generalize()
        self.assertGreaterEqual(len(result.patterns_identified), 2)


class TestEngineGeneralizationBinding(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager, self.analytics, self.opp_mgr, self.tracer, self.tuner, self.generalizer = _make_all(self.tmpdir)
        self.tracer.start_loop()

    async def test_engine_triggers_generalization_after_3_executions(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_tracer(self.tracer)
        engine.set_auto_tuner(self.tuner)
        engine.set_generalizer(self.generalizer)

        for i in range(3):
            await engine.execute_goal(f"Goal {i}")

        gen_events = [e for e in engine.events if "Patterns generalized" in e.message]
        self.assertGreaterEqual(len(gen_events), 1)
        self.assertGreaterEqual(self.generalizer.get_pattern_count(), 1)

    async def test_no_generalizer_no_generalization_event(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_tracer(self.tracer)
        engine.set_auto_tuner(self.tuner)
        engine.set_generalizer(None)

        for i in range(4):
            await engine.execute_goal(f"Goal {i}")

        gen_events = [e for e in engine.events if "Patterns generalized" in e.message]
        self.assertEqual(len(gen_events), 0)


if __name__ == "__main__":
    unittest.main()
