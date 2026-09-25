"""Tests for Feedback -> Opportunity binding (PR #235).

Proves:
1. OpportunityManager registers opportunities from recommendations
2. _register_opportunity persists and emits event when manager injected
3. get_current_opportunity retrieves the most recent opportunity
4. Opportunity survives engine restart (SQLite persistence)
5. No opportunity manager -> no-op, no events
6. Priority assignment: regression recommendations -> high
"""

from __future__ import annotations

import os
import tempfile
import unittest

from thinkbox.engine import ThinkBoxEngine, EngineConfig, TaskState
from thinkbox.experiment import ExperimentManager
from thinkbox.experiment_analytics import (
    ExperimentAnalytics,
    OpportunityManager,
    Opportunity,
    NextActionGenerator,
)


def _make_managers(tmpdir: str):
    db_path = os.path.join(tmpdir, "experiments.db")
    artifacts_dir = os.path.join(tmpdir, "artifacts")
    opp_db = os.path.join(tmpdir, "opportunities.db")
    manager = ExperimentManager(db_path=db_path, artifacts_dir=artifacts_dir)
    analytics = ExperimentAnalytics(manager)
    opp_mgr = OpportunityManager(manager, analytics, db_path=opp_db)
    return manager, analytics, opp_mgr


class TestOpportunityManager(unittest.TestCase):

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager, self.analytics, self.opp_mgr = _make_managers(self.tmpdir)

    def test_register_opportunity(self) -> None:
        rec = {"type": "validation_run", "rationale": "no issues", "max_retries": 1}
        metrics = {"throughput": 10.0, "p50_latency": 0.1, "error_rate": 0.0, "iteration_count": 1}
        opp = self.opp_mgr.register_opportunity("exp1", "goal1", rec, metrics, priority="medium")

        self.assertIsInstance(opp, Opportunity)
        self.assertTrue(opp.opportunity_id.startswith("opp_"))
        self.assertEqual(opp.source_experiment_id, "exp1")
        self.assertEqual(opp.source_goal_run_id, "goal1")
        self.assertEqual(opp.recommendation, rec)
        self.assertEqual(opp.priority, "medium")

    def test_get_current_opportunity(self) -> None:
        rec1 = {"type": "validation_run", "rationale": "first"}
        rec2 = {"type": "anomaly_followup", "rationale": "second"}
        metrics = {"throughput": 10.0, "p50_latency": 0.1, "error_rate": 0.0, "iteration_count": 1}

        self.assertIsNone(self.opp_mgr.get_current_opportunity())
        self.opp_mgr.register_opportunity("exp1", "goal1", rec1, metrics)
        self.opp_mgr.register_opportunity("exp2", "goal2", rec2, metrics)
        current = self.opp_mgr.get_current_opportunity()
        self.assertIsNotNone(current)
        self.assertEqual(current.recommendation["type"], "anomaly_followup")

    def test_list_opportunities(self) -> None:
        metrics = {"throughput": 10.0, "p50_latency": 0.1, "error_rate": 0.0, "iteration_count": 1}
        self.opp_mgr.register_opportunity("exp1", "goal1", {"type": "validation_run"}, metrics)
        self.opp_mgr.register_opportunity("exp2", "goal2", {"type": "anomaly_followup"}, metrics)
        opps = self.opp_mgr.list_opportunities()
        self.assertEqual(len(opps), 2)

    def test_count_opportunities(self) -> None:
        metrics = {"throughput": 10.0, "p50_latency": 0.1, "error_rate": 0.0, "iteration_count": 1}
        self.assertEqual(self.opp_mgr.count_opportunities(), 0)
        self.opp_mgr.register_opportunity("exp1", "goal1", {"type": "validation_run"}, metrics)
        self.assertEqual(self.opp_mgr.count_opportunities(), 1)
        self.opp_mgr.register_opportunity("exp2", "goal2", {"type": "anomaly_followup"}, metrics)
        self.assertEqual(self.opp_mgr.count_opportunities(), 2)


