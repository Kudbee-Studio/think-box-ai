"""Tests for Memory -> Planning binding (PR #232).

Proves:
1. prior_recommendation parameter on TaskDecomposer.decompose seeds additional task nodes
2. regression_followup type creates investigation sub-tasks
3. anomaly_followup type creates investigation sub-tasks
4. validation_run type does not create additional sub-tasks
5. None recommendation preserves default behavior (single root task)
6. ThinkBoxEngine.set_experiment_manager + execute_goal wires recommendation into decomposition
7. ExperimentManager stores recommendation that get_last_next_action retrieves
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock

from thinkbox.decomposer import TaskDecomposer, TaskGraph
from thinkbox.experiment import ExperimentManager
from thinkbox.experiment_analytics import ExperimentAnalytics, NextActionGenerator
from thinkbox.engine import ThinkBoxEngine, EngineConfig


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
    run2 = {"throughput": 5.0, "p50_latency": 0.5, "p95_latency": 0.8,
            "p99_latency": 1.2, "error_rate": 0.1, "iteration_count": 2}
    analytics.persist_run(exp.experiment_id, run1)
    analytics.persist_run(exp.experiment_id, run2)
    return exp.experiment_id


def _produce_recommendation(manager: ExperimentManager, analytics: ExperimentAnalytics, exp_id: str) -> dict:
    generator = NextActionGenerator(manager, analytics)
    action = generator.generate(exp_id, {"status": "completed"}, confidence=0.9)
    return action["recommended_next_experiment"]


class TestDecomposerRecommendation(unittest.TestCase):
    """Test the TaskDecomposer.decompose() recommendation wiring."""

    def setUp(self) -> None:
        self.decomposer = TaskDecomposer()

    def test_none_recommendation_single_root(self) -> None:
        """No recommendation -> single root task (default behavior)."""
        graph = self.decomposer.decompose("Fix authentication bug", prior_recommendation=None)
        self.assertEqual(len(graph.tasks), 1)
        self.assertEqual(graph.root_id in graph.tasks, True)
        root = graph.tasks[graph.root_id]
        self.assertEqual(root.dependencies, [])

    def test_regression_followup_creates_investigation_tasks(self) -> None:
        """regression_followup type with adjustments -> investigation sub-tasks dependent on root."""
        rec = {
            "type": "regression_followup",
            "rationale": "Regression detected",
            "adjustments": [
                {"metric": "error_rate", "action": "investigate_root_cause"},
                {"metric": "throughput", "action": "investigate_root_cause"},
            ],
            "max_retries": 2,
        }
        graph = self.decomposer.decompose("Fix auth bug", prior_recommendation=rec)
        self.assertGreater(len(graph.tasks), 1)
        root = graph.tasks[graph.root_id]
        sub_tasks = [t for t in graph.tasks.values() if t.id != root.id]
        self.assertEqual(len(sub_tasks), 2)
        for sub in sub_tasks:
            self.assertIn(root.id, sub.dependencies)
            self.assertEqual(sub.metadata["generated_from"], "prior_recommendation")
            self.assertEqual(sub.metadata["recommendation_type"], "regression_followup")
            self.assertIn("target_metric", sub.metadata)
            self.assertIn("recommended_action", sub.metadata)

    def test_anomaly_followup_creates_investigation_tasks(self) -> None:
        """anomaly_followup type -> anomaly investigation sub-tasks."""
        rec = {
            "type": "anomaly_followup",
            "rationale": "Anomalies detected",
            "adjustments": [
                {"type": "high_error_rate", "action": "investigate"},
                {"type": "high_p99_latency", "action": "investigate"},
            ],
            "max_retries": 2,
        }
        graph = self.decomposer.decompose("Optimize query", prior_recommendation=rec)
        root = graph.tasks[graph.root_id]
        sub_tasks = [t for t in graph.tasks.values() if t.id != root.id]
        self.assertEqual(len(sub_tasks), 2)
        for sub in sub_tasks:
            self.assertIn(root.id, sub.dependencies)
            self.assertEqual(sub.metadata["generated_from"], "prior_recommendation")
            self.assertEqual(sub.metadata["recommendation_type"], "anomaly_followup")
            self.assertIn("anomaly_type", sub.metadata)

    def test_validation_run_no_subtasks(self) -> None:
        """validation_run type with empty adjustments -> no sub-tasks (default behavior)."""
        rec = {
            "type": "validation_run",
            "rationale": "No regression detected",
            "adjustments": [],
            "max_retries": 1,
        }
        graph = self.decomposer.decompose("Validate fix", prior_recommendation=rec)
        self.assertEqual(len(graph.tasks), 1)


class TestRecommendationRetrieval(unittest.TestCase):
    """Test 7: ExperimentManager stores and retrieves recommendations."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager = _make_manager(self.tmpdir)
        self.analytics = ExperimentAnalytics(self.manager)
        self.generator = NextActionGenerator(self.manager, self.analytics)

    def test_recommendation_persisted_and_retrieved(self) -> None:
        exp_id = _create_exp_with_metrics(self.manager, self.analytics)
        rec = _produce_recommendation(self.manager, self.analytics, exp_id)

        retrieved = self.manager.get_last_next_action()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["type"], rec["type"])


class TestEngineIntegration(unittest.TestCase):
    """Test 6: ThinkBoxEngine wires recommendation into decomposition."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager = _make_manager(self.tmpdir)
        self.analytics = ExperimentAnalytics(self.manager)

    def test_engine_seeds_graph_from_prior_recommendation(self) -> None:
        """Engine with injected ExperimentManager produces enriched task graph."""
        exp_id = _create_exp_with_metrics(self.manager, self.analytics)
        rec = _produce_recommendation(self.manager, self.analytics, exp_id)
        self.assertEqual(rec["type"], "regression_followup")

        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.set_experiment_manager(self.manager)

        graph = engine.decomposer.decompose("Test goal", prior_recommendation=rec)
        self.assertGreater(len(graph.tasks), 1)
        root = graph.tasks[graph.root_id]
        subs = [t for t in graph.tasks.values() if t.id != root.id]
        self.assertGreater(len(subs), 0)
        for sub in subs:
            self.assertEqual(sub.metadata["generated_from"], "prior_recommendation")
            self.assertIn(root.id, sub.dependencies)

    def test_engine_no_manager_preserves_default(self) -> None:
        """Engine without ExperimentManager produces single-root graph."""
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        graph = engine.decomposer.decompose("Test goal", prior_recommendation=None)
        self.assertEqual(len(graph.tasks), 1)


class TestFullBindingChain(unittest.TestCase):
    """End-to-end: prior experiment recommendation flows through to task graph parameterization."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager = _make_manager(self.tmpdir)
        self.analytics = ExperimentAnalytics(self.manager)

    def test_prior_recommendation_flows_to_graph(self) -> None:
        """Full chain: NextActionGenerator produces rec -> ExperimentManager persists -> Engine retrieves + seeds graph."""
        exp_id = _create_exp_with_metrics(self.manager, self.analytics)
        rec = _produce_recommendation(self.manager, self.analytics, exp_id)

        retrieved = self.manager.get_last_next_action()
        self.assertIsNotNone(retrieved)

        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.set_experiment_manager(self.manager)

        recommendation = engine._experiment_manager.get_last_next_action()
        graph = engine.decomposer.decompose("Resolve production incident", prior_recommendation=recommendation)

        self.assertGreater(len(graph.tasks), 1)
        root = graph.tasks[graph.root_id]
        subs = [t for t in graph.tasks.values() if t.id != root.id]
        self.assertGreater(len(subs), 0)
        for sub in subs:
            self.assertEqual(sub.metadata["recommendation_type"], rec["type"])
            self.assertIn("prior_recommendation", sub.metadata["generated_from"])


if __name__ == "__main__":
    unittest.main()
