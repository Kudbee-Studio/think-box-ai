"""Tests for ExperimentAnalytics, lifecycle, NextAction, Replay, and Approval.

Covers: aggregation, comparison, regression, lifecycle, next action,
replay, approval boundary, proof decisions, persistence/reload.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import sqlite3

from thinkbox.experiment import (
    ExperimentManager,
    ExperimentRecord,
    ParameterProvenance,
    ParameterClassification,
    ProvenanceSource,
)
from thinkbox.experiment_analytics import (
    ExperimentAnalytics,
    ExperimentLifecycle,
    NextActionGenerator,
    ReplayEngine,
    ApprovalBoundary,
    ProofDecision,
    METRIC_KEYS,
)
from thinkbox.pr_db import PRDatabaseConfig, PRDatabaseProvisioner, PRDBState


def _make_manager(tmpdir: str) -> ExperimentManager:
    db_path = os.path.join(tmpdir, "experiments.db")
    os.makedirs(tmpdir, exist_ok=True)
    return ExperimentManager(db_path=db_path)


def _create_exp(manager: ExperimentManager, intent: str = "test") -> str:
    session = manager.create_session(agent_id="test_agent")
    exp = manager.create_experiment(
        intent=intent, hypothesis="test hypothesis", agent_id="test_agent",
    )
    return exp.experiment_id


class TestExperimentAnalyticsCore(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager = _make_manager(self.tmpdir)
        self.analytics = ExperimentAnalytics(self.manager)

    def _seed_artifacts(self, exp_id: str, count: int) -> None:
        for i in range(count):
            run_data = {
                "throughput": 10.0 + i * 2.0,
                "p50_latency": 0.3 + i * 0.05,
                "p95_latency": 0.5 + i * 0.07,
                "p99_latency": 0.8 + i * 0.1,
                "error_rate": 0.01 + i * 0.01,
                "iteration_count": i + 1,
            }
            self.analytics.persist_run(exp_id, run_data)

    def test_zero_history(self) -> None:
        exp_id = _create_exp(self.manager)
        with self.assertRaises(ValueError):
            self.analytics.aggregate_metrics(exp_id)

    def test_first_run(self) -> None:
        exp_id = _create_exp(self.manager)
        run_data = {
            "throughput": 10.0,
            "p50_latency": 0.3,
            "p95_latency": 0.5,
            "p99_latency": 0.8,
            "error_rate": 0.01,
            "iteration_count": 1,
        }
        artifact_id = self.analytics.persist_run(exp_id, run_data)
        self.assertTrue(artifact_id.startswith("art_"))
        result = self.analytics.aggregate_metrics(exp_id)
        self.assertEqual(result["n_runs"], 1)
        self.assertEqual(result["summary"]["throughput"]["mean"], 10.0)

    def test_single_run(self) -> None:
        exp_id = _create_exp(self.manager)
        self._seed_artifacts(exp_id, 1)
        result = self.analytics.aggregate_metrics(exp_id)
        self.assertEqual(result["n_runs"], 1)
        self.assertIn("summary", result)

    def test_multiple_runs(self) -> None:
        exp_id = _create_exp(self.manager)
        self._seed_artifacts(exp_id, 5)
        result = self.analytics.aggregate_metrics(exp_id)
        self.assertEqual(result["n_runs"], 5)
        self.assertAlmostEqual(
            result["summary"]["throughput"]["mean"], 14.0, places=4
        )

    def test_missing_metrics(self) -> None:
        exp_id = _create_exp(self.manager)
        with self.assertRaises(ValueError) as ctx:
            self.analytics.persist_run(exp_id, {"throughput": 10.0})
        self.assertIn("Missing required metric", str(ctx.exception))

    def test_malformed_metrics_non_numeric(self) -> None:
        exp_id = _create_exp(self.manager)
        with self.assertRaises(ValueError):
            self.analytics.persist_run(exp_id, {
                "throughput": "fast",
                "p50_latency": 0.3,
                "p95_latency": 0.5,
                "p99_latency": 0.8,
                "error_rate": 0.01,
                "iteration_count": 1,
            })

    def test_compare_runs(self) -> None:
        exp_id = _create_exp(self.manager)
        self._seed_artifacts(exp_id, 3)
        comparison = self.analytics.compare_runs(exp_id)
        self.assertEqual(comparison["n_comparisons"], 2)
        self.assertIn("comparisons", comparison)

    def test_compare_runs_insufficient(self) -> None:
        exp_id = _create_exp(self.manager)
        run_data = {
            "throughput": 10.0, "p50_latency": 0.3, "p95_latency": 0.5,
            "p99_latency": 0.8, "error_rate": 0.01, "iteration_count": 1,
        }
        self.analytics.persist_run(exp_id, run_data)
        with self.assertRaises(ValueError):
            self.analytics.compare_runs(exp_id)

    def test_regression_beyond_threshold(self) -> None:
        exp_id = _create_exp(self.manager)
        run1 = {
            "throughput": 20.0, "p50_latency": 0.3, "p95_latency": 0.5,
            "p99_latency": 0.8, "error_rate": 0.01, "iteration_count": 1,
        }
        run2 = {
            "throughput": 15.0, "p50_latency": 0.4, "p95_latency": 0.6,
            "p99_latency": 0.9, "error_rate": 0.02, "iteration_count": 2,
        }
        self.analytics.persist_run(exp_id, run1)
        self.analytics.persist_run(exp_id, run2)
        result = self.analytics.detect_regression(metric="throughput", experiment_id=exp_id)
        self.assertTrue(result["is_regression"])
        self.assertIn("pct_change", result)

    def test_regression_at_threshold(self) -> None:
        exp_id = _create_exp(self.manager)
        run1 = {"throughput": 20.0, "p50_latency": 0.3, "p95_latency": 0.5,
                "p99_latency": 0.8, "error_rate": 0.01, "iteration_count": 1}
        run2 = {"throughput": 19.0, "p50_latency": 0.4, "p95_latency": 0.6,
                "p99_latency": 0.9, "error_rate": 0.02, "iteration_count": 2}
        self.analytics.persist_run(exp_id, run1)
        self.analytics.persist_run(exp_id, run2)
        result = self.analytics.detect_regression(metric="throughput", experiment_id=exp_id)
        self.assertFalse(result["is_regression"])
        pct = result["pct_change"]
        self.assertAlmostEqual(pct, -5.0, places=2)

    def test_improvement(self) -> None:
        exp_id = _create_exp(self.manager)
        run1 = {"throughput": 10.0, "p50_latency": 0.4, "p95_latency": 0.6,
                "p99_latency": 0.9, "error_rate": 0.02, "iteration_count": 1}
        run2 = {"throughput": 20.0, "p50_latency": 0.3, "p95_latency": 0.5,
                "p99_latency": 0.8, "error_rate": 0.01, "iteration_count": 2}
        self.analytics.persist_run(exp_id, run1)
        self.analytics.persist_run(exp_id, run2)
        result = self.analytics.detect_regression(metric="throughput", experiment_id=exp_id)
        self.assertFalse(result["is_regression"])
        self.assertGreater(result["pct_change"], 0)

    def test_query_history(self) -> None:
        exp_id = _create_exp(self.manager)
        self._seed_artifacts(exp_id, 3)
        history = self.analytics.query_history(metric="throughput", limit=10)
        self.assertEqual(history["n_runs"], 3)
        self.assertIn("trend_direction", history)
        self.assertIn("runs", history)

    def test_query_history_unknown_metric(self) -> None:
        exp_id = _create_exp(self.manager)
        with self.assertRaises(ValueError):
            self.analytics.query_history(metric="invalid_metric")

    def test_proof_linkage(self) -> None:
        exp_id = _create_exp(self.manager)
        run_data = {
            "throughput": 10.0, "p50_latency": 0.3, "p95_latency": 0.5,
            "p99_latency": 0.8, "error_rate": 0.01, "iteration_count": 1,
        }
        self.analytics.persist_run(exp_id, run_data)
        self.manager.add_proof(exp_id, {
            "proof_sha256": "abc123",
            "decision": "validated",
            "experiment_id": exp_id,
        })
        exp = self.manager.db.get_experiment(exp_id)
        self.assertIsNotNone(exp)
        proof_data = self.manager.db.get_experiment(exp_id)
        self.assertIn("proof", str(proof_data).lower())

    def test_persistence_reload(self) -> None:
        exp_id = _create_exp(self.manager)
        run_data = {
            "throughput": 10.0, "p50_latency": 0.3, "p95_latency": 0.5,
            "p99_latency": 0.8, "error_rate": 0.01, "iteration_count": 1,
        }
        self.analytics.persist_run(exp_id, run_data)

        db_path = os.path.join(self.tmpdir, "experiments.db")
        manager2 = _make_manager(self.tmpdir)
        analytics2 = ExperimentAnalytics(manager2)
        result = analytics2.aggregate_metrics(exp_id)
        self.assertEqual(result["n_runs"], 1)

    def test_dashboard_data(self) -> None:
        exp_id = _create_exp(self.manager)
        run_data = {
            "throughput": 10.0, "p50_latency": 0.3, "p95_latency": 0.5,
            "p99_latency": 0.8, "error_rate": 0.01, "iteration_count": 1,
        }
        self.analytics.persist_run(exp_id, run_data)
        data = self.analytics.dashboard_data()
        self.assertIn("mercury_metrics", data)
        self.assertIn("total_runs", data["mercury_metrics"])
        self.assertEqual(data["mercury_metrics"]["total_runs"], 1)

    def test_lifecycle_states(self) -> None:
        self.assertEqual(ExperimentLifecycle.valid_states(), ["PROPOSED", "RUNNING", "OBSERVED", "VERIFIED", "COMPARED", "LEARNED"])

    def test_lifecycle_valid_transition(self) -> None:
        self.assertTrue(ExperimentLifecycle.can_transition("PROPOSED", "RUNNING"))
        self.assertTrue(ExperimentLifecycle.can_transition("RUNNING", "OBSERVED"))
        self.assertTrue(ExperimentLifecycle.can_transition("OBSERVED", "VERIFIED"))
        self.assertTrue(ExperimentLifecycle.can_transition("VERIFIED", "COMPARED"))
        self.assertTrue(ExperimentLifecycle.can_transition("COMPARED", "LEARNED"))

    def test_lifecycle_invalid_transition(self) -> None:
        self.assertFalse(ExperimentLifecycle.can_transition("PROPOSED", "VERIFIED"))
        self.assertFalse(ExperimentLifecycle.can_transition("LEARNED", "PROPOSED"))

    def test_lifecycle_validate_invalid(self) -> None:
        with self.assertRaises(ValueError):
            ExperimentLifecycle.validate_transition("PROPOSED", "VERIFIED")

    def test_lifecycle_instance(self) -> None:
        exp_id = _create_exp(self.manager)
        lc = ExperimentLifecycle(self.manager, exp_id)
        self.assertEqual(lc.current_state(), "PROPOSED")
        lc.transition("RUNNING")
        self.assertEqual(lc.current_state(), "RUNNING")

    def test_lifecycle_strict_order(self) -> None:
        exp_id = _create_exp(self.manager)
        lc = ExperimentLifecycle(self.manager, exp_id)
        states = ["PROPOSED", "RUNNING", "OBSERVED", "VERIFIED", "COMPARED", "LEARNED"]
        lc.transition(states[1])
        self.assertEqual(lc.current_state(), "RUNNING")
        lc.transition(states[2])
        self.assertEqual(lc.current_state(), "OBSERVED")
        lc.transition(states[3])
        self.assertEqual(lc.current_state(), "VERIFIED")
        lc.transition(states[4])
        self.assertEqual(lc.current_state(), "COMPARED")
        lc.transition(states[5])
        self.assertEqual(lc.current_state(), "LEARNED")


class TestNextActionGenerator(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager = _make_manager(self.tmpdir)
        self.analytics = ExperimentAnalytics(self.manager)
        self.generator = NextActionGenerator(self.manager, self.analytics)

    def test_generates_next_action(self) -> None:
        exp_id = _create_exp(self.manager)
        run1 = {"throughput": 20.0, "p50_latency": 0.3, "p95_latency": 0.5,
                "p99_latency": 0.8, "error_rate": 0.01, "iteration_count": 1}
        run2 = {"throughput": 25.0, "p50_latency": 0.2, "p95_latency": 0.4,
                "p99_latency": 0.7, "error_rate": 0.005, "iteration_count": 2}
        self.analytics.persist_run(exp_id, run1)
        self.analytics.persist_run(exp_id, run2)
        outcome = {"status": "completed", "summary": "test run"}
        action = self.generator.generate(exp_id, outcome, confidence=0.8)
        self.assertIn("next_action_id", action)
        self.assertIn("what_changed", action)
        self.assertIn("recommended_next_experiment", action)
        self.assertIn("evidence", action)
        self.assertIsInstance(action["requires_human_approval"], bool)

    def test_regression_triggers_approval(self) -> None:
        exp_id = _create_exp(self.manager)
        run1 = {"throughput": 20.0, "p50_latency": 0.3, "p95_latency": 0.5,
                "p99_latency": 0.8, "error_rate": 0.01, "iteration_count": 1}
        run2 = {"throughput": 10.0, "p50_latency": 0.5, "p95_latency": 0.8,
                "p99_latency": 1.2, "error_rate": 0.1, "iteration_count": 2}
        self.analytics.persist_run(exp_id, run1)
        self.analytics.persist_run(exp_id, run2)
        outcome = {"status": "completed"}
        action = self.generator.generate(exp_id, outcome, confidence=0.9)
        self.assertTrue(action["requires_human_approval"])

    def test_low_confidence_triggers_approval(self) -> None:
        exp_id = _create_exp(self.manager)
        run1 = {"throughput": 10.0, "p50_latency": 0.3, "p95_latency": 0.5,
                "p99_latency": 0.8, "error_rate": 0.01, "iteration_count": 1}
        run2 = {"throughput": 12.0, "p50_latency": 0.3, "p95_latency": 0.5,
                "p99_latency": 0.8, "error_rate": 0.01, "iteration_count": 2}
        self.analytics.persist_run(exp_id, run1)
        self.analytics.persist_run(exp_id, run2)
        outcome = {"status": "completed"}
        action = self.generator.generate(exp_id, outcome, confidence=0.3)
        self.assertTrue(action["requires_human_approval"])

    def test_high_confidence_no_regression(self) -> None:
        exp_id = _create_exp(self.manager)
        run1 = {"throughput": 10.0, "p50_latency": 0.3, "p95_latency": 0.5,
                "p99_latency": 0.8, "error_rate": 0.01, "iteration_count": 1}
        run2 = {"throughput": 15.0, "p50_latency": 0.2, "p95_latency": 0.4,
                "p99_latency": 0.7, "error_rate": 0.005, "iteration_count": 2}
        self.analytics.persist_run(exp_id, run1)
        self.analytics.persist_run(exp_id, run2)
        outcome = {"status": "completed"}
        action = self.generator.generate(exp_id, outcome, confidence=0.9)
        self.assertFalse(action["requires_human_approval"])


class TestReplayEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager = _make_manager(self.tmpdir)
        self.analytics = ExperimentAnalytics(self.manager)
        self.replayer = ReplayEngine(self.manager, self.analytics)

    def test_replay(self) -> None:
        exp_id = _create_exp(self.manager)
        run_data = {
            "throughput": 10.0, "p50_latency": 0.3, "p95_latency": 0.5,
            "p99_latency": 0.8, "error_rate": 0.01, "iteration_count": 1,
        }
        self.analytics.persist_run(exp_id, run_data)
        result = self.replayer.replay(exp_id)
        self.assertIn("metrics", result)
        self.assertIn("comparison", result)
        self.assertIn("history_context", result)
        self.assertIn("outcome", result)

    def test_replay_not_found(self) -> None:
        with self.assertRaises(ValueError):
            self.replayer.replay("nonexistent")

    def test_replay_insufficient_data(self) -> None:
        exp_id = _create_exp(self.manager)
        run_data = {
            "throughput": 10.0, "p50_latency": 0.3, "p95_latency": 0.5,
            "p99_latency": 0.8, "error_rate": 0.01, "iteration_count": 1,
        }
        self.analytics.persist_run(exp_id, run_data)
        result = self.replayer.replay(exp_id)
        self.assertEqual(result["metrics"]["n_runs"], 1)


class TestApprovalBoundary(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager = _make_manager(self.tmpdir)
        self.boundary = ApprovalBoundary(self.manager)

    def test_requires_approval_merge(self) -> None:
        self.assertTrue(self.boundary.requires_approval("merge"))

    def test_requires_approval_deploy(self) -> None:
        self.assertTrue(self.boundary.requires_approval("deploy_production"))

    def test_autonomous_inspect(self) -> None:
        self.assertFalse(self.boundary.requires_approval("inspect"))

    def test_autonomous_experiment(self) -> None:
        self.assertFalse(self.boundary.requires_approval("experiment"))

    def test_autonomous_create_branch(self) -> None:
        self.assertFalse(self.boundary.requires_approval("create_branch"))

    def test_boundary_complete(self) -> None:
        boundary = self.boundary.get_boundary()
        self.assertIn("autonomous", boundary)
        self.assertIn("approval_required", boundary)
        self.assertTrue(len(boundary["autonomous"]) > 0)
        self.assertTrue(len(boundary["approval_required"]) > 0)

    def test_record_decision(self) -> None:
        exp_id = _create_exp(self.manager)
        self.boundary.record_decision(exp_id, "merge", approved=True, approver="human")
        exp = self.manager.db.get_experiment(exp_id)
        self.assertIsNotNone(exp)


class TestProofDecision(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager = _make_manager(self.tmpdir)
        self.decision = ProofDecision(self.manager)

    def test_record_decision(self) -> None:
        exp_id = _create_exp(self.manager)
        self.decision.record(
            experiment_id=exp_id,
            decision="validated",
            proof_sha256="abc123",
            metrics={"throughput": 10.0},
            confidence=0.9,
        )
        exp = self.manager.db.get_experiment(exp_id)
        self.assertIsNotNone(exp)

    def test_record_decision_minimal(self) -> None:
        exp_id = _create_exp(self.manager)
        self.decision.record(experiment_id=exp_id, decision="review")
        exp = self.manager.db.get_experiment(exp_id)
        self.assertIsNotNone(exp)


class TestPRDBIntegration(unittest.TestCase):
    def test_pr_db_with_analytics(self) -> None:
        config = PRDatabaseConfig(pr_number=104, test_mode=True)
        provisioner = PRDatabaseProvisioner(config)
        record = provisioner.provision()
        provisioner.activate(record.db_id)
        manager = provisioner.get_manager(record.db_id)
        analytics = ExperimentAnalytics(manager)

        exp_id = _create_exp(manager, intent="pr104_test")
        run_data = {
            "throughput": 10.0, "p50_latency": 0.3, "p95_latency": 0.5,
            "p99_latency": 0.8, "error_rate": 0.01, "iteration_count": 1,
        }
        analytics.persist_run(exp_id, run_data)
        result = analytics.aggregate_metrics(exp_id)
        self.assertEqual(result["n_runs"], 1)

    def test_pr_db_isolation(self) -> None:
        config1 = PRDatabaseConfig(pr_number=104, test_mode=True)
        config2 = PRDatabaseConfig(pr_number=105, test_mode=True)
        p1 = PRDatabaseProvisioner(config1)
        p2 = PRDatabaseProvisioner(config2)
        r1 = p1.provision()
        r2 = p2.provision()
        p1.activate(r1.db_id)
        p2.activate(r2.db_id)
        m1 = p1.get_manager(r1.db_id)
        m2 = p2.get_manager(r2.db_id)
        self.assertNotEqual(m1.db.db_path, m2.db.db_path)

    def test_pr_db_cleanup_preserves_other(self) -> None:
        config1 = PRDatabaseConfig(pr_number=104, test_mode=True)
        config2 = PRDatabaseConfig(pr_number=105, test_mode=True)
        p1 = PRDatabaseProvisioner(config1)
        p2 = PRDatabaseProvisioner(config2)
        r1 = p1.provision()
        r2 = p2.provision()
        p1.activate(r1.db_id)
        p2.activate(r2.db_id)
        p1.cleanup(r1.db_id)
        self.assertEqual(p1.get_status(r1.db_id)["state"], PRDBState.CLEANED.value)
        health2 = p2.health_check(r2.db_id)
        self.assertTrue(health2["healthy"])