class TestEngineOpportunityBinding(unittest.TestCase):

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager, self.analytics, self.opp_mgr = _make_managers(self.tmpdir)

    def test_register_opportunity_emits_event(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)

        rec = {"type": "validation_run", "rationale": "ok"}
        metrics = {"throughput": 10.0, "p50_latency": 0.1, "error_rate": 0.0, "iteration_count": 1}
        engine._register_opportunity("exp1", "goal1", rec, metrics)

        opp_events = [e for e in engine.events if "Opportunity registered" in e.message]
        self.assertEqual(len(opp_events), 1)
        self.assertEqual(opp_events[0].metadata["recommendation_type"], "validation_run")

    def test_no_opportunity_manager_no_op(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, None)

        rec = {"type": "validation_run"}
        metrics = {"throughput": 10.0, "p50_latency": 0.1, "error_rate": 0.0, "iteration_count": 1}
        engine._register_opportunity("exp1", "goal1", rec, metrics)

        opp_events = [e for e in engine.events if "Opportunity registered" in e.message]
        self.assertEqual(len(opp_events), 0)

    def test_regression_recommendation_high_priority(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)

        rec = {"type": "regression_followup", "rationale": "regression found"}
        metrics = {"throughput": 5.0, "p50_latency": 0.5, "error_rate": 0.1, "iteration_count": 1}
        engine._register_opportunity("exp1", "goal1", rec, metrics)

        opp = self.opp_mgr.get_current_opportunity()
        self.assertIsNotNone(opp)
        self.assertEqual(opp.priority, "high")

    def test_opportunity_survives_engine_restart(self) -> None:
        engine1 = ThinkBoxEngine(EngineConfig(speculative=False))
        engine1.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)

        rec = {"type": "anomaly_followup", "rationale": "anomaly"}
        metrics = {"throughput": 8.0, "p50_latency": 0.2, "error_rate": 0.05, "iteration_count": 2}
        engine1._register_opportunity("exp1", "goal1", rec, metrics)

        fresh_mgr, fresh_an, fresh_opp = _make_managers(self.tmpdir)
        opp = fresh_opp.get_current_opportunity()
        self.assertIsNotNone(opp)
        self.assertEqual(opp.recommendation["type"], "anomaly_followup")


class TestFullFeedbackToOpportunityFlow(unittest.TestCase):

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager, self.analytics, self.opp_mgr = _make_managers(self.tmpdir)

    def test_feedback_creates_experiment_and_opportunity(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)

        summary = {
            "goal_run_id": "goal_235",
            "total_tasks": 4,
            "completed": 4,
            "successful": 3,
            "failed": 1,
            "total_time_ms": 1200.0,
            "events": 10,
        }
        engine._record_execution_feedback(summary, "goal_235")

        experiments = self.manager.db.get_all_experiments()
        self.assertEqual(len(experiments), 1)
        self.assertEqual(experiments[0]["intent"], "goal:goal_235")

        opp = self.opp_mgr.get_current_opportunity()
        self.assertIsNotNone(opp)
        self.assertEqual(opp.source_goal_run_id, "goal_235")
        self.assertIn("type", opp.recommendation)

    def test_opportunity_recommendation_is_next_action(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)

        summary = {
            "goal_run_id": "goal_na",
            "total_tasks": 2,
            "completed": 2,
            "successful": 2,
            "failed": 0,
            "total_time_ms": 500.0,
            "events": 5,
        }
        engine._record_execution_feedback(summary, "goal_na")

        opp = self.opp_mgr.get_current_opportunity()
        self.assertIsNotNone(opp)
        rec = opp.recommendation
        self.assertIn("type", rec)
        self.assertIn("rationale", rec)
        self.assertIn("max_retries", rec)
        self.assertIn("adjustments", rec)


if __name__ == "__main__":
    unittest.main()
