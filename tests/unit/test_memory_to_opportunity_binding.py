"""Tests for Memory -> Opportunity binding (PR #233).

Proves:
1. PRLifecycleConfig accepts prior_recommendation field
2. PRLifecycleConfig.from_prior_experiments() seeds config from ExperimentManager
3. Orchestrator uses config.prior_recommendation (explicit founder review) over auto-retrieval
4. No prior_recommendation and no auto-retrieval → default behavior
5. Config-sourced recommendation has correct event source label
6. Full founder-driven flow: prior experiment → config from prior → orchestrator seeds params
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from thinkbox.experiment import ExperimentManager
from thinkbox.experiment_analytics import ExperimentAnalytics, NextActionGenerator
from thinkbox.pr_lifecycle import (
    PRLifecycleConfig,
    PRLifecycleOrchestrator,
    PRLifecycleState,
)


def _make_manager(tmpdir: str) -> ExperimentManager:
    db_path = os.path.join(tmpdir, "experiments.db")
    artifacts_dir = os.path.join(tmpdir, "artifacts")
    return ExperimentManager(db_path=db_path, artifacts_dir=artifacts_dir)


def _produce_recommendation(manager: ExperimentManager, analytics: ExperimentAnalytics) -> dict:
    session = manager.create_session(agent_id="test_agent")
    exp = manager.create_experiment(intent="baseline", hypothesis="h0", agent_id="test_agent")
    run1 = {"throughput": 10.0, "p50_latency": 0.3, "p95_latency": 0.5,
            "p99_latency": 0.8, "error_rate": 0.01, "iteration_count": 1}
    run2 = {"throughput": 5.0, "p50_latency": 0.5, "p95_latency": 0.8,
            "p99_latency": 1.2, "error_rate": 0.1, "iteration_count": 2}
    analytics.persist_run(exp.experiment_id, run1)
    analytics.persist_run(exp.experiment_id, run2)
    generator = NextActionGenerator(manager, analytics)
    action = generator.generate(exp.experiment_id, {"status": "completed"}, confidence=0.9)
    return action["recommended_next_experiment"]


class TestConfigPriorRecommendationField(unittest.TestCase):
    def test_config_accepts_prior_recommendation(self) -> None:
        rec = {"type": "validation_run", "rationale": "stable", "adjustments": [], "max_retries": 1}
        config = PRLifecycleConfig(pr_number=233, prior_recommendation=rec)
        self.assertEqual(config.prior_recommendation, rec)

    def test_config_defaults_to_none(self) -> None:
        config = PRLifecycleConfig(pr_number=233)
        self.assertIsNone(config.prior_recommendation)


class TestConfigFromPriorExperiments(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager = _make_manager(self.tmpdir)
        self.analytics = ExperimentAnalytics(self.manager)

    def test_from_prior_experiments_seeds_recommendation(self) -> None:
        _produce_recommendation(self.manager, self.analytics)
        config = PRLifecycleConfig.from_prior_experiments(233, self.manager, test_mode=True)
        self.assertIsNotNone(config.prior_recommendation)
        self.assertEqual(config.pr_number, 233)

    def test_from_prior_experiments_no_priors_returns_none(self) -> None:
        config = PRLifecycleConfig.from_prior_experiments(233, self.manager, test_mode=True)
        self.assertIsNone(config.prior_recommendation)


class TestOrchestratorUsesConfigOverAutoRetrieval(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager = _make_manager(self.tmpdir)
        self.analytics = ExperimentAnalytics(self.manager)

    def test_config_recommendation_used_over_auto(self) -> None:
        """When config.prior_recommendation is set, it takes priority over auto-retrieval."""
        _produce_recommendation(self.manager, self.analytics)

        explicit_rec = {
            "type": "regression_followup",
            "rationale": "explicitly seeded by founder",
            "adjustments": [{"metric": "error_rate", "action": "deep_investigation"}],
            "max_retries": 3,
        }
        config = PRLifecycleConfig(
            pr_number=233,
            test_mode=True,
            approvals={"merge": True},
            prior_recommendation=explicit_rec,
        )
        orch = PRLifecycleOrchestrator(config, manager=self.manager, analytics=self.analytics)
        result = orch.run()

        exp_id = result.context.get("experiment_id")
        self.assertIsNotNone(exp_id)
        exp = self.manager.db.get_experiment(exp_id)
        params = json.loads(exp["parameters"])
        self.assertEqual(params["prior_recommendation_type"], "regression_followup")
        self.assertEqual(params["prior_recommendation_max_retries"], 3)
        self.assertIn("deep_investigation", params["prior_recommendation_adjustments"][0]["action"])

        events = self.manager.db.get_events_by_experiment(exp_id)
        consumed = [e for e in events if e.get("event_type") == "recommendation_consumed"]
        data = json.loads(consumed[0]["data"]) if isinstance(consumed[0]["data"], str) else consumed[0]["data"]
        self.assertEqual(data["recommendation_source"], "config")

    def test_no_config_no_auto_uses_default(self) -> None:
        """No config recommendation and no auto-retrieval → default behavior."""
        analytics = ExperimentAnalytics(self.manager)
        config = PRLifecycleConfig(
            pr_number=233,
            test_mode=True,
            approvals={"merge": True},
        )
        orch = PRLifecycleOrchestrator(config, manager=self.manager, analytics=analytics)
        result = orch.run()

        exp_id = result.context.get("experiment_id")
        exp = self.manager.db.get_experiment(exp_id)
        params = json.loads(exp["parameters"]) if exp["parameters"] else {}
        self.assertNotIn("prior_recommendation_type", params)
        self.assertEqual(exp["intent"], "pr-233-lifecycle")
        self.assertEqual(exp["hypothesis"], "Local deterministic PR lifecycle experiment")

        events = self.manager.db.get_events_by_experiment(exp_id)
        consumed = [e for e in events if e.get("event_type") == "recommendation_consumed"]
        data = json.loads(consumed[0]["data"]) if isinstance(consumed[0]["data"], str) else consumed[0]["data"]
        self.assertEqual(data["recommendation_source"], "none")


class TestFullFounderDrivenFlow(unittest.TestCase):
    """End-to-end: prior experiment → config from_prior_experiments → orchestrator → seeded params."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager = _make_manager(self.tmpdir)
        self.analytics = ExperimentAnalytics(self.manager)

    def test_full_flow(self) -> None:
        _produce_recommendation(self.manager, self.analytics)

        config = PRLifecycleConfig.from_prior_experiments(
            234, self.manager,
            test_mode=True,
            approvals={"merge": True},
            deterministic_metrics=[
                {"throughput": 10.0, "p50_latency": 0.3, "p95_latency": 0.5,
                 "p99_latency": 0.8, "error_rate": 0.01, "iteration_count": 1},
                {"throughput": 12.0, "p50_latency": 0.28, "p95_latency": 0.48,
                 "p99_latency": 0.75, "error_rate": 0.008, "iteration_count": 2},
            ],
        )
        self.assertIsNotNone(config.prior_recommendation)

        orch = PRLifecycleOrchestrator(config, manager=self.manager, analytics=self.analytics)
        result = orch.run()
        self.assertEqual(result.terminal_state, PRLifecycleState.LEARN.value)

        self.assertIn("prior_recommendation", result.context)
        exp_id = result.context["experiment_id"]
        exp = self.manager.db.get_experiment(exp_id)
        params = json.loads(exp["parameters"])
        self.assertIn("prior_recommendation_type", params)

        events = self.manager.db.get_events_by_experiment(exp_id)
        consumed = [e for e in events if e.get("event_type") == "recommendation_consumed"]
        data = json.loads(consumed[0]["data"]) if isinstance(consumed[0]["data"], str) else consumed[0]["data"]
        self.assertEqual(data["recommendation_source"], "config")


if __name__ == "__main__":
    unittest.main()
