"""Tests for Loop Measurement & Observability (PR #237).

Proves:
1. LoopTracer records iterations with cycle time and traceability
2. execute_goal with LoopTracer traces the full cycle
3. Loop metrics aggregate correctly (total iterations, avg cycle time, etc.)
4. Recommendation traceability (which recommendation drove which goal)
5. No LoopTracer -> no tracing, legacy behavior preserved
6. Full autonomous loop observability: execute -> feedback -> opportunity -> trace -> next execution
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch

from thinkbox.engine import ThinkBoxEngine, EngineConfig, TaskState
from thinkbox.experiment import ExperimentManager
from thinkbox.experiment_analytics import (
    ExperimentAnalytics,
    OpportunityManager,
    LoopTracer,
    LoopIteration,
    LoopMetrics,
)


def _make_all_managers(tmpdir: str):
    db_path = os.path.join(tmpdir, "experiments.db")
    artifacts_dir = os.path.join(tmpdir, "artifacts")
    opp_db = os.path.join(tmpdir, "opportunities.db")
    loop_db = os.path.join(tmpdir, "loop_tracer.db")
    manager = ExperimentManager(db_path=db_path, artifacts_dir=artifacts_dir)
    analytics = ExperimentAnalytics(manager)
    opp_mgr = OpportunityManager(manager, analytics, db_path=opp_db)
    tracer = LoopTracer(db_path=loop_db)
    return manager, analytics, opp_mgr, tracer


class TestLoopTracer(unittest.TestCase):

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager, self.analytics, self.opp_mgr, self.tracer = _make_all_managers(self.tmpdir)

    def test_start_and_complete_iteration(self) -> None:
        loop_id = self.tracer.start_loop()
        self.assertEqual(self.tracer.get_current_loop_id(), loop_id)

        iteration_id = self.tracer.start_iteration("goal_test", loop_id=loop_id)
        self.assertTrue(iteration_id.startswith("iter_"))

        rec = {"type": "validation_run", "rationale": "ok", "max_retries": 1}
        metrics = {"throughput": 10.0, "p50_latency": 0.1, "error_rate": 0.0, "iteration_count": 1}
        iteration = self.tracer.complete_iteration(
            iteration_id=iteration_id,
            experiment_id="exp_test",
            opportunity_id="opp_test",
            recommendation_type="validation_run",
            priority="medium",
            metrics=metrics,
        )
        self.assertIsInstance(iteration, LoopIteration)
        self.assertEqual(iteration.iteration_id, iteration_id)
        self.assertEqual(iteration.experiment_id, "exp_test")
        self.assertEqual(iteration.opportunity_id, "opp_test")
        self.assertEqual(iteration.recommendation_type, "validation_run")
        self.assertEqual(iteration.priority, "medium")
        self.assertGreaterEqual(iteration.cycle_time_s, 0.0)

    def test_get_iteration(self) -> None:
        loop_id = self.tracer.start_loop()
        iteration_id = self.tracer.start_iteration("goal_get", loop_id=loop_id)
        metrics = {"throughput": 10.0, "p50_latency": 0.1, "error_rate": 0.0, "iteration_count": 1}
        self.tracer.complete_iteration(
            iteration_id=iteration_id,
            experiment_id="exp1",
            opportunity_id="opp1",
            recommendation_type="anomaly_followup",
            priority="high",
            metrics=metrics,
        )

        retrieved = self.tracer.get_iteration(iteration_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.recommendation_type, "anomaly_followup")
        self.assertEqual(retrieved.priority, "high")

    def test_list_iterations(self) -> None:
        loop_id = self.tracer.start_loop()
        metrics = {"throughput": 10.0, "p50_latency": 0.1, "error_rate": 0.0, "iteration_count": 1}
        for i in range(3):
            iteration_id = self.tracer.start_iteration(f"goal_{i}", loop_id=loop_id)
            self.tracer.complete_iteration(
                iteration_id=iteration_id,
                experiment_id=f"exp_{i}",
                opportunity_id=f"opp_{i}",
                recommendation_type="validation_run",
                priority="medium",
                metrics=metrics,
            )
        iterations = self.tracer.list_iterations(loop_id=loop_id)
        self.assertEqual(len(iterations), 3)

    def test_get_metrics(self) -> None:
        loop_id = self.tracer.start_loop()
        metrics = {"throughput": 10.0, "p50_latency": 0.1, "error_rate": 0.0, "iteration_count": 1}
        iterations = []
        for i in range(5):
            iteration_id = self.tracer.start_iteration(f"goal_{i}", loop_id=loop_id)
            iterations.append(iteration_id)
            self.tracer.complete_iteration(
                iteration_id=iteration_id,
                experiment_id=f"exp_{i}",
                opportunity_id=f"opp_{i}",
                recommendation_type="validation_run" if i % 2 == 0 else "anomaly_followup",
                priority="medium" if i % 2 == 0 else "high",
                metrics=metrics,
            )

        loop_metrics = self.tracer.get_metrics()
        self.assertIsInstance(loop_metrics, LoopMetrics)
        self.assertEqual(loop_metrics.total_iterations, 5)
        self.assertGreaterEqual(loop_metrics.avg_cycle_time_s, 0.0)
        self.assertEqual(loop_metrics.recommendation_types["validation_run"], 3)
        self.assertEqual(loop_metrics.recommendation_types["anomaly_followup"], 2)
        self.assertEqual(loop_metrics.priority_distribution["medium"], 3)
        self.assertEqual(loop_metrics.priority_distribution["high"], 2)
        self.assertEqual(loop_metrics.first_iteration_id, iterations[0])
        self.assertEqual(loop_metrics.latest_iteration_id, iterations[4])

    def test_complete_iteration_invalid_id_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.tracer.complete_iteration(
                iteration_id="nonexistent",
                experiment_id="exp1",
                opportunity_id="opp1",
                recommendation_type="validation_run",
                priority="medium",
                metrics={"throughput": 10.0},
            )

    def test_empty_metrics(self) -> None:
        metrics = self.tracer.get_metrics()
        self.assertEqual(metrics.total_iterations, 0)
        self.assertEqual(metrics.recommendation_types, {})


class TestEngineLoopTracing(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager, self.analytics, self.opp_mgr, self.tracer = _make_all_managers(self.tmpdir)

    async def test_execute_goal_traces_loop_iteration(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_tracer(self.tracer)

        await engine.execute_goal("Test goal with tracing")

        trace_events = [e for e in engine.events if "Loop iteration traced" in e.message]
        self.assertEqual(len(trace_events), 1)

        metrics = self.tracer.get_metrics()
        self.assertEqual(metrics.total_iterations, 1)

    async def test_traced_iteration_has_experiment_and_opportunity(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_tracer(self.tracer)

        await engine.execute_goal("Test goal traceability")

        iterations = self.tracer.list_iterations()
        self.assertEqual(len(iterations), 1)
        it = iterations[0]
        self.assertTrue(it.experiment_id.startswith("tb_exp_"))
        self.assertTrue(it.opportunity_id.startswith("opp_"))
        self.assertIn(it.recommendation_type, {"validation_run", "anomaly_followup", "regression_followup"})

    async def test_no_tracer_no_tracing(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_tracer(None)

        await engine.execute_goal("Test no tracer")

        trace_events = [e for e in engine.events if "Loop iteration traced" in e.message]
        self.assertEqual(len(trace_events), 0)
        self.assertEqual(self.tracer.get_metrics().total_iterations, 0)

    async def test_full_loop_observability(self) -> None:
        """Full loop: execute -> feedback -> opportunity -> trace -> next execute consumes opportunity."""
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_tracer(self.tracer)
        self.tracer.start_loop()

        await engine.execute_goal("First goal")
        metrics1 = self.tracer.get_metrics()
        self.assertEqual(metrics1.total_iterations, 1)

        await engine.execute_goal("Second goal consuming opportunity")
        metrics2 = self.tracer.get_metrics()
        self.assertEqual(metrics2.total_iterations, 2)

        consume_events = [e for e in engine.events if "Consuming current opportunity" in e.message]
        self.assertEqual(len(consume_events), 1)
        trace_events = [e for e in engine.events if "Loop iteration traced" in e.message]
        self.assertEqual(len(trace_events), 2)

    async def test_traced_iteration_persists_across_restart(self) -> None:
        engine1 = ThinkBoxEngine(EngineConfig(speculative=False))
        engine1.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine1.set_loop_tracer(self.tracer)
        self.tracer.start_loop()

        await engine1.execute_goal("First goal")
        metrics1 = self.tracer.get_metrics()
        self.assertEqual(metrics1.total_iterations, 1)

        fresh_mgr, fresh_an, fresh_opp, fresh_tracer = _make_all_managers(self.tmpdir)
        engine2 = ThinkBoxEngine(EngineConfig(speculative=False))
        engine2.wire_experiment_feedback(fresh_mgr, fresh_an, fresh_opp)
        engine2.set_loop_tracer(fresh_tracer)

        await engine2.execute_goal("Second goal")
        metrics2 = fresh_tracer.get_metrics()
        self.assertEqual(metrics2.total_iterations, 2)


if __name__ == "__main__":
    unittest.main()
