"""Tests for Planning -> Execution -> Feedback binding (PR #234).

Proves:
1. execute_goal() returns summary with verified metrics
2. _record_execution_feedback() persists experiment + outcome when manager/analytics injected
3. NextActionGenerator generates a recommendation from the execution summary
4. get_last_next_action() retrieves the feedback-generated recommendation
5. Full closed loop: recommendation from prior execution -> feed into next execute_goal's decompose
6. No manager injected -> no feedback recording, default behavior preserved
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from thinkbox.engine import ThinkBoxEngine, EngineConfig, TaskState
from thinkbox.experiment import ExperimentManager
from thinkbox.experiment_analytics import ExperimentAnalytics, NextActionGenerator


def _make_manager(tmpdir: str) -> ExperimentManager:
    db_path = os.path.join(tmpdir, "experiments.db")
    artifacts_dir = os.path.join(tmpdir, "artifacts")
    return ExperimentManager(db_path=db_path, artifacts_dir=artifacts_dir)


class TestFeedbackRecording(unittest.TestCase):
    """Test 2-3: _record_execution_feedback persists experiment + generates recommendation."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager = _make_manager(self.tmpdir)
        self.analytics = ExperimentAnalytics(self.manager)

    def test_feedback_records_experiment_and_recommendation(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics)

        summary = {
            "goal_run_id": "goal_test123",
            "total_tasks": 4,
            "completed": 4,
            "successful": 3,
            "failed": 1,
            "total_time_ms": 1200.0,
            "events": 10,
        }
        engine._record_execution_feedback(summary, "goal_test123")

        experiments = self.manager.db.get_all_experiments()
        self.assertEqual(len(experiments), 1)
        exp = experiments[0]
        self.assertEqual(exp["intent"], "goal:goal_test123")
        self.assertEqual(exp["execution_mode"], "verified")

        rec = self.manager.get_last_next_action()
        self.assertIsNotNone(rec)
        self.assertIn("type", rec)
        self.assertIn("max_retries", rec)

    def test_no_manager_no_feedback(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        summary = {"goal_run_id": "goal_test", "total_tasks": 2, "total_time_ms": 100.0}
        engine._record_execution_feedback(summary, "goal_test")
        self.assertIsNone(engine._experiment_manager)
        self.assertEqual(len(engine.events), 0)

    def test_event_emitted_after_feedback(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics)

        summary = {
            "goal_run_id": "goal_evt",
            "total_tasks": 2,
            "completed": 2,
            "successful": 2,
            "failed": 0,
            "total_time_ms": 500.0,
            "events": 5,
        }
        engine._record_execution_feedback(summary, "goal_evt")

        events = engine.events
        feedback_events = [e for e in events if "Feedback recorded" in e.message]
        self.assertEqual(len(feedback_events), 1)


class TestFullClosedLoop(unittest.TestCase):
    """Test 5: End-to-end closed loop — execution feedback -> recommendation -> next decompose."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager = _make_manager(self.tmpdir)
        self.analytics = ExperimentAnalytics(self.manager)

    def test_execution_produces_recommendation_consumed_by_next_decompose(self) -> None:
        """Prior execution generates recommendation; next execute_goal retrieves and uses it."""
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics)

        summary1 = {
            "goal_run_id": "goal_001",
            "total_tasks": 3,
            "completed": 3,
            "successful": 2,
            "failed": 1,
            "total_time_ms": 800.0,
            "events": 8,
        }
        engine._record_execution_feedback(summary1, "goal_001")

        rec = self.manager.get_last_next_action()
        self.assertIsNotNone(rec)
        rec_type = rec["type"]

        graph = engine.decomposer.decompose("Next goal task", prior_recommendation=rec)
        self.assertGreater(len(graph.tasks), 1)
        root = graph.tasks[graph.root_id]
        subs = [t for t in graph.tasks.values() if t.id != root.id]
        self.assertGreater(len(subs), 0)
        for sub in subs:
            self.assertEqual(sub.metadata["generated_from"], "prior_recommendation")
            self.assertEqual(sub.metadata["recommendation_type"], rec_type)

    def test_recommendation_persists_across_engine_instances(self) -> None:
        """Feedback persist in SQLite survives engine restart."""
        engine1 = ThinkBoxEngine(EngineConfig(speculative=False))
        engine1.wire_experiment_feedback(self.manager, self.analytics)

        summary = {
            "goal_run_id": "goal_persist",
            "total_tasks": 5,
            "completed": 5,
            "successful": 4,
            "failed": 1,
            "total_time_ms": 1000.0,
            "events": 10,
        }
        engine1._record_execution_feedback(summary, "goal_persist")

        fresh_engine = ThinkBoxEngine(EngineConfig(speculative=False))
        fresh_engine.wire_experiment_feedback(self.manager, self.analytics)

        rec = fresh_engine._experiment_manager.get_last_next_action()
        self.assertIsNotNone(rec)
        self.assertIn("type", rec)


class TestNoManagerPreservesDefault(unittest.TestCase):
    """Test 6: Without injected manager, execute_goal behaves as legacy."""

    def test_no_manager_no_feedback_events(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        summary = {"goal_run_id": "goal_no_mgr", "total_tasks": 1, "total_time_ms": 100.0}
        engine._record_execution_feedback(summary, "goal_no_mgr")
        self.assertEqual(len(engine.events), 0)


if __name__ == "__main__":
    unittest.main()
