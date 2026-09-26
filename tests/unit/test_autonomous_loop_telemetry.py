"""Tests for Autonomous Loop Telemetry & Observability Dashboard (PR #243).

Proves:
1. AutonomousLoopTelemetry data model validates and serializes correctly
2. DashboardState records/retrieves loop telemetry and includes in state
3. Engine._telemetry_tick() captures metrics after execute_goal
4. Telemetry rate-limiting via telemetry_interval_s
5. Convergence assessment produces correct statuses
"""

from __future__ import annotations

import os
import tempfile
import time
import unittest

from thinkbox.dashboard_state import (
    DashboardState,
    DashboardCategory,
    DashboardEvent,
    AutonomousLoopEntry,
    AutonomousLoopTelemetry,
    get_dashboard_state,
)
from thinkbox.engine import ThinkBoxEngine, EngineConfig, TaskState
from thinkbox.experiment import ExperimentManager
from thinkbox.experiment_analytics import (
    ExperimentAnalytics,
    OpportunityManager,
    LoopTracer,
    EngineAutoTuner,
    CrossExperimentGeneralizer,
    LoopSessionManager,
    LoopBootstrap,
    LoopMetrics,
)


def _make_all(tmpdir: str):
    db_path = os.path.join(tmpdir, "experiments.db")
    artifacts_dir = os.path.join(tmpdir, "artifacts")
    opp_db = os.path.join(tmpdir, "opportunities.db")
    loop_db = os.path.join(tmpdir, "loop.db")
    tuner_db = os.path.join(tmpdir, "tuner.db")
    gen_db = os.path.join(tmpdir, "generalizer.db")
    sess_db = os.path.join(tmpdir, "sessions.db")
    boot_db = os.path.join(tmpdir, "bootstrap.db")
    manager = ExperimentManager(db_path=db_path, artifacts_dir=artifacts_dir)
    analytics = ExperimentAnalytics(manager)
    opp_mgr = OpportunityManager(manager, analytics, db_path=opp_db)
    tracer = LoopTracer(db_path=loop_db)
    tuner = EngineAutoTuner(tracer, db_path=tuner_db)
    generalizer = CrossExperimentGeneralizer(tracer, manager, analytics, db_path=gen_db)
    sess_mgr = LoopSessionManager(tracer, generalizer, db_path=sess_db)
    bootstrap = LoopBootstrap(manager, analytics, db_path=boot_db)
    return manager, analytics, opp_mgr, tracer, tuner, generalizer, sess_mgr, bootstrap


def _reset_dashboard():
    DashboardState._instance = None
    import thinkbox.dashboard_state as ds_mod
    ds_mod._dashboard_state = None


class TestAutonomousLoopTelemetry(unittest.TestCase):

    def test_telemetry_model_dump(self) -> None:
        tel = AutonomousLoopTelemetry(
            total_iterations=10,
            total_cycle_time_s=5.0,
            avg_cycle_time_s=0.5,
            min_cycle_time_s=0.1,
            max_cycle_time_s=1.2,
            throughput=2.0,
            recommendation_types={"validation_run": 3, "retry": 2},
            priority_distribution={"high": 4, "low": 6},
            learning_curve_points=[{"iteration": 1, "throughput": 1.0}],
            convergence_status="converged",
            last_iteration_id="iter_abc",
            first_iteration_id="iter_xyz",
        )
        d = tel.model_dump()
        self.assertEqual(d["total_iterations"], 10)
        self.assertEqual(d["throughput"], 2.0)
        self.assertEqual(d["convergence_status"], "converged")
        self.assertEqual(d["recommendation_types"]["validation_run"], 3)
        self.assertEqual(d["learning_curve_points"][0]["iteration"], 1)

    def test_telemetry_defaults(self) -> None:
        tel = AutonomousLoopTelemetry()
        d = tel.model_dump()
        self.assertEqual(d["total_iterations"], 0)
        self.assertEqual(d["throughput"], 0.0)
        self.assertEqual(d["convergence_status"], "pending")
        self.assertEqual(d["recommendation_types"], {})
        self.assertEqual(d["learning_curve_points"], [])

    def test_entry_includes_telemetry_field(self) -> None:
        tel = AutonomousLoopTelemetry(total_iterations=3, convergence_status="improving")
        entry = AutonomousLoopEntry(
            loop_id="loop_test",
            telemetry=tel,
        )
        d = entry.model_dump()
        self.assertIn("telemetry", d)
        self.assertEqual(d["telemetry"]["total_iterations"], 3)
        self.assertEqual(d["telemetry"]["convergence_status"], "improving")

    def test_entry_telemetry_defaults_to_empty(self) -> None:
        entry = AutonomousLoopEntry(loop_id="loop_default")
        d = entry.model_dump()
        self.assertIn("telemetry", d)
        self.assertEqual(d["telemetry"]["total_iterations"], 0)
        self.assertEqual(d["telemetry"]["convergence_status"], "pending")


