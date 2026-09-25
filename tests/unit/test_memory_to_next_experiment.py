"""Tests for Memory → Next Experiment binding (PR #224).

Proves:
1. Prior experiment evidence (recommended_next_experiment) is persisted.
2. NextActionGenerator generates it.
3. ExperimentManager.get_last_next_action() retrieves it.
4. PRLifecycleOrchestrator consumes it to seed the next experiment's parameters.
5. No prior evidence → default behavior (parameters=None, original intent/hypothesis).
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from thinkbox.experiment import (
    ExperimentManager,
    FourState,
)
from thinkbox.experiment_analytics import (
    ExperimentAnalytics,
    NextActionGenerator,
)
from thinkbox.pr_lifecycle import (
    PRLifecycleOrchestrator,
    PRLifecycleConfig,
    PRLifecycleState,
)


def _make_manager(tmpdir: str) -> ExperimentManager:
    db_path = os.path.join(tmpdir, "experiments.db")
    artifacts_dir = os.path.join(tmpdir, "artifacts")
    return ExperimentManager(db_path=db_path, artifacts_dir=artifacts_dir)


def _create_exp_with_metrics(manager: ExperimentManager, analytics: ExperimentAnalytics) -> str:
    session = manager.create_session(agent_id="test_agent")
    exp = manager.create_experiment(
        intent="baseline test", hypothesis="h0", agent_id="test_agent",
    )
    run1 = {"throughput": 10.0, "p50_latency": 0.3, "p95_latency": 0.5,
            "p99_latency": 0.8, "error_rate": 0.01, "iteration_count": 1}
    run2 = {"throughput": 12.0, "p50_latency": 0.28, "p95_latency": 0.48,
            "p99_latency": 0.75, "error_rate": 0.008, "iteration_count": 2}
    analytics.persist_run(exp.experiment_id, run1)
    analytics.persist_run(exp.experiment_id, run2)
    return exp.experiment_id


class TestPriorEvidencePersisted(unittest.TestCase):
    """Test 1: recommended_next_experiment is persisted to SQLite via events table."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager = _make_manager(self.tmpdir)
        self.analytics = ExperimentAnalytics(self.manager)
        self.generator = NextActionGenerator(self.manager, self.analytics)

    def test_recommended_next_experiment_persisted(self) -> None:
        exp_id = _create_exp_with_metrics(self.manager, self.analytics)
        action = self.generator.generate(exp_id, {"status": "completed"}, confidence=0.9)

        events = self.manager.db.get_events_by_experiment(exp_id)
        next_action_events = [e for e in events if e.get("event_type") == "next_action_generated"]
        self.assertEqual(len(next_action_events), 1)
        data = next_action_events[0]["data"]
        if isinstance(data, str):
            data = json.loads(data)
        self.assertIn("recommended_next_experiment", data)
        rec = data["recommended_next_experiment"]
        self.assertIn("type", rec)
        self.assertIn("rationale", rec)
        self.assertIn("adjustments", rec)
        self.assertIn("max_retries", rec)

    def test_get_last_next_action_retrieves_recommendation(self) -> None:
        exp_id = _create_exp_with_metrics(self.manager, self.analytics)
        self.generator.generate(exp_id, {"status": "completed"}, confidence=0.9)

        rec = self.manager.get_last_next_action()
        self.assertIsNotNone(rec)
        self.assertIn("type", rec)
        self.assertIn("adjustments", rec)
        self.assertIn("max_retries", rec)


