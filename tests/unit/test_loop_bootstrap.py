"""Tests for Loop Bootstrap (PR #241).

Proves:
1. LoopBootstrap.needs_bootstrap() returns True when no prior recommendations
2. LoopBootstrap.needs_bootstrap() returns False when prior recommendations exist
3. bootstrap() creates experiment with seed metrics and recommendation
4. bootstrap() returns unbootstrapped when prior data exists
5. mark_consumed updates bootstrap state
6. Engine uses bootstrap when no prior recommendation exists
7. Engine skips bootstrap when prior recommendation exists (normal loop)
8. No bootstrap injected -> legacy behavior preserved
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest

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
    BootstrapResult,
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


class TestLoopBootstrap(unittest.TestCase):

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager, self.analytics, self.opp_mgr, self.tracer, \
            self.tuner, self.generalizer, self.sess_mgr, self.bootstrap = _make_all(self.tmpdir)

    def test_needs_bootstrap_when_no_prior_data(self) -> None:
        self.assertTrue(self.bootstrap.needs_bootstrap())

    def test_needs_bootstrap_false_after_existing_recommendation(self) -> None:
        result = self.bootstrap.bootstrap()
        self.assertTrue(result.bootstrapped)
        self.assertFalse(self.bootstrap.needs_bootstrap())

    def test_bootstrap_creates_experiment(self) -> None:
        result = self.bootstrap.bootstrap()
        self.assertIsInstance(result, BootstrapResult)
        self.assertTrue(result.bootstrapped)
        self.assertTrue(result.experiment_id.startswith("tb_exp_"))
        self.assertEqual(result.source, "bootstrap")
        self.assertEqual(result.four_state, "TEST_VERIFIED")

    def test_bootstrap_recommendation_has_required_fields(self) -> None:
        result = self.bootstrap.bootstrap()
        rec = result.recommendation
        self.assertIn("type", rec)
        self.assertIn("rationale", rec)
        self.assertIn("max_retries", rec)
        self.assertIn("adjustments", rec)

    def test_bootstrap_seed_metrics(self) -> None:
        result = self.bootstrap.bootstrap()
        metrics = result.seed_metrics
        self.assertIn("throughput", metrics)
        self.assertIn("p50_latency", metrics)
        self.assertIn("error_rate", metrics)

    def test_bootstrap_second_call_unbootstrapped(self) -> None:
        first = self.bootstrap.bootstrap()
        self.assertTrue(first.bootstrapped)
        second = self.bootstrap.bootstrap()
        self.assertFalse(second.bootstrapped)
        self.assertEqual(second.source, "existing_data")

    def test_bootstrap_persisted_to_db(self) -> None:
        result = self.bootstrap.bootstrap()
        history = self.bootstrap.get_bootstrap_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["experiment_id"], result.experiment_id)
        self.assertEqual(self.bootstrap.get_bootstrap_count(), 1)

    def test_mark_consumed(self) -> None:
        result = self.bootstrap.bootstrap()
        self.bootstrap.mark_consumed(result.experiment_id)
        history = self.bootstrap.get_bootstrap_history()
        self.assertEqual(history[0]["was_consumed"], 1)

    def test_custom_bootstrap_config(self) -> None:
        config = BootstrapConfig(
            default_intent="custom_bootstrap",
            seed_hypothesis="Custom hypothesis",
            confidence=0.8,
            four_state="TEST_VERIFIED",
        )
        bootstrap = LoopBootstrap(self.manager, self.analytics, config=config,
                                  db_path=os.path.join(self.tmpdir, "custom_bootstrap.db"))
        result = bootstrap.bootstrap()
        self.assertTrue(result.bootstrapped)
        self.assertEqual(result.confidence, 0.8)


class TestEngineBootstrapBinding(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager, self.analytics, self.opp_mgr, self.tracer, \
            self.tuner, self.generalizer, self.sess_mgr, self.bootstrap = _make_all(self.tmpdir)

    async def test_engine_uses_bootstrap_from_cold_start(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_bootstrap(self.bootstrap)

        await engine.execute_goal("Cold start goal")

        bootstrap_events = [e for e in engine.events if "Loop bootstrapped" in e.message]
        self.assertEqual(len(bootstrap_events), 1)

    async def test_engine_skips_bootstrap_with_prior_data(self) -> None:
        self.bootstrap.bootstrap()

        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_bootstrap(self.bootstrap)

        await engine.execute_goal("Warm start goal")

        bootstrap_events = [e for e in engine.events if "Loop bootstrapped" in e.message]
        self.assertEqual(len(bootstrap_events), 0)

    async def test_no_bootstrap_manager_legacy_behavior(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        await engine.execute_goal("No bootstrap goal")

        bootstrap_events = [e for e in engine.events if "Loop bootstrapped" in e.message]
        self.assertEqual(len(bootstrap_events), 0)
        summary_events = [e for e in engine.events if "Goal execution complete" in e.message]
        self.assertEqual(len(summary_events), 1)

    async def test_full_cold_start_to_warm_cycle(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_bootstrap(self.bootstrap)

        await engine.execute_goal("First goal - cold start")
        self.assertTrue(self.bootstrap.needs_bootstrap() is False)

        await engine.execute_goal("Second goal - warm")
        bootstrap_events = [e for e in engine.events if "Loop bootstrapped" in e.message]
        self.assertEqual(len(bootstrap_events), 1)

        experiments = self.manager.db.get_all_experiments()
        self.assertGreaterEqual(len(experiments), 2)


if __name__ == "__main__":
    unittest.main()