class TestDashboardTelemetry(unittest.TestCase):

    def setUp(self) -> None:
        _reset_dashboard()

    def tearDown(self) -> None:
        _reset_dashboard()

    def test_upsert_then_record_telemetry(self) -> None:
        state = DashboardState()
        entry = AutonomousLoopEntry(loop_id="loop_t1")
        state.upsert_autonomous_loop(entry)
        tel = AutonomousLoopTelemetry(total_iterations=5, convergence_status="converged")
        state.record_loop_telemetry("loop_t1", tel)
        retrieved = state.get_loop_telemetry("loop_t1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.total_iterations, 5)
        self.assertEqual(retrieved.convergence_status, "converged")

    def test_get_loop_telemetry_unknown_returns_none(self) -> None:
        state = DashboardState()
        result = state.get_loop_telemetry("nonexistent")
        self.assertIsNone(result)

    def test_get_all_loop_telemetry(self) -> None:
        state = DashboardState()
        entry1 = AutonomousLoopEntry(loop_id="loop_a")
        entry2 = AutonomousLoopEntry(loop_id="loop_b")
        tel1 = AutonomousLoopTelemetry(total_iterations=2)
        tel2 = AutonomousLoopTelemetry(total_iterations=8)
        tel1.first_iteration_id = "loop_a"
        tel2.first_iteration_id = "loop_b"
        entry1.telemetry = tel1
        entry2.telemetry = tel2
        state.upsert_autonomous_loop(entry1)
        state.upsert_autonomous_loop(entry2)
        all_tel = state.get_all_loop_telemetry()
        self.assertEqual(len(all_tel), 2)
        counts = {t["total_iterations"] for t in all_tel}
        self.assertEqual(counts, {2, 8})

    def test_state_summary_includes_telemetry(self) -> None:
        state = DashboardState()
        entry = AutonomousLoopEntry(loop_id="loop_s1")
        tel = AutonomousLoopTelemetry(total_iterations=3)
        tel.first_iteration_id = "loop_s1"
        entry.telemetry = tel
        state.upsert_autonomous_loop(entry)

        summary = state.get_state_summary()
        self.assertIn("loop_telemetry_summary", summary)
        self.assertEqual(summary["loop_telemetry_summary"]["loops_with_telemetry"], 1)
        self.assertEqual(summary["summary"]["total_loop_iterations"], 3)

        full_state = state.get_state()
        self.assertIn("loop_telemetry", full_state)
        self.assertEqual(len(full_state["loop_telemetry"]), 1)


class TestEngineTelemetryIntegration(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager, self.analytics, self.opp_mgr, self.tracer, \
            self.tuner, self.generalizer, self.sess_mgr, self.bootstrap = _make_all(self.tmpdir)

    def tearDown(self) -> None:
        _reset_dashboard()

    async def test_engine_updates_telemetry_after_goal(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False, telemetry_interval_s=0.0))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_bootstrap(self.bootstrap)
        engine.set_loop_tracer(self.tracer)
        engine.set_auto_tuner(self.tuner)
        engine.set_generalizer(self.generalizer)

        await engine.execute_goal("Goal with telemetry")

        state = get_dashboard_state()
        self.assertGreaterEqual(len(state.autonomous_loops), 1)
        loop_entry = list(state.autonomous_loops.values())[0]
        tel = loop_entry.telemetry
        self.assertIsInstance(tel, AutonomousLoopTelemetry)
        self.assertGreaterEqual(tel.total_iterations, 1)

    async def test_engine_telemetry_no_tracer_no_update(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False, telemetry_interval_s=0.0))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)

        await engine.execute_goal("Goal without tracer")

        state = get_dashboard_state()
        self.assertEqual(len(state.autonomous_loops), 0)

    async def test_telemetry_rate_limiting(self) -> None:
        engine1 = ThinkBoxEngine(EngineConfig(speculative=False, telemetry_interval_s=3600.0))
        engine1.set_loop_tracer(self.tracer)

        engine2 = ThinkBoxEngine(EngineConfig(speculative=False, telemetry_interval_s=0.0))
        engine2.set_loop_tracer(self.tracer)

        self.tracer.start_iteration("goal_test1")
        state = get_dashboard_state()
        state.upsert_autonomous_loop(AutonomousLoopEntry(loop_id=self.tracer.get_current_loop_id()))
        loop_id = self.tracer.get_current_loop_id()

        engine1._telemetry_tick()
        tel1 = state.get_loop_telemetry(loop_id)
        self.assertIsNotNone(tel1)
        self.assertEqual(tel1.total_iterations, 0)

        engine1._last_telemetry_time = time.monotonic()
        engine1._telemetry_tick()
        tel1_after_rate_limit = state.get_loop_telemetry(loop_id)
        self.assertEqual(tel1_after_rate_limit.total_iterations, 0)

        engine2._telemetry_tick()
        tel2 = state.get_loop_telemetry(loop_id)
        self.assertIsNotNone(tel2)
        self.assertEqual(tel2.total_iterations, 0)

    async def test_assess_convergence_statuses(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))

        pending_metrics = LoopMetrics(
            total_iterations=2, total_cycle_time_s=1.0, avg_cycle_time_s=0.5,
            min_cycle_time_s=0.5, max_cycle_time_s=0.5,
            recommendation_types={}, priority_distribution={},
            first_iteration_id="", latest_iteration_id="",
        )
        self.assertEqual(engine._assess_convergence(pending_metrics), "improving")

        stable_metrics = LoopMetrics(
            total_iterations=6, total_cycle_time_s=10.0, avg_cycle_time_s=1.0,
            min_cycle_time_s=0.9, max_cycle_time_s=1.1,
            recommendation_types={}, priority_distribution={},
            first_iteration_id="", latest_iteration_id="",
        )
        self.assertEqual(engine._assess_convergence(stable_metrics), "converged")

        unstable_metrics = LoopMetrics(
            total_iterations=6, total_cycle_time_s=10.0, avg_cycle_time_s=1.5,
            min_cycle_time_s=0.5, max_cycle_time_s=2.5,
            recommendation_types={}, priority_distribution={},
            first_iteration_id="", latest_iteration_id="",
        )
        self.assertEqual(engine._assess_convergence(unstable_metrics), "improving")

        empty_metrics = LoopMetrics(
            total_iterations=0, total_cycle_time_s=0.0, avg_cycle_time_s=0.0,
            min_cycle_time_s=0.0, max_cycle_time_s=0.0,
            recommendation_types={}, priority_distribution={},
            first_iteration_id="", latest_iteration_id="",
        )
        self.assertEqual(engine._assess_convergence(empty_metrics), "pending")


if __name__ == "__main__":
    unittest.main()
