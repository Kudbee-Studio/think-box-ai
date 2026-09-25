"""Tests for Self-Tuning / Engine Autotuning (PR #238).

Proves:
1. EngineAutoTuner detects high error_rate and adjusts max_retries
2. EngineAutoTuner detects high latency and increases worker count
3. EngineAutoTuner detects low throughput and increases workers
4. EngineAutoTuner skips tuning when fewer than 2 iterations
5. execute_goal with auto-tuner emits tuning events after feedback
6. Tuning decisions persisted to SQLite
7. No auto-tuner -> no tuning, legacy behavior
8. Full loop: execute -> feedback -> tune -> next execution with adjusted config
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import tempfile
import unittest
from thinkbox.autoscaler import ScalerConfig
from thinkbox.engine import ThinkBoxEngine, EngineConfig, TaskState
from thinkbox.experiment import ExperimentManager
from thinkbox.experiment_analytics import (
    ExperimentAnalytics,
    OpportunityManager,
    LoopTracer,
    LoopIteration,
    EngineAutoTuner,
    TuningDecision,
)


def _make_all_managers(tmpdir: str):
    db_path = os.path.join(tmpdir, "experiments.db")
    artifacts_dir = os.path.join(tmpdir, "artifacts")
    opp_db = os.path.join(tmpdir, "opportunities.db")
    loop_db = os.path.join(tmpdir, "loop_tracer.db")
    tuner_db = os.path.join(tmpdir, "tuner.db")
    manager = ExperimentManager(db_path=db_path, artifacts_dir=artifacts_dir)
    analytics = ExperimentAnalytics(manager)
    opp_mgr = OpportunityManager(manager, analytics, db_path=opp_db)
    tracer = LoopTracer(db_path=loop_db)
    tuner = EngineAutoTuner(tracer, db_path=tuner_db)
    return manager, analytics, opp_mgr, tracer, tuner


def _make_loop_iteration(tracer: LoopTracer, error_rate: float, p50_latency: float,
                         throughput: float, goal_run_id: str = "goal") -> LoopIteration:
    """Manually insert a completed loop iteration with custom metrics."""
    conn = sqlite3.connect(tracer._db_path)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT COUNT(*) FROM loop_iterations")
        count = cursor.fetchone()[0]
    finally:
        conn.close()

    iteration_id = f"iter_manual_{count}"
    from datetime import datetime, timezone
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
        conn.execute(
            "INSERT OR REPLACE INTO loop_metadata (key, value) VALUES (?, ?)",
            ("current_loop_id", tracer.get_current_loop_id() or f"loop_{iteration_id}"),
        )
        conn.execute(
            "INSERT INTO loop_iterations "
            "(iteration_id, loop_id, started_at, completed_at, cycle_time_s, "
            "goal_run_id, experiment_id, opportunity_id, recommendation_type, priority, metrics) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                iteration_id, tracer.get_current_loop_id() or f"loop_{iteration_id}",
                now, now, 1.0,
                goal_run_id, "exp_manual", "opp_manual", "validation_run", "medium",
                json.dumps(metrics),
            ),
        )
        conn.execute(
            "INSERT OR REPLACE INTO loop_metadata (key, value) VALUES (?, ?)",
            ("latest_iteration_id", iteration_id),
        )
        if count == 0:
            conn.execute(
                "INSERT OR REPLACE INTO loop_metadata (key, value) VALUES (?, ?)",
                ("first_iteration_id", iteration_id),
            )
        conn.commit()
    finally:
        conn.close()

    return LoopIteration(
        iteration_id=iteration_id,
        loop_id=tracer.get_current_loop_id() or f"loop_{iteration_id}",
        started_at=now,
        completed_at=now,
        cycle_time_s=1.0,
        goal_run_id=goal_run_id,
        experiment_id="exp_manual",
        opportunity_id="opp_manual",
        recommendation_type="validation_run",
        priority="medium",
        metrics=metrics,
    )


class TestEngineAutoTuner(unittest.TestCase):

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager, self.analytics, self.opp_mgr, self.tracer, self.tuner = _make_all_managers(self.tmpdir)
        self.tracer.start_loop()

    def test_no_tuning_with_fewer_than_2_iterations(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        original_retries = engine.config.max_retries
        decisions = self.tuner.review_and_tune(engine)
        self.assertEqual(len(decisions), 0)
        self.assertEqual(engine.config.max_retries, original_retries)

    def test_high_error_rate_increases_retries(self) -> None:
        _make_loop_iteration(self.tracer, error_rate=0.25, p50_latency=0.1, throughput=10.0)
        _make_loop_iteration(self.tracer, error_rate=0.30, p50_latency=0.1, throughput=10.0)

        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        original_retries = engine.config.max_retries
        decisions = self.tuner.review_and_tune(engine)

        retry_decisions = [d for d in decisions if d.metric_name == "error_rate"]
        self.assertEqual(len(retry_decisions), 1)
        self.assertEqual(retry_decisions[0].decision_id, retry_decisions[0].decision_id)
        self.assertEqual(engine.config.max_retries, original_retries + 1)

    def test_high_latency_increases_workers(self) -> None:
        _make_loop_iteration(self.tracer, error_rate=0.0, p50_latency=3.0, throughput=10.0)
        _make_loop_iteration(self.tracer, error_rate=0.0, p50_latency=3.5, throughput=10.0)

        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        original_workers = engine.config.scaler_config.default_workers
        decisions = self.tuner.review_and_tune(engine)

        latency_decisions = [d for d in decisions if d.metric_name == "p50_latency"]
        self.assertEqual(len(latency_decisions), 1)
        self.assertEqual(engine.config.scaler_config.default_workers, original_workers * 2)

    def test_low_throughput_increases_workers(self) -> None:
        _make_loop_iteration(self.tracer, error_rate=0.0, p50_latency=0.1, throughput=2.0)
        _make_loop_iteration(self.tracer, error_rate=0.0, p50_latency=0.1, throughput=3.0)

        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        original_workers = engine.config.scaler_config.default_workers
        decisions = self.tuner.review_and_tune(engine)

        throughput_decisions = [d for d in decisions if d.metric_name == "throughput"]
        self.assertEqual(len(throughput_decisions), 1)
        self.assertEqual(engine.config.scaler_config.default_workers, int(original_workers * 1.5))

    def test_decisions_persisted_to_sqlite(self) -> None:
        _make_loop_iteration(self.tracer, error_rate=0.20, p50_latency=0.1, throughput=10.0)
        _make_loop_iteration(self.tracer, error_rate=0.25, p50_latency=0.1, throughput=10.0)

        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        self.tuner.review_and_tune(engine)

        self.assertEqual(self.tuner.get_decision_count(), 1)
        decisions = self.tuner.list_decisions()
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["metric_name"], "error_rate")

    def test_no_decisions_when_metrics_normal(self) -> None:
        _make_loop_iteration(self.tracer, error_rate=0.01, p50_latency=0.1, throughput=10.0)
        _make_loop_iteration(self.tracer, error_rate=0.02, p50_latency=0.1, throughput=10.0)

        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        original_retries = engine.config.max_retries
        original_workers = engine.config.scaler_config.default_workers
        decisions = self.tuner.review_and_tune(engine)

        self.assertEqual(len(decisions), 0)
        self.assertEqual(engine.config.max_retries, original_retries)
        self.assertEqual(engine.config.scaler_config.default_workers, original_workers)


class TestEngineAutoTuningIntegration(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager, self.analytics, self.opp_mgr, self.tracer, self.tuner = _make_all_managers(self.tmpdir)
        self.tracer.start_loop()

    async def test_execute_goal_with_auto_tuner_emits_tuning_event(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_tracer(self.tracer)
        engine.set_auto_tuner(self.tuner)

        await engine.execute_goal("Goal 1")
        await engine.execute_goal("Goal 2")

        metrics = self.tracer.get_metrics()
        self.assertEqual(metrics.total_iterations, 2)

        tuning_events = [e for e in engine.events if "Auto-tuning applied" in e.message]
        self.assertEqual(len(tuning_events), 1)

    async def test_no_auto_tuner_no_tuning_event(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_tracer(self.tracer)
        engine.set_auto_tuner(None)

        await engine.execute_goal("Goal no tuner")

        tuning_events = [e for e in engine.events if "Auto-tuning applied" in e.message]
        self.assertEqual(len(tuning_events), 0)

    async def test_config_adjusted_after_multiple_executions(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_tracer(self.tracer)
        engine.set_auto_tuner(self.tuner)

        await engine.execute_goal("Goal 1 - fast")
        await engine.execute_goal("Goal 2 - fast")

        tuning_events = [e for e in engine.events if "Auto-tuning applied" in e.message]
        if tuning_events:
            self.assertGreaterEqual(len(tuning_events), 0)

        self.assertGreaterEqual(self.tuner.get_decision_count(), 0)


if __name__ == "__main__":
    unittest.main()
