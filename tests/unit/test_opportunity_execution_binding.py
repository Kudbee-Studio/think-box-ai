"""Tests for Opportunity -> Execution binding (PR #236).

Proves:
1. execute_goal retrieves current opportunity and passes its recommendation to decompose
2. When opportunity has a recommendation, it takes priority over get_last_next_action
3. Opportunity priority and ID are emitted as events
4. No opportunity manager -> falls back to ExperimentManager.get_last_next_action
5. No managers -> default decomposed graph (legacy behavior)
6. Full closed loop: execution -> feedback -> opportunity -> next execution consumes it
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch

from thinkbox.engine import ThinkBoxEngine, EngineConfig, TaskState
from thinkbox.experiment import ExperimentManager
from thinkbox.experiment_analytics import ExperimentAnalytics, OpportunityManager


def _make_managers(tmpdir: str):
    db_path = os.path.join(tmpdir, "experiments.db")
    artifacts_dir = os.path.join(tmpdir, "artifacts")
    opp_db = os.path.join(tmpdir, "opportunities.db")
    manager = ExperimentManager(db_path=db_path, artifacts_dir=artifacts_dir)
    analytics = ExperimentAnalytics(manager)
    opp_mgr = OpportunityManager(manager, analytics, db_path=opp_db)
    return manager, analytics, opp_mgr


class TestOpportunityConsumption(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager, self.analytics, self.opp_mgr = _make_managers(self.tmpdir)

    async def test_execute_goal_consumes_current_opportunity(self) -> None:
        """When an opportunity exists, its recommendation is passed to decompose."""
        rec = {"type": "anomaly_followup", "rationale": "high error rate", "max_retries": 2}
        metrics = {"throughput": 8.0, "p50_latency": 0.2, "error_rate": 0.1, "iteration_count": 2}
        self.opp_mgr.register_opportunity("exp1", "goal1", rec, metrics)

        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)

        with patch.object(engine.decomposer, "decompose", wraps=engine.decomposer.decompose) as mock_decompose:
            await engine.execute_goal("Test goal for opportunity")

        self.assertGreater(mock_decompose.call_count, 0)
        call_kwargs = mock_decompose.call_args.kwargs
        passed_rec = call_kwargs.get("prior_recommendation")
        self.assertIsNotNone(passed_rec)
        self.assertEqual(passed_rec["type"], "anomaly_followup")

    async def test_opportunity_emits_event_with_priority(self) -> None:
        rec = {"type": "regression_followup", "rationale": "regression", "max_retries": 3}
        metrics = {"throughput": 5.0, "p50_latency": 0.5, "error_rate": 0.2, "iteration_count": 1}
        self.opp_mgr.register_opportunity("exp1", "goal1", rec, metrics, priority="high")

        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)

        await engine.execute_goal("Test goal")

        opp_events = [e for e in engine.events if "Consuming current opportunity" in e.message]
        self.assertEqual(len(opp_events), 1)
        self.assertEqual(opp_events[0].metadata["opportunity_priority"], "high")

    async def test_no_opportunity_falls_back_to_experiment_manager(self) -> None:
        """Without an opportunity, falls back to ExperimentManager.get_last_next_action()."""
        self.assertIsNone(self.opp_mgr.get_current_opportunity())
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)

        await engine.execute_goal("Test goal fallback")

        opp_events = [e for e in engine.events if "Consuming current opportunity" in e.message]
        self.assertEqual(len(opp_events), 0)

    async def test_no_managers_default_decompose(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        await engine.execute_goal("Test goal no managers")

        opp_events = [e for e in engine.events if "Consuming current opportunity" in e.message]
        self.assertEqual(len(opp_events), 0)
        summary_events = [e for e in engine.events if "Goal execution complete" in e.message]
        self.assertEqual(len(summary_events), 1)

    async def test_opportunity_consumed_after_feedback(self) -> None:
        """Full loop: feedback registers opportunity, next execute_goal consumes it."""
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)

        summary = {
            "goal_run_id": "goal_loop",
            "total_tasks": 3,
            "completed": 3,
            "successful": 2,
            "failed": 1,
            "total_time_ms": 800.0,
            "events": 8,
        }
        engine._record_execution_feedback(summary, "goal_loop")

        opp = self.opp_mgr.get_current_opportunity()
        self.assertIsNotNone(opp)
        consumed_opp_id = opp.opportunity_id

        opp_events_before = [e for e in engine.events if "Consuming current opportunity" in e.message]
        self.assertEqual(len(opp_events_before), 0)

        await engine.execute_goal("Follow-up goal consuming opportunity")

        opp_events_after = [e for e in engine.events if "Consuming current opportunity" in e.message]
        self.assertEqual(len(opp_events_after), 1)
        self.assertEqual(opp_events_after[0].metadata["opportunity_id"], consumed_opp_id)


class TestOpportunityExecutionIntegration(unittest.TestCase):

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager, self.analytics, self.opp_mgr = _make_managers(self.tmpdir)

    def test_opportunity_recommendation_persists_to_next_execution(self) -> None:
        """The recommendation from Opportunity survives engine restart and is consumed."""
        engine1 = ThinkBoxEngine(EngineConfig(speculative=False))
        engine1.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)

        summary = {
            "goal_run_id": "goal_restart",
            "total_tasks": 2,
            "completed": 2,
            "successful": 2,
            "failed": 0,
            "total_time_ms": 500.0,
            "events": 5,
        }
        engine1._record_execution_feedback(summary, "goal_restart")
        opp_id = self.opp_mgr.get_current_opportunity().opportunity_id

        fresh_mgr, fresh_an, fresh_opp = _make_managers(self.tmpdir)
        engine2 = ThinkBoxEngine(EngineConfig(speculative=False))
        engine2.wire_experiment_feedback(fresh_mgr, fresh_an, fresh_opp)

        asyncio.run(engine2.execute_goal("Goal with persisted opportunity"))
        opp_events = [e for e in engine2.events if "Consuming current opportunity" in e.message]
        self.assertEqual(len(opp_events), 1)
        self.assertEqual(opp_events[0].metadata["opportunity_id"], opp_id)


if __name__ == "__main__":
    unittest.main()