class TestRecommendationConsumed(unittest.TestCase):
    """Test 3-4: PRLifecycleOrchestrator consumes recommendation to seed next experiment."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager = _make_manager(self.tmpdir)

    def test_orchestrator_seeds_params_from_prior_recommendation(self) -> None:
        """Simulate: prior experiment produced a recommendation, next orchestrator run consumes it."""
        analytics = ExperimentAnalytics(self.manager)
        generator = NextActionGenerator(self.manager, analytics)
        exp_id = _create_exp_with_metrics(self.manager, analytics)
        generator.generate(exp_id, {"status": "completed"}, confidence=0.9)

        prior_rec = self.manager.get_last_next_action()
        self.assertIsNotNone(prior_rec)

        config = PRLifecycleConfig(
            pr_number=224,
            test_mode=True,
            approvals={"merge": True},
            deterministic_metrics=[
                {"throughput": 10.0, "p50_latency": 0.3, "p95_latency": 0.5,
                 "p99_latency": 0.8, "error_rate": 0.01, "iteration_count": 1},
            ],
        )
        orch = PRLifecycleOrchestrator(config, manager=self.manager, analytics=analytics)
        result = orch.run()

        next_exp_id = result.context.get("experiment_id")
        self.assertIsNotNone(next_exp_id)
        next_exp = self.manager.db.get_experiment(next_exp_id)
        self.assertIsNotNone(next_exp)

        params = json.loads(next_exp["parameters"]) if next_exp["parameters"] else {}
        self.assertIn("prior_recommendation_type", params)
        self.assertEqual(params["prior_recommendation_type"], prior_rec["type"])
        self.assertEqual(params["prior_recommendation_max_retries"], prior_rec["max_retries"])
        self.assertIn("prior_recommendation", result.context)

        events = self.manager.db.get_events_by_experiment(next_exp_id)
        consumed_events = [e for e in events if e.get("event_type") == "recommendation_consumed"]
        self.assertEqual(len(consumed_events), 1)
        consumed_data = consumed_events[0]["data"]
        if isinstance(consumed_data, str):
            consumed_data = json.loads(consumed_data)
        self.assertTrue(consumed_data["consumed"])

    def test_orchestrator_no_prior_recommendation_uses_default(self) -> None:
        """When no prior recommendation exists, default behavior is preserved."""
        analytics = ExperimentAnalytics(self.manager)
        config = PRLifecycleConfig(
            pr_number=224,
            test_mode=True,
            approvals={"merge": True},
        )
        orch = PRLifecycleOrchestrator(config, manager=self.manager, analytics=analytics)
        result = orch.run()

        next_exp_id = result.context.get("experiment_id")
        self.assertIsNotNone(next_exp_id)
        next_exp = self.manager.db.get_experiment(next_exp_id)

        params = json.loads(next_exp["parameters"]) if next_exp["parameters"] else {}
        self.assertNotIn("prior_recommendation_type", params)
        self.assertEqual(next_exp["intent"], "pr-224-lifecycle")
        self.assertEqual(next_exp["hypothesis"], "Local deterministic PR lifecycle experiment")


class TestFullBindingLoop(unittest.TestCase):
    """Test 6: End-to-end — two consecutive PRLifecycleOrchestrator runs, second consumes first's recommendation."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager = _make_manager(self.tmpdir)

    def test_two_runs_binding(self) -> None:
        """First run produces recommendation; second run consumes it to seed parameters."""
        metrics = [
            {"throughput": 10.0, "p50_latency": 0.3, "p95_latency": 0.5,
             "p99_latency": 0.8, "error_rate": 0.01, "iteration_count": 1},
            {"throughput": 15.0, "p50_latency": 0.2, "p95_latency": 0.4,
             "p99_latency": 0.7, "error_rate": 0.005, "iteration_count": 2},
        ]

        config1 = PRLifecycleConfig(
            pr_number=225,
            test_mode=True,
            approvals={"merge": True},
            deterministic_metrics=metrics,
        )
        orch1 = PRLifecycleOrchestrator(config1, manager=self.manager)
        result1 = orch1.run()
        self.assertEqual(result1.terminal_state, PRLifecycleState.LEARN.value)

        rec = self.manager.get_last_next_action()
        self.assertIsNotNone(rec)
        rec_type = rec["type"]

        config2 = PRLifecycleConfig(
            pr_number=226,
            test_mode=True,
            approvals={"merge": True},
            deterministic_metrics=metrics,
        )
        orch2 = PRLifecycleOrchestrator(config2, manager=self.manager)
        result2 = orch2.run()

        self.assertIn("prior_recommendation", result2.context)
        self.assertEqual(result2.context["prior_recommendation"]["type"], rec_type)

        exp2_id = result2.context["experiment_id"]
        exp2 = self.manager.db.get_experiment(exp2_id)
        params = json.loads(exp2["parameters"])
        self.assertEqual(params["prior_recommendation_type"], rec_type)


if __name__ == "__main__":
    unittest.main()
