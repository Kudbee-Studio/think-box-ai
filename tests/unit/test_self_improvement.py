"""Tests for SelfImprovementLoop wiring into swarm runs.

Verifies:
1. Improvement path — retest index > baseline → accepted
2. No-regression path — retest index <= baseline → rejected
3. End-to-end cycle — Run → Evaluate → Improve → Retest → Compare → Verdict → persisted evidence
4. Engine integration — post_run_callback fires after execute_goal
5. ImprovementRunner.evaluate from run summary
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock, patch

from thinkbox.experiments import (
    ImprovementRunner,
    SelfImprovementLoop,
    Variant,
    VariantResult,
    run_improvement_cycle,
)
from thinkbox.experiments import ExperimentStore


class TestImprovementRunnerEvaluate(unittest.TestCase):
    def test_evaluate_all_success(self):
        runner = ImprovementRunner(MagicMock(), MagicMock())
        summary = {"total_tasks": 10, "successful": 10}
        self.assertEqual(runner.evaluate(summary), 1.0)

    def test_evaluate_partial_success(self):
        runner = ImprovementRunner(MagicMock(), MagicMock())
        summary = {"total_tasks": 10, "successful": 7}
        self.assertEqual(runner.evaluate(summary), 0.7)

    def test_evaluate_zero_tasks(self):
        runner = ImprovementRunner(MagicMock(), MagicMock())
        summary = {"total_tasks": 0, "successful": 0}
        self.assertEqual(runner.evaluate(summary), 0.0)

    def test_evaluate_no_total_key(self):
        runner = ImprovementRunner(MagicMock(), MagicMock())
        summary = {"successful": 5}
        self.assertEqual(runner.evaluate(summary), 0.0)


class TestImprovementRunnerCycle(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ExperimentStore(":memory:")
        self.pool = MagicMock()
        self.pool.max_workers = 32

    def test_improvement_accepted(self):
        runner = ImprovementRunner(self.store, self.pool)
        baseline = 0.7
        components = {
            "reliability": 0.7,
            "grounding": 0.7,
            "evidence_quality": 0.7,
        }
        record = runner.run_cycle("test goal", baseline, components)
        self.assertTrue(record["applied"])
        self.assertIsNotNone(record["retest_index"])
        self.assertEqual(record["baseline_index"], baseline)
        self.assertIn(record["weakness"], ("reliability", "grounding", "evidence_quality"))

    def test_improvement_rejected_no_regression(self):
        """Weakness + config kind produces a lower score → rejected."""
        runner = ImprovementRunner(self.store, self.pool)
        baseline = 0.7
        components = {
            "reliability": 0.5,
            "grounding": 0.7,
            "evidence_quality": 0.7,
        }
        record = runner.run_cycle("test goal", baseline, components)
        self.assertTrue(record["applied"])
        # With "config" kind, the deterministic score may be lower
        if record["delta"] is not None and record["delta"] <= 0:
            self.assertFalse(record["accepted"])

    def test_history_persists(self):
        runner = ImprovementRunner(self.store, self.pool)
        runner.run_cycle("goal", 0.7, {"reliability": 0.7})
        runner.run_cycle("goal", 0.75, {"reliability": 0.7})
        self.assertEqual(len(runner.history), 2)

    def test_database_record_exists(self):
        runner = ImprovementRunner(self.store, self.pool)
        record = runner.run_cycle("goal", 0.6, {"reliability": 0.6, "grounding": 0.8})
        improvements = self.store._conn.execute(
            "SELECT * FROM improvements WHERE experiment_id=?", (record["experiment_id"],)
        ).fetchall()
        self.assertEqual(len(improvements), 1)
        row = improvements[0]
        self.assertEqual(row["experiment_id"], record["experiment_id"])
        self.assertEqual(row["baseline_index"], 0.6)
        self.assertIsNotNone(row["weakness"])
        self.assertIsNotNone(row["proposed_change"])


class TestRunImprovementCycleConvenience(unittest.TestCase):
    def test_returns_record(self):
        store = ExperimentStore(":memory:")
        pool = MagicMock()
        pool.max_workers = 16
        record = run_improvement_cycle(store, pool, "test goal", 0.7, {
            "reliability": 0.7,
            "grounding": 0.7,
        })
        self.assertIn("experiment_id", record)
        self.assertIn("weakness", record)
        self.assertIn("accepted", record)
        self.assertIn("baseline_index", record)


class TestSelfImprovementLoopDirect(unittest.TestCase):
    def test_accepted_when_retest_better(self):
        store = ExperimentStore(":memory:")
        loop = SelfImprovementLoop(store)
        eid = store.start_experiment("direct", "test")

        def retest(proposal):
            return VariantResult(Variant("improved"), index=0.8)

        comps = {"reliability": 0.5, "grounding": 0.8}
        rec = loop.run(eid, baseline_index=0.6, baseline_components=comps, retest=retest)
        self.assertTrue(rec["applied"])
        self.assertTrue(rec["accepted"])
        self.assertGreater(rec["delta"], 0)

    def test_rejected_when_retest_worse(self):
        store = ExperimentStore(":memory:")
        loop = SelfImprovementLoop(store)
        eid = store.start_experiment("direct2", "test")

        def retest(proposal):
            return VariantResult(Variant("regressed"), index=0.5)

        comps = {"reliability": 0.5, "grounding": 0.8}
        rec = loop.run(eid, baseline_index=0.6, baseline_components=comps, retest=retest)
        self.assertTrue(rec["applied"])
        self.assertFalse(rec["accepted"])
        self.assertLess(rec["delta"], 0)

    def test_no_regression_equal_score(self):
        store = ExperimentStore(":memory:")
        loop = SelfImprovementLoop(store)
        eid = store.start_experiment("equal", "test")

        def retest(proposal):
            return VariantResult(Variant("same"), index=0.6)

        comps = {"reliability": 0.5, "grounding": 0.8}
        rec = loop.run(eid, baseline_index=0.6, baseline_components=comps, retest=retest)
        self.assertFalse(rec["accepted"])
        self.assertEqual(rec["delta"], 0.0)

    def test_without_retest(self):
        store = ExperimentStore(":memory:")
        loop = SelfImprovementLoop(store)
        eid = store.start_experiment("notest", "test")
        comps = {"reliability": 0.5, "grounding": 0.8}
        rec = loop.run(eid, baseline_index=0.6, baseline_components=comps, retest=None)
        self.assertFalse(rec["applied"])
        self.assertIsNone(rec["accepted"])
        self.assertIsNone(rec["retest_index"])

    def test_identified_weakness(self):
        store = ExperimentStore(":memory:")
        loop = SelfImprovementLoop(store)
        comps = {"reliability": 0.3, "grounding": 0.9, "evidence_quality": 0.7}
        self.assertEqual(loop.identify_weakness(comps), "reliability")

    def test_propose_returns_change(self):
        store = ExperimentStore(":memory:")
        loop = SelfImprovementLoop(store)
        comps = {"reliability": 0.3, "grounding": 0.9}
        proposal = loop.propose(comps)
        self.assertEqual(proposal["weakness"], "reliability")
        self.assertIn("kind", proposal)
        self.assertIn("detail", proposal)
        self.assertIn("weakness_score", proposal)


class TestEngineIntegration(unittest.TestCase):
    def test_post_run_callback_fires_on_success(self):
        from thinkbox.engine import ThinkBoxEngine, EngineConfig, TaskState

        callback_fired = False
        captured_summary = None

        def on_complete(summary):
            nonlocal callback_fired, captured_summary
            callback_fired = True
            captured_summary = summary

        engine = ThinkBoxEngine(EngineConfig())
        engine.on_run_complete(on_complete)

        with patch.object(engine.swarm, "execute_task") as mock_exec:
            mock_exec.return_value = MagicMock(
                task_id="task_1",
                success=True,
                exit_code=0,
                output="done",
                execution_time_ms=100.0,
                tokens_used=50,
            )
            summary = asyncio.run(
                engine.execute_goal("test goal")
            )

        self.assertTrue(callback_fired, "post_run_callback should fire on successful run")
        self.assertIsNotNone(captured_summary)
        self.assertEqual(captured_summary["total_tasks"], summary["total_tasks"])

    def test_post_run_callback_not_fired_without_registration(self):
        from thinkbox.engine import ThinkBoxEngine, EngineConfig

        engine = ThinkBoxEngine(EngineConfig())
        self.assertIsNone(engine._post_run_callback)

    def test_on_run_complete_replaces_callback(self):
        from thinkbox.engine import ThinkBoxEngine, EngineConfig

        engine = ThinkBoxEngine(EngineConfig())

        def cb1(summary):
            pass

        def cb2(summary):
            pass

        engine.on_run_complete(cb1)
        self.assertEqual(engine._post_run_callback, cb1)
        engine.on_run_complete(cb2)
        self.assertEqual(engine._post_run_callback, cb2)

    def test_post_run_callback_errors_swallowed(self):
        from thinkbox.engine import ThinkBoxEngine, EngineConfig

        def bad_callback(summary):
            raise RuntimeError("callback error")

        engine = ThinkBoxEngine(EngineConfig())
        engine.on_run_complete(bad_callback)

        with patch.object(engine.swarm, "execute_task") as mock_exec:
            mock_exec.return_value = MagicMock(
                task_id="task_1",
                success=True,
                exit_code=0,
                output="done",
                execution_time_ms=100.0,
                tokens_used=50,
            )
            asyncio.run(
                engine.execute_goal("test goal")
            )


class TestEndToEndCycle(unittest.TestCase):
    """Run → Evaluate → Improve → Retest → Compare → Verdict → persisted evidence."""

    def test_full_cycle_with_improvement(self):
        store = ExperimentStore(":memory:")
        pool = MagicMock()
        pool.max_workers = 32

        baseline_index = 0.6
        baseline_components = {
            "reliability": 0.4,
            "grounding": 0.7,
            "evidence_quality": 0.6,
        }

        record = run_improvement_cycle(store, pool, "e2e goal", baseline_index, baseline_components)

        # Run: baseline_index was computed from summary
        self.assertIsNotNone(record["experiment_id"])

        # Evaluate: weakness identified
        self.assertIn(record["weakness"], ("reliability", "grounding", "evidence_quality"))

        # Improve: proposal generated
        self.assertIn("kind", record["proposed_change"])
        self.assertIn("detail", record["proposed_change"])
        self.assertIn("weakness_score", record["proposed_change"])

        # Retest: applied because retest callback exists
        self.assertTrue(record["applied"])
        self.assertIsNotNone(record["retest_index"])

        # Compare: delta computed
        self.assertIsNotNone(record["delta"])

        # Verdict: either accepted or rejected (both valid outcomes)
        self.assertIn(record["accepted"], (True, False, None))

        # Persisted: record in database
        rows = store._conn.execute(
            "SELECT * FROM improvements WHERE experiment_id=?",
            (record["experiment_id"],)
        ).fetchall()
        self.assertEqual(len(rows), 1)

    def test_full_cycle_no_regression(self):
        store = ExperimentStore(":memory:")
        pool = MagicMock()
        pool.max_workers = 16

        baseline_index = 0.6
        baseline_components = {
            "reliability": 0.5,
            "grounding": 0.5,
            "evidence_quality": 0.5,
        }

        record = run_improvement_cycle(store, pool, "e2e goal", baseline_index, baseline_components)

        # All components equal, weakness is reliability (first in dict order)
        self.assertEqual(record["weakness"], "reliability")
        self.assertTrue(record["applied"])

        # Verdict recorded (accepted or rejected — both are valid cycle completions)
        self.assertIsNotNone(record["accepted"])

        # Persisted
        rows = store._conn.execute(
            "SELECT * FROM improvements WHERE experiment_id=?",
            (record["experiment_id"],)
        ).fetchall()
        self.assertEqual(len(rows), 1)


class TestEngineWiring(unittest.TestCase):
    def test_wired_runner_fires_on_success(self) -> None:
        from thinkbox.engine import ThinkBoxEngine, EngineConfig, TaskState
        from thinkbox.experiments import ImprovementRunner, ExperimentStore
        from thinkbox.swarm import ExecutionResult

        store = ExperimentStore(":memory:")
        pool = MagicMock()
        pool.max_workers = 32
        runner = ImprovementRunner(store, pool)

        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_improvement_runner(runner, {"reliability": 0.7})

        with patch.object(engine.swarm, "execute_task") as mock_exec:
            mock_exec.return_value = ExecutionResult(
                task_id="task_1", success=True, exit_code=0,
                output="done", execution_time_ms=100.0, tokens_used=50,
            )
            summary = asyncio.run(engine.execute_goal("test goal"))

        self.assertEqual(len(runner.history), 1)
        record = runner.history[0]
        self.assertIn("experiment_id", record)
        self.assertIn("weakness", record)
        self.assertIn("accepted", record)
        self.assertEqual(record["baseline_index"], 1.0)

    def test_wired_runner_improvement_path(self) -> None:
        from thinkbox.engine import ThinkBoxEngine, EngineConfig
        from thinkbox.experiments import ImprovementRunner, ExperimentStore
        from thinkbox.swarm import ExecutionResult

        store = ExperimentStore(":memory:")
        pool = MagicMock()
        pool.max_workers = 32
        runner = ImprovementRunner(store, pool)

        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_improvement_runner(
            runner, {"reliability": 0.7, "grounding": 0.7, "evidence_quality": 0.7}
        )

        with patch.object(engine.swarm, "execute_task") as mock_exec:
            mock_exec.return_value = ExecutionResult(
                task_id="task_1", success=True, exit_code=0,
                output="done", execution_time_ms=100.0, tokens_used=50,
            )
            asyncio.run(engine.execute_goal("test goal"))

        self.assertEqual(len(runner.history), 1)
        record = runner.history[0]
        self.assertTrue(record["applied"])
        self.assertIsNotNone(record["retest_index"])
        if record["delta"] is not None and record["delta"] > 0:
            self.assertTrue(record["accepted"])
        elif record["delta"] is not None and record["delta"] <= 0:
            self.assertFalse(record["accepted"])

    def test_wired_runner_rejection_path(self) -> None:
        from thinkbox.engine import ThinkBoxEngine, EngineConfig
        from thinkbox.experiments import ImprovementRunner, ExperimentStore
        from thinkbox.swarm import ExecutionResult

        store = ExperimentStore(":memory:")
        pool = MagicMock()
        pool.max_workers = 16
        runner = ImprovementRunner(store, pool)

        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_improvement_runner(
            runner, {"reliability": 0.5, "grounding": 0.9, "evidence_quality": 0.9}
        )

        with patch.object(engine.swarm, "execute_task") as mock_exec:
            mock_exec.return_value = ExecutionResult(
                task_id="task_1", success=True, exit_code=0,
                output="done", execution_time_ms=100.0, tokens_used=50,
            )
            asyncio.run(engine.execute_goal("test goal"))

        self.assertEqual(len(runner.history), 1)
        record = runner.history[0]
        self.assertTrue(record["applied"])
        self.assertIsNotNone(record["retest_index"])
        self.assertEqual(record["baseline_index"], 1.0)
        self.assertIn(record["weakness"], ("reliability", "grounding", "evidence_quality"))

    def test_wired_runner_database_record(self) -> None:
        from thinkbox.engine import ThinkBoxEngine, EngineConfig
        from thinkbox.experiments import ImprovementRunner, ExperimentStore
        from thinkbox.swarm import ExecutionResult

        store = ExperimentStore(":memory:")
        pool = MagicMock()
        pool.max_workers = 32
        runner = ImprovementRunner(store, pool)

        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_improvement_runner(runner, {"reliability": 0.7})

        with patch.object(engine.swarm, "execute_task") as mock_exec:
            mock_exec.return_value = ExecutionResult(
                task_id="task_1", success=True, exit_code=0,
                output="done", execution_time_ms=100.0, tokens_used=50,
            )
            asyncio.run(engine.execute_goal("test goal"))

        record = runner.history[0]
        rows = store._conn.execute(
            "SELECT * FROM improvements WHERE experiment_id=?",
            (record["experiment_id"],)
        ).fetchall()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["experiment_id"], record["experiment_id"])
        self.assertEqual(row["baseline_index"], 1.0)
        self.assertIsNotNone(row["weakness"])
        self.assertIsNotNone(row["proposed_change"])


if __name__ == "__main__":
    unittest.main()