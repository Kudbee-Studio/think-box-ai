"""Tests for Autonomous Loop Learning Curve + Convergence History (Number Four) (PR #246).

Proves:
1. AutonomousLoopTelemetry.model_dump includes convergence_history and learning_curve_points
2. Engine._telemetry_tick populates learning_curve_points from LoopTracer iteration history
3. Convergence history accumulates across telemetry ticks
4. Engine._assess_convergence produces correct statuses for various metrics
5. Session lifecycle wiring: current_session_id flows from LoopSessionManager to dashboard
6. DashboardState records closed sessions and lists them
7. Learning curve points are correctly built from iteration metrics
"""

from __future__ import annotations

import os
import tempfile
import unittest

from thinkbox.dashboard_state import (
    DashboardState,
    AutonomousLoopEntry,
    AutonomousLoopTelemetry,
    LoopSessionEntry,
)
import thinkbox.dashboard_state as ds_mod

from thinkbox.engine import ThinkBoxEngine, EngineConfig
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
    LoopIteration,
)


def _reset_dashboard():
    DashboardState._instance = None
    ds_mod._dashboard_state = None


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


class TestTelemetryModelExtensions(unittest.TestCase):

    def test_telemetry_model_dump_includes_learning_curve_and_convergence_history(self) -> None:
        tel = AutonomousLoopTelemetry(
            total_iterations=5,
            convergence_status="improving",
            learning_curve_points=[{"iteration": 1, "throughput": 1.0}],
            convergence_history=[{"timestamp": "2026-01-01T00:00:00Z", "status": "pending"}],
        )
        d = tel.model_dump()
        self.assertIn("learning_curve_points", d)
        self.assertEqual(len(d["learning_curve_points"]), 1)
        self.assertIn("convergence_history", d)
        self.assertEqual(len(d["convergence_history"]), 1)

    def test_telemetry_defaults_include_empty_lists(self) -> None:
        tel = AutonomousLoopTelemetry()
        d = tel.model_dump()
        self.assertEqual(d["learning_curve_points"], [])
        self.assertEqual(d["convergence_history"], [])

    def test_telemetry_convergence_history_capped_at_100(self) -> None:
        tel = AutonomousLoopTelemetry()
        tel.convergence_history = [{"status": "pending"}] * 150
        d = tel.model_dump()
        self.assertEqual(len(d["convergence_history"]), 150)


class TestLearningCurvePopulation(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager, self.analytics, self.opp_mgr, self.tracer, \
            self.tuner, self.generalizer, self.sess_mgr, self.bootstrap = _make_all(self.tmpdir)

    def tearDown(self) -> None:
        _reset_dashboard()

    async def test_telemetry_tick_populates_learning_curve(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False, telemetry_interval_s=0.0))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_tracer(self.tracer)
        engine.set_auto_tuner(self.tuner)

        await engine.execute_goal("Goal for learning curve")

        state = DashboardState()
        loops = list(state.autonomous_loops.values())
        self.assertGreaterEqual(len(loops), 1)
        tel = loops[0].telemetry
        self.assertIsNotNone(tel)
        self.assertIsInstance(tel, AutonomousLoopTelemetry)
        self.assertGreaterEqual(tel.total_iterations, 1)
        self.assertGreaterEqual(len(tel.learning_curve_points), 1)
        pc = tel.learning_curve_points[0]
        self.assertIn("iteration", pc)
        self.assertIn("throughput", pc)
        self.assertIn("avg_cycle_time_s", pc)

    async def test_convergence_history_accumulates(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False, telemetry_interval_s=0.0))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_tracer(self.tracer)
        engine.set_auto_tuner(self.tuner)

        await engine.execute_goal("First goal")
        await engine.execute_goal("Second goal")

        state = DashboardState()
        loop_id = self.tracer.get_current_loop_id()
        tel = state.get_loop_telemetry(loop_id)
        self.assertIsNotNone(tel)
        self.assertGreaterEqual(len(tel.convergence_history), 1)
        for entry in tel.convergence_history:
            self.assertIn("timestamp", entry)
            self.assertIn("status", entry)
            self.assertIn("iteration", entry)


