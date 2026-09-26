"""Tests for Autonomous Loop Dashboard (Number Two 42) binding (PR #242).

Proves:
1. AutonomousLoopEntry data model validates correctly
2. DashboardState tracks autonomous_loops and includes in get_state()
3. Engine updates loop dashboard after execute_goal
4. Dashboard reflects all component states (bootstrap, feedback, opportunity, etc.)
5. Autonomous loop summary counts appear in get_state_summary()
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from thinkbox.dashboard_state import (
    DashboardState,
    DashboardCategory,
    DashboardEvent,
    AutonomousLoopEntry,
)
from thinkbox.dashboard_state import _dashboard_state as _ds_global
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
    BootstrapConfig,
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


class TestAutonomousLoopEntry(unittest.TestCase):

    def test_entry_model_dump(self) -> None:
        entry = AutonomousLoopEntry(
            loop_id="loop_test123",
            status="running",
            iterations_count=5,
            patterns_identified=2,
            tuning_decisions=1,
            bootstrapped=True,
            latest_recommendation={"type": "validation_run"},
            latest_metrics={"throughput": 10.0},
            components={
                "bootstrap": True,
                "experiment_manager": True,
                "decomposer": True,
                "execution": True,
                "feedback": True,
                "opportunity": True,
                "loop_tracer": True,
                "auto_tuner": True,
                "generalizer": True,
                "session_manager": True,
            },
        )
        d = entry.model_dump()
        self.assertEqual(d["loop_id"], "loop_test123")
        self.assertEqual(d["iterations_count"], 5)
        self.assertTrue(d["bootstrapped"])
        self.assertIn("bootstrap", d["components"])
        d["evidence_label"] == "infmred"

    def test_entry_defaults(self) -> None:
        entry = AutonomousLoopEntry(loop_id="loop_default")
        d = entry.model_dump()
        self.assertEqual(d["status"], "idle")
        self.assertEqual(d["iterations_count"], 0)
        self.assertFalse(d["bootstrapped"])
        self.assertEqual(d["components"]["bootstrap"], False)


class TestDashboardAutonomousLoop(unittest.TestCase):

    def tearDown(self) -> None:
        DashboardState._instance = None
        import thinkbox.dashboard_state as ds_mod
        ds_mod._dashboard_state = None

    def test_dashboard_tracks_autonomous_loops(self) -> None:
        state = DashboardState()
        entry = AutonomousLoopEntry(loop_id="loop_test", status="running", iterations_count=3)
        state.upsert_autonomous_loop(entry)
        self.assertEqual(len(state.autonomous_loops), 1)

        s = state.get_state()
        self.assertIn("autonomous_loops", s)
        self.assertEqual(len(s["autonomous_loops"]), 1)
        self.assertEqual(s["autonomous_loops"][0]["loop_id"], "loop_test")

    def test_dashboard_summary_includes_loop_count(self) -> None:
        state = DashboardState()
        state.upsert_autonomous_loop(AutonomousLoopEntry(loop_id="loop1"))
        state.upsert_autonomous_loop(AutonomousLoopEntry(loop_id="loop2"))

        summary = state.get_state_summary()
        self.assertEqual(summary["summary"]["total_autonomous_loops"], 2)

        full_state = state.get_state()
        self.assertEqual(full_state["summary"]["total_autonomous_loops"], 2)

    def test_dashboard_event_constants(self) -> None:
        self.assertTrue(hasattr(DashboardEvent, "LOOP_STARTED"))
        self.assertTrue(hasattr(DashboardEvent, "LOOP_ITERATION_COMPLETED"))
        self.assertTrue(hasattr(DashboardEvent, "LOOP_BOOTSTRAPPED"))
        self.assertTrue(hasattr(DashboardEvent, "SESSION_CLOSED"))
        self.assertTrue(hasattr(DashboardEvent, "TUNING_APPLIED"))
        self.assertTrue(hasattr(DashboardEvent, "PATTERN_GENERALIZED"))

    def test_dashboard_category_has_autonomous_loop(self) -> None:
        self.assertTrue(hasattr(DashboardCategory, "AUTONOMOUS_LOOP"))


class TestEngineDashboardIntegration(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager, self.analytics, self.opp_mgr, self.tracer, \
            self.tuner, self.generalizer, self.sess_mgr, self.bootstrap = _make_all(self.tmpdir)

    def tearDown(self) -> None:
        DashboardState._instance = None
        import thinkbox.dashboard_state as ds_mod
        ds_mod._dashboard_state = None

    async def test_engine_updates_loop_dashboard(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_bootstrap(self.bootstrap)
        engine.set_loop_tracer(self.tracer)
        engine.set_auto_tuner(self.tuner)
        engine.set_generalizer(self.generalizer)

        await engine.execute_goal("Goal with dashboard")

        state = DashboardState()
        self.assertGreaterEqual(len(state.autonomous_loops), 1)
        loop_entry = list(state.autonomous_loops.values())[0]
        self.assertEqual(loop_entry.status, "running")
        self.assertGreaterEqual(loop_entry.iterations_count, 1)
        self.assertTrue(loop_entry.components["bootstrap"])
        self.assertTrue(loop_entry.components["feedback"])
        self.assertTrue(loop_entry.components["loop_tracer"])

    async def test_engine_without_tracer_no_dashboard_update(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_bootstrap(self.bootstrap)

        await engine.execute_goal("Goal without tracer")

        state = DashboardState()
        self.assertEqual(len(state.autonomous_loops), 0)

    async def test_engine_dashboard_reflects_all_components(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_bootstrap(self.bootstrap)
        engine.set_loop_tracer(self.tracer)
        engine.set_auto_tuner(self.tuner)
        engine.set_generalizer(self.generalizer)
        engine.set_session_manager(self.sess_mgr)

        await engine.execute_goal("Full component goal")

        state = DashboardState()
        self.assertGreaterEqual(len(state.autonomous_loops), 1)
        loop_entry = list(state.autonomous_loops.values())[0]
        comps = loop_entry.components
        self.assertTrue(comps["bootstrap"])
        self.assertTrue(comps["experiment_manager"])
        self.assertTrue(comps["decomposer"])
        self.assertTrue(comps["execution"])
        self.assertTrue(comps["feedback"])
        self.assertTrue(comps["opportunity"])


if __name__ == "__main__":
    unittest.main()