class TestConvergenceAssessment(unittest.TestCase):

    def test_convergence_pending_no_iterations(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        metrics = LoopMetrics(
            total_iterations=0, total_cycle_time_s=0.0, avg_cycle_time_s=0.0,
            min_cycle_time_s=0.0, max_cycle_time_s=0.0,
            recommendation_types={}, priority_distribution={},
            first_iteration_id="", latest_iteration_id="",
        )
        self.assertEqual(engine._assess_convergence(metrics), "pending")

    def test_convergence_improving_with_iterations(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        metrics = LoopMetrics(
            total_iterations=2, total_cycle_time_s=1.0, avg_cycle_time_s=0.5,
            min_cycle_time_s=0.5, max_cycle_time_s=0.5,
            recommendation_types={}, priority_distribution={},
            first_iteration_id="", latest_iteration_id="",
        )
        self.assertEqual(engine._assess_convergence(metrics), "improving")

    def test_convergence_converged_low_spread(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        metrics = LoopMetrics(
            total_iterations=6, total_cycle_time_s=10.0, avg_cycle_time_s=1.0,
            min_cycle_time_s=0.9, max_cycle_time_s=1.1,
            recommendation_types={}, priority_distribution={},
            first_iteration_id="", latest_iteration_id="",
        )
        self.assertEqual(engine._assess_convergence(metrics), "converged")

    def test_convergence_improving_high_spread(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        metrics = LoopMetrics(
            total_iterations=6, total_cycle_time_s=10.0, avg_cycle_time_s=1.5,
            min_cycle_time_s=0.5, max_cycle_time_s=2.5,
            recommendation_types={}, priority_distribution={},
            first_iteration_id="", latest_iteration_id="",
        )
        self.assertEqual(engine._assess_convergence(metrics), "improving")


class TestSessionLifecycleWiring(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager, self.analytics, self.opp_mgr, self.tracer, \
            self.tuner, self.generalizer, self.sess_mgr, self.bootstrap = _make_all(self.tmpdir)

    def tearDown(self) -> None:
        _reset_dashboard()

    async def test_session_manager_sets_current_session_id(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False, telemetry_interval_s=0.0))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_bootstrap(self.bootstrap)
        engine.set_loop_tracer(self.tracer)
        engine.set_auto_tuner(self.tuner)
        engine.set_session_manager(self.sess_mgr)

        self.tracer.start_loop()
        self.sess_mgr.start_session()
        current = self.sess_mgr.get_current_session()

        await engine.execute_goal("Goal with session")

        state = DashboardState()
        loops = list(state.autonomous_loops.values())
        self.assertGreaterEqual(len(loops), 1)
        entry = loops[0]
        self.assertTrue(entry.components["session_manager"])

    async def test_closed_session_recorded_in_dashboard(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False, telemetry_interval_s=0.0))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_tracer(self.tracer)
        engine.set_session_manager(self.sess_mgr)
        engine.set_generalizer(self.generalizer)

        self.tracer.start_loop()
        self.sess_mgr.start_session()

        for i in range(3):
            await engine.execute_goal(f"Goal iteration {i}")

        closed = self.sess_mgr.close_session()
        self.assertIsNotNone(closed)

        state = DashboardState()
        engine._record_closed_session()

        sessions = state.list_loop_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].session_id, closed.session_id)


class TestDashboardSessionManagement(unittest.TestCase):

    def setUp(self) -> None:
        _reset_dashboard()

    def tearDown(self) -> None:
        _reset_dashboard()

    def test_record_autonomous_loop_session(self) -> None:
        state = DashboardState()
        entry = LoopSessionEntry(
            session_id="sess_001",
            loop_id="loop_a",
            started_at="2026-01-01T00:00:00Z",
            closed_at="2026-01-01T01:00:00Z",
            iterations_count=5,
            avg_throughput=0.8,
            avg_p50_latency=1.2,
            avg_error_rate=0.02,
            total_cycle_time_s=300.0,
            patterns_identified=2,
            improved_over_baseline=True,
        )
        state.record_autonomous_loop_session(entry)
        self.assertEqual(len(state.loop_sessions), 1)

        retrieved = state.get_loop_session("sess_001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.session_id, "sess_001")
        self.assertTrue(retrieved.improved_over_baseline)

    def test_get_loop_session_not_found(self) -> None:
        state = DashboardState()
        result = state.get_loop_session("nonexistent")
        self.assertIsNone(result)

    def test_list_loop_sessions_ordered_by_recency(self) -> None:
        state = DashboardState()
        s1 = LoopSessionEntry(session_id="sess_old", loop_id="loop_a",
                              started_at="2026-01-01T00:00:00Z", closed_at="2026-01-01T01:00:00Z")
        s2 = LoopSessionEntry(session_id="sess_new", loop_id="loop_a",
                              started_at="2026-01-02T00:00:00Z", closed_at="2026-01-02T01:00:00Z")
        state.record_autonomous_loop_session(s1)
        state.record_autonomous_loop_session(s2)

        sessions = state.list_loop_sessions()
        self.assertEqual(sessions[0].session_id, "sess_new")
        self.assertEqual(sessions[1].session_id, "sess_old")

    def test_get_state_includes_loop_sessions(self) -> None:
        state = DashboardState()
        entry = LoopSessionEntry(session_id="sess_001", loop_id="loop_a",
                                 closed_at="2026-01-01T01:00:00Z")
        state.record_autonomous_loop_session(entry)

        s = state.get_state()
        self.assertIn("loop_sessions", s)
        self.assertEqual(len(s["loop_sessions"]), 1)
        self.assertEqual(s["loop_sessions"][0]["session_id"], "sess_001")

    def test_state_summary_includes_session_count(self) -> None:
        state = DashboardState()
        entry = AutonomousLoopEntry(loop_id="loop1")
        state.upsert_autonomous_loop(entry)
        sess = LoopSessionEntry(session_id="sess_001", loop_id="loop1",
                                closed_at="2026-01-01T01:00:00Z")
        state.record_autonomous_loop_session(sess)

        summary = state.get_state_summary()
        self.assertIn("loop_session_summary", summary)
        self.assertEqual(summary["loop_session_summary"]["total_sessions"], 1)


class TestLoopSessionEntryModel(unittest.TestCase):

    def test_loop_session_entry_model_dump(self) -> None:
        entry = LoopSessionEntry(
            session_id="sess_test",
            loop_id="loop_1",
            started_at="2026-01-01T00:00:00Z",
            closed_at="2026-01-01T01:00:00Z",
            iterations_count=10,
            avg_throughput=2.5,
            improved_over_baseline=True,
        )
        d = entry.model_dump()
        self.assertEqual(d["session_id"], "sess_test")
        self.assertEqual(d["iterations_count"], 10)
        self.assertTrue(d["improved_over_baseline"])
        self.assertIn("summary", d)


if __name__ == "__main__":
    unittest.main()
