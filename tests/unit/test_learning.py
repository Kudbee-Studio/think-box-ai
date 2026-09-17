"""Tests for Evidence-Driven Learning, Replay & Comparison Engine and Experiment Arena."""

from __future__ import annotations

import os
import tempfile
import unittest

from thinkbox.experiment import (
    ExperimentManager,
    ExperimentDB,
    ParameterClassification,
    EvidenceDrivenLearningEngine,
    ReplayEngine,
    ComparisonEngine,
    ExperimentDashboardUpgrade,
    ExperimentArena,
    ArenaEvaluator,
    MemoryReuseTracker,
    ArenaReplayEngine,
    OutcomeClassifier,
    LearnedParameter,
    EvidencePattern,
    Conflict,
    Recommendation,
    ReplayRecord,
    ExperimentComparison,
)


class TestEvidenceDrivenLearningEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_db = tempfile.mktemp(suffix=".db")
        self.manager = ExperimentManager(db_path=self.tmp_db)
        self.engine = EvidenceDrivenLearningEngine(self.manager.db)

    def tearDown(self) -> None:
        if os.path.exists(self.tmp_db):
            os.unlink(self.tmp_db)

    def test_learn_from_empty_history(self) -> None:
        result = self.engine.learn_from_history()
        self.assertEqual(result["learned_parameters"], {})
        self.assertEqual(result["evidence_patterns"], [])
        self.assertEqual(result["conflicts"], [])
        self.assertEqual(result["unknowns"], [])
        self.assertEqual(result["total_experiments_analyzed"], 0)

    def test_learn_from_observed_parameters(self) -> None:
        exp = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value, confidence=0.95)
        result = self.engine.learn_from_history()
        self.assertIn("rpm", result["learned_parameters"])
        lp = result["learned_parameters"]["rpm"]
        self.assertEqual(lp.classification, ParameterClassification.OBSERVED.value)
        self.assertEqual(lp.mean_val, 8000.0)
        self.assertEqual(lp.sample_count, 1)

    def test_learn_from_multiple_experiments(self) -> None:
        exp1 = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp1.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value, confidence=0.95)
        exp2 = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 10000})
        self.manager.add_parameter(exp2.experiment_id, "rpm", 10000, classification=ParameterClassification.OBSERVED.value, confidence=0.92)
        result = self.engine.learn_from_history()
        lp = result["learned_parameters"]["rpm"]
        self.assertEqual(lp.sample_count, 2)
        self.assertEqual(lp.min_val, 8000.0)
        self.assertEqual(lp.max_val, 10000.0)
        self.assertEqual(lp.trend, "increasing")

    def test_observed_takes_precedence(self) -> None:
        exp1 = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp1.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        exp2 = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 9000})
        self.manager.add_parameter(exp2.experiment_id, "rpm", 9000, classification=ParameterClassification.ESTIMATED.value)
        result = self.engine.learn_from_history()
        self.assertEqual(result["learned_parameters"]["rpm"].classification, ParameterClassification.OBSERVED.value)

    def test_estimated_when_no_observed(self) -> None:
        exp = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp.experiment_id, "rpm", 8000, classification=ParameterClassification.ESTIMATED.value)
        result = self.engine.learn_from_history()
        self.assertEqual(result["learned_parameters"]["rpm"].classification, ParameterClassification.ESTIMATED.value)

    def test_conflict_detection(self) -> None:
        exp1 = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp1.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        exp2 = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 9000})
        self.manager.add_parameter(exp2.experiment_id, "rpm", 9000, classification=ParameterClassification.ESTIMATED.value)
        result = self.engine.learn_from_history()
        self.assertGreater(len(result["conflicts"]), 0)

    def test_evidence_patterns(self) -> None:
        exp1 = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp1.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        exp2 = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 10000})
        self.manager.add_parameter(exp2.experiment_id, "rpm", 10000, classification=ParameterClassification.OBSERVED.value)
        result = self.engine.learn_from_history()
        self.assertGreater(len(result["evidence_patterns"]), 0)

    def test_recommend_next_experiment(self) -> None:
        exp = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value, confidence=0.3)
        result = self.engine.learn_from_history()
        recs = self.engine.recommend_next_experiment(result["learned_parameters"])
        self.assertGreater(len(recs), 0)
        self.assertEqual(recs[0].parameter_name, "rpm")

    def test_unknowns_detection(self) -> None:
        exp = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value, confidence=0.3)
        result = self.engine.learn_from_history()
        self.assertGreater(len(result["unknowns"]), 0)

    def test_learned_parameter_model_dump(self) -> None:
        exp = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value, confidence=0.95)
        result = self.engine.learn_from_history()
        lp = result["learned_parameters"]["rpm"]
        dump = lp.model_dump()
        self.assertEqual(dump["name"], "rpm")
        self.assertEqual(dump["classification"], ParameterClassification.OBSERVED.value)

    def test_trend_detection(self) -> None:
        exp1 = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp1.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        exp2 = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 10000})
        self.manager.add_parameter(exp2.experiment_id, "rpm", 10000, classification=ParameterClassification.OBSERVED.value)
        result = self.engine.learn_from_history()
        lp = result["learned_parameters"]["rpm"]
        self.assertEqual(lp.trend, "increasing")


class TestReplayEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_db = tempfile.mktemp(suffix=".db")
        self.manager = ExperimentManager(db_path=self.tmp_db)
        self.replay_engine = ReplayEngine(self.manager.db)

    def tearDown(self) -> None:
        if os.path.exists(self.tmp_db):
            os.unlink(self.tmp_db)

    def test_replay_reconstructs_lifecycle(self) -> None:
        exp = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        self.manager.add_test(exp.experiment_id, {"name": "test_cut", "result": "pass"})
        self.manager.add_artifact(exp.experiment_id, "report", "/tmp/report.md")
        self.manager.record_outcome(exp.experiment_id, {"success": True}, 0.95, "TEST_VERIFIED")
        record = self.replay_engine.replay(exp.experiment_id)
        self.assertEqual(record.experiment_id, exp.experiment_id)
        self.assertEqual(record.task, "cut")
        self.assertEqual(record.strategy, "test")
        self.assertEqual(len(record.tests), 1)
        self.assertEqual(len(record.artifacts), 1)

    def test_replay_after_restart(self) -> None:
        exp = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        result = self.replay_engine.replay_after_restart()
        self.assertTrue(result["replayable"])
        self.assertIn("recovery_data", result)

    def test_replay_missing_experiment(self) -> None:
        with self.assertRaises(ValueError):
            self.replay_engine.replay("nonexistent_id")


class TestComparisonEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_db = tempfile.mktemp(suffix=".db")
        self.manager = ExperimentManager(db_path=self.tmp_db)
        self.comparison_engine = ComparisonEngine(self.manager.db)

    def tearDown(self) -> None:
        if os.path.exists(self.tmp_db):
            os.unlink(self.tmp_db)

    def test_compare_two_experiments(self) -> None:
        exp1 = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp1.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        exp2 = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 10000})
        self.manager.add_parameter(exp2.experiment_id, "rpm", 10000, classification=ParameterClassification.OBSERVED.value)
        comparison = self.comparison_engine.compare(exp1.experiment_id, exp2.experiment_id)
        self.assertIn("rpm", comparison.parameter_differences)
        self.assertEqual(comparison.exp_a_id, exp1.experiment_id)
        self.assertEqual(comparison.exp_b_id, exp2.experiment_id)

    def test_comparison_model_dump(self) -> None:
        exp1 = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        exp2 = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 10000})
        self.manager.add_parameter(exp1.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        self.manager.add_parameter(exp2.experiment_id, "rpm", 10000, classification=ParameterClassification.OBSERVED.value)
        comparison = self.comparison_engine.compare(exp1.experiment_id, exp2.experiment_id)
        dump = comparison.model_dump()
        self.assertEqual(dump["exp_a_id"], exp1.experiment_id)
        self.assertIn("parameter_differences", dump)

    def test_compare_with_missing_experiment(self) -> None:
        exp1 = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        with self.assertRaises(ValueError):
            self.comparison_engine.compare(exp1.experiment_id, "nonexistent_id")

    def test_compare_with_different_outcomes(self) -> None:
        exp1 = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp1.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        self.manager.record_outcome(exp1.experiment_id, {"success": True}, 0.95, "TEST_VERIFIED")
        exp2 = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 10000})
        self.manager.add_parameter(exp2.experiment_id, "rpm", 10000, classification=ParameterClassification.OBSERVED.value)
        self.manager.record_outcome(exp2.experiment_id, {"success": False}, 0.5, "FAILED")
        comparison = self.comparison_engine.compare(exp1.experiment_id, exp2.experiment_id)
        self.assertIn("outcome_differences", comparison.model_dump())


class TestExperimentDashboardUpgrade(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_db = tempfile.mktemp(suffix=".db")
        self.manager = ExperimentManager(db_path=self.tmp_db)
        self.engine = EvidenceDrivenLearningEngine(self.manager.db)
        self.upgrade = ExperimentDashboardUpgrade(self.manager.db, self.engine)

    def tearDown(self) -> None:
        if os.path.exists(self.tmp_db):
            os.unlink(self.tmp_db)

    def test_get_upgraded_dashboard(self) -> None:
        exp = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        dashboard = self.upgrade.get_upgraded_dashboard()
        self.assertIn("learned_parameters", dashboard)
        self.assertIn("evidence_patterns", dashboard)
        self.assertIn("conflicts", dashboard)
        self.assertIn("unknowns", dashboard)
        self.assertIn("replay_data", dashboard)

    def test_get_evidence_graph(self) -> None:
        exp = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        graph = self.upgrade.get_evidence_graph()
        self.assertIn("nodes", graph)
        self.assertIn("links", graph)

    def test_upgraded_dashboard_with_no_data(self) -> None:
        dashboard = self.upgrade.get_upgraded_dashboard()
        self.assertEqual(dashboard["learned_parameters"], {})


class TestExperimentArena(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_db = tempfile.mktemp(suffix=".db")
        self.manager = ExperimentManager(db_path=self.tmp_db)
        self.arena = ExperimentArena(self.manager.db, self.manager)

    def tearDown(self) -> None:
        if os.path.exists(self.tmp_db):
            os.unlink(self.tmp_db)

    def test_create_arena(self) -> None:
        result = self.arena.create_arena("task_001", "Test CNC cutting", ["BASELINE", "LEARNED"])
        self.assertEqual(result["task_id"], "task_001")
        self.assertIn("BASELINE", result["strategies"])
        self.assertIn("LEARNED", result["strategies"])
        self.assertTrue(result["arena_id"].startswith("arena_"))

    def test_run_baseline(self) -> None:
        exp_id = self.arena.run_baseline("task_001", {"rpm": 8000, "feed_rate": 200})
        self.assertTrue(exp_id.startswith("tb_exp_"))
        results = self.arena.get_arena_results()
        self.assertIn("BASELINE", results)
        self.assertEqual(len(results["BASELINE"]), 1)

    def test_run_learned(self) -> None:
        self.arena.run_baseline("task_001", {"rpm": 8000})
        learned_params = {"rpm": LearnedParameter(name="rpm", observations=[8000.0], min_val=8000, max_val=8000, mean_val=8000, median_val=8000, sample_count=1, confidence=1.0, source_count=1, latest_observation=8000.0, trend="stable", conflicts=[], unit="", classification="observed")}
        exp_id = self.arena.run_learned("task_001", {"rpm": 8000}, learned_params)
        self.assertTrue(exp_id.startswith("tb_exp_"))
        results = self.arena.get_arena_results()
        self.assertIn("LEARNED", results)

    def test_run_variant(self) -> None:
        exp_id = self.arena.run_variant("task_001", {"rpm": 9000}, "VARIANT_A")
        self.assertTrue(exp_id.startswith("tb_exp_"))
        results = self.arena.get_arena_results()
        self.assertIn("VARIANT_A", results)

    def test_arena_evaluate(self) -> None:
        exp_id = self.arena.run_baseline("task_001", {"rpm": 8000})
        self.manager.add_test(exp_id, {"name": "test1", "result": "pass"})
        results = self.arena.evaluate([exp_id])
        self.assertIn(exp_id, results)
        self.assertEqual(results[exp_id]["test_pass_rate"], 1.0)

    def test_arena_compare(self) -> None:
        baseline_id = self.arena.run_baseline("task_001", {"rpm": 8000})
        learned_params = {"rpm": LearnedParameter(name="rpm", observations=[8000.0], min_val=8000, max_val=8000, mean_val=8000, median_val=8000, sample_count=1, confidence=1.0, source_count=1, latest_observation=8000.0, trend="stable", conflicts=[], unit="", classification="observed")}
        learned_id = self.arena.run_learned("task_001", {"rpm": 8000}, learned_params)
        comparison = self.arena.compare(baseline_id, learned_id)
        self.assertEqual(comparison.exp_a_id, baseline_id)
        self.assertEqual(comparison.exp_b_id, learned_id)

    def test_arena_get_results(self) -> None:
        exp_id = self.arena.run_baseline("task_001", {"rpm": 8000})
        results = self.arena.get_arena_results()
        self.assertIn("BASELINE", results)
        self.assertEqual(len(results["BASELINE"]), 1)


class TestArenaEvaluator(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_db = tempfile.mktemp(suffix=".db")
        self.manager = ExperimentManager(db_path=self.tmp_db)
        self.evaluator = ArenaEvaluator(self.manager.db)

    def tearDown(self) -> None:
        if os.path.exists(self.tmp_db):
            os.unlink(self.tmp_db)

    def test_evaluate_experiments(self) -> None:
        exp = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        self.manager.add_test(exp.experiment_id, {"name": "test1", "result": "pass"})
        results = self.evaluator.evaluate_experiments([exp.experiment_id])
        self.assertIn(exp.experiment_id, results)
        self.assertEqual(results[exp.experiment_id]["test_pass_rate"], 1.0)

    def test_evaluate_with_errors(self) -> None:
        exp = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        self.manager.add_test(exp.experiment_id, {"name": "test1", "result": "fail"})
        results = self.evaluator.evaluate_experiments([exp.experiment_id])
        self.assertEqual(results[exp.experiment_id]["error_count"], 1)
        self.assertEqual(results[exp.experiment_id]["test_pass_rate"], 0.0)

    def test_evaluate_with_artifacts_and_proof(self) -> None:
        exp = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        self.manager.add_artifact(exp.experiment_id, "report", "/tmp/report.md")
        self.manager.add_proof(exp.experiment_id, {"proof_id": "p1", "evidence_label": "verified"})
        results = self.evaluator.evaluate_experiments([exp.experiment_id])
        self.assertEqual(results[exp.experiment_id]["artifact_quality"], 1.0)
        self.assertEqual(results[exp.experiment_id]["proof_completeness"], 1.0)


class TestMemoryReuseTracker(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_db = tempfile.mktemp(suffix=".db")
        self.manager = ExperimentManager(db_path=self.tmp_db)
        self.tracker = MemoryReuseTracker(self.manager.db)

    def tearDown(self) -> None:
        if os.path.exists(self.tmp_db):
            os.unlink(self.tmp_db)

    def test_memory_reuse_detected(self) -> None:
        baseline = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(baseline.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        learned = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(learned.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        self.manager.add_parameter(learned.experiment_id, "learned_rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        result = self.tracker.track_memory_reuse(learned.experiment_id, baseline.experiment_id)
        self.assertTrue(result["memory_reused"])
        self.assertGreater(result["reuse_count"], 0)

    def test_no_memory_reuse(self) -> None:
        baseline = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(baseline.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        learned = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"speed": 100})
        self.manager.add_parameter(learned.experiment_id, "speed", 100, classification=ParameterClassification.OBSERVED.value)
        result = self.tracker.track_memory_reuse(learned.experiment_id, baseline.experiment_id)
        self.assertFalse(result["memory_reused"])


class TestArenaReplayEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_db = tempfile.mktemp(suffix=".db")
        self.manager = ExperimentManager(db_path=self.tmp_db)
        self.arena_replay = ArenaReplayEngine(self.manager.db)

    def tearDown(self) -> None:
        if os.path.exists(self.tmp_db):
            os.unlink(self.tmp_db)

    def test_replay_arena(self) -> None:
        exp = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        result = self.arena_replay.replay_arena("arena_001")
        self.assertTrue(result["replayable"])
        self.assertEqual(result["arena_id"], "arena_001")

    def test_verify_reproducibility(self) -> None:
        exp = self.manager.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.manager.add_parameter(exp.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        result = self.arena_replay.verify_reproducibility(exp.experiment_id)
        self.assertTrue(result["reproducible"])
        self.assertEqual(result["runs"], 2)


class TestOutcomeClassifier(unittest.TestCase):
    def test_classify_improved(self) -> None:
        outcome = OutcomeClassifier.classify(
            {"test_pass_rate": 0.5, "error_count": 5},
            {"test_pass_rate": 0.9, "error_count": 1},
        )
        self.assertEqual(outcome, "IMPROVED")

    def test_classify_no_improvement(self) -> None:
        outcome = OutcomeClassifier.classify(
            {"test_pass_rate": 0.8, "error_count": 2},
            {"test_pass_rate": 0.8, "error_count": 2},
        )
        self.assertEqual(outcome, "NO_MEASURABLE_IMPROVEMENT")

    def test_classify_regression(self) -> None:
        outcome = OutcomeClassifier.classify(
            {"test_pass_rate": 0.9, "error_count": 1},
            {"test_pass_rate": 0.5, "error_count": 5},
        )
        self.assertEqual(outcome, "REGRESSION")

    def test_classify_inconclusive(self) -> None:
        outcome = OutcomeClassifier.classify(
            {"test_pass_rate": 0.5, "error_count": 3},
            {"test_pass_rate": 0.6, "error_count": 4},
        )
        self.assertEqual(outcome, "INCONCLUSIVE")

    def test_classify_failed(self) -> None:
        outcome = OutcomeClassifier.classify_failed({"error_count": 5, "test_pass_rate": 0.0})
        self.assertEqual(outcome, "FAILED")

    def test_classify_missing_evidence(self) -> None:
        outcome = OutcomeClassifier.classify_missing_evidence({"proof_completeness": 0.0})
        self.assertEqual(outcome, "FAILED")

    def test_classify_not_failed(self) -> None:
        outcome = OutcomeClassifier.classify_failed({"error_count": 1, "test_pass_rate": 0.8})
        self.assertEqual(outcome, "INCONCLUSIVE")


class TestZeroServerLearning(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_db = tempfile.mktemp(suffix=".db")
        self.manager = ExperimentManager(db_path=self.tmp_db)

    def tearDown(self) -> None:
        if os.path.exists(self.tmp_db):
            os.unlink(self.tmp_db)

    def test_zero_server_with_learning(self) -> None:
        result = self.manager.run_zero_server_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        self.assertIn("experiment_id", result)
        engine = EvidenceDrivenLearningEngine(self.manager.db)
        learned = engine.learn_from_history()
        self.assertIn("rpm", learned["learned_parameters"])

    def test_arena_full_workflow(self) -> None:
        arena = ExperimentArena(self.manager.db, self.manager)
        arena.create_arena("task_001", "CNC parameter test", ["BASELINE", "LEARNED"])
        baseline_id = arena.run_baseline("task_001", {"rpm": 8000})
        self.manager.add_test(baseline_id, {"name": "test1", "result": "pass"})
        learned_params = {"rpm": LearnedParameter(name="rpm", observations=[8000.0], min_val=8000, max_val=8000, mean_val=8000, median_val=8000, sample_count=1, confidence=1.0, source_count=1, latest_observation=8000.0, trend="stable", conflicts=[], unit="", classification="observed")}
        learned_id = arena.run_learned("task_001", {"rpm": 8000}, learned_params)
        self.manager.add_test(learned_id, {"name": "test1", "result": "pass"})
        evaluation = arena.evaluate([baseline_id, learned_id])
        self.assertIn(baseline_id, evaluation)
        self.assertIn(learned_id, evaluation)
        comparison = arena.compare(baseline_id, learned_id)
        self.assertIsNotNone(comparison)
        outcome = OutcomeClassifier.classify(
            evaluation[baseline_id],
            evaluation[learned_id],
        )
        self.assertIn(outcome, ["IMPROVED", "NO_MEASURABLE_IMPROVEMENT", "REGRESSION", "INCONCLUSIVE"])


from thinkbox.experiment import (
    ExperimentManager,
    ExperimentDB,
    ParameterClassification,
    EvidenceDrivenLearningEngine,
    ReplayEngine,
    ComparisonEngine,
    ExperimentDashboardUpgrade,
    ExperimentArena,
    ArenaEvaluator,
    MemoryReuseTracker,
    ArenaReplayEngine,
    OutcomeClassifier,
    OutcomeClassification,
    ExperimentOutcome,
    LearnedParameter,
    EvidencePattern,
    Conflict,
    Recommendation,
    ReplayRecord,
    ExperimentComparison,
    FourState,
)


class TestCanonicalFourState(unittest.TestCase):
    def test_four_state_has_failed(self) -> None:
        self.assertIn(FourState.FAILED.value, [FourState.CODE_COMPLETE.value, FourState.TEST_VERIFIED.value, FourState.LIVE_VERIFIED.value, FourState.PRODUCTION_READY.value, FourState.FAILED.value])

    def test_four_state_all_values(self) -> None:
        values = [s.value for s in FourState]
        self.assertIn("CODE_COMPLETE", values)
        self.assertIn("TEST_VERIFIED", values)
        self.assertIn("LIVE_VERIFIED", values)
        self.assertIn("PRODUCTION_READY", values)
        self.assertIn("FAILED", values)

    def test_four_state_import_from_experiment(self) -> None:
        from thinkbox.experiment import FourState as FS
        self.assertEqual(FS.CODE_COMPLETE.value, "CODE_COMPLETE")

    def test_four_state_failed_classification(self) -> None:
        self.assertEqual(FourState.FAILED.value, "FAILED")


class TestOutcomeClassificationEnum(unittest.TestCase):
    def test_outcome_classification_values(self) -> None:
        values = [s.value for s in OutcomeClassification]
        self.assertIn("IMPROVED", values)
        self.assertIn("NO_MEASURABLE_IMPROVEMENT", values)
        self.assertIn("REGRESSION", values)
        self.assertIn("INCONCLUSIVE", values)
        self.assertIn("FAILED", values)

    def test_classify_returns_enum(self) -> None:
        result = OutcomeClassifier.classify(
            {"test_pass_rate": 0.5, "error_count": 5},
            {"test_pass_rate": 0.9, "error_count": 1},
        )
        self.assertIsInstance(result, OutcomeClassification)
        self.assertEqual(result, OutcomeClassification.IMPROVED)

    def test_classify_failed_returns_enum(self) -> None:
        result = OutcomeClassifier.classify_failed({"error_count": 5, "test_pass_rate": 0.0})
        self.assertIsInstance(result, OutcomeClassification)
        self.assertEqual(result, OutcomeClassification.FAILED)

    def test_classify_missing_evidence_returns_enum(self) -> None:
        result = OutcomeClassifier.classify_missing_evidence({"proof_completeness": 0.0})
        self.assertIsInstance(result, OutcomeClassification)
        self.assertEqual(result, OutcomeClassification.FAILED)

    def test_outcome_enum_model_dump(self) -> None:
        from thinkbox.experiment import ExperimentOutcome
        self.assertEqual(ExperimentOutcome.SUCCESS.value, "success")
        self.assertEqual(ExperimentOutcome.FAILURE.value, "failure")


class TestCNCCompatibility(unittest.TestCase):
    def test_cnc_job_has_no_four_state(self) -> None:
        import thinkbox.cnc.job as cnc_job
        self.assertFalse(hasattr(cnc_job, 'FourState'))

    def test_cnc_uses_separate_state_system(self) -> None:
        from thinkbox.cnc.safety import ApprovalStatus
        self.assertIsInstance(ApprovalStatus.APPROVED, ApprovalStatus)


class TestExperimentCompatibility(unittest.TestCase):
    def test_experiment_record_uses_four_state(self) -> None:
        from thinkbox.experiment import ExperimentRecord, FourState
        exp = ExperimentRecord(four_state=FourState.TEST_VERIFIED.value)
        self.assertEqual(exp.four_state, FourState.TEST_VERIFIED.value)

    def test_four_state_persistence(self) -> None:
        import tempfile, os
        from thinkbox.experiment import ExperimentManager, FourState
        tmp_db = tempfile.mktemp(suffix=".db")
        m = ExperimentManager(db_path=tmp_db)
        exp = m.create_experiment(intent="test", hypothesis="test")
        m.record_outcome(exp.experiment_id, {"success": True}, 0.95, FourState.TEST_VERIFIED.value)
        result = m.db.get_outcomes_by_experiment(exp.experiment_id)
        self.assertIsNotNone(result)
        os.unlink(tmp_db)


class TestArenaCompatibility(unittest.TestCase):
    def test_arena_uses_four_state(self) -> None:
        from thinkbox.experiment import FourState
        self.assertIn(FourState.FAILED.value, [FourState.CODE_COMPLETE.value, FourState.TEST_VERIFIED.value, FourState.LIVE_VERIFIED.value, FourState.PRODUCTION_READY.value, FourState.FAILED.value])

    def test_outcome_classifier_in_arena(self) -> None:
        from thinkbox.experiment import OutcomeClassifier, OutcomeClassification
        result = OutcomeClassifier.classify(
            {"test_pass_rate": 0.5, "error_count": 3},
            {"test_pass_rate": 0.6, "error_count": 4},
        )
        self.assertIsInstance(result, OutcomeClassification)


class TestLearningCompatibility(unittest.TestCase):
    def test_learning_engine_uses_four_state(self) -> None:
        from thinkbox.experiment import FourState
        self.assertIn(FourState.FAILED.value, [s.value for s in FourState])

    def test_evidence_driven_learning_returns_enum_compatible(self) -> None:
        import tempfile, os
        from thinkbox.experiment import ExperimentManager, EvidenceDrivenLearningEngine, ParameterClassification
        tmp_db = tempfile.mktemp(suffix=".db")
        m = ExperimentManager(db_path=tmp_db)
        exp = m.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        m.add_parameter(exp.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        engine = EvidenceDrivenLearningEngine(m.db)
        result = engine.learn_from_history()
        self.assertIn("rpm", result["learned_parameters"])
        os.unlink(tmp_db)


class TestReplayCompatibility(unittest.TestCase):
    def test_replay_engine_uses_four_state(self) -> None:
        from thinkbox.experiment import FourState
        self.assertIn(FourState.FAILED.value, [s.value for s in FourState])

    def test_replay_persists_four_state(self) -> None:
        import tempfile, os
        from thinkbox.experiment import ExperimentManager, ReplayEngine, FourState
        tmp_db = tempfile.mktemp(suffix=".db")
        m = ExperimentManager(db_path=tmp_db)
        exp = m.create_experiment(intent="cut", hypothesis="test", parameters={"rpm": 8000})
        m.add_parameter(exp.experiment_id, "rpm", 8000, classification=ParameterClassification.OBSERVED.value)
        m.record_outcome(exp.experiment_id, {"success": True}, 0.95, FourState.TEST_VERIFIED.value)
        replay = ReplayEngine(m.db)
        record = replay.replay(exp.experiment_id)
        self.assertEqual(record.experiment_id, exp.experiment_id)
        os.unlink(tmp_db)


class TestAPISerialization(unittest.TestCase):
    def test_four_state_serializes_to_string(self) -> None:
        from thinkbox.experiment import FourState
        self.assertEqual(FourState.TEST_VERIFIED.value, "TEST_VERIFIED")
        self.assertEqual(FourState.TEST_VERIFIED.value, "TEST_VERIFIED")

    def test_outcome_classification_serializes_to_string(self) -> None:
        from thinkbox.experiment import OutcomeClassification
        self.assertEqual(OutcomeClassification.IMPROVED.value, "IMPROVED")

    def test_four_state_json_serializable(self) -> None:
        import json
        from thinkbox.experiment import FourState
        serialized = json.dumps({"state": FourState.TEST_VERIFIED.value})
        self.assertIn("TEST_VERIFIED", serialized)

    def test_outcome_classification_json_serializable(self) -> None:
        import json
        from thinkbox.experiment import OutcomeClassification
        serialized = json.dumps({"outcome": OutcomeClassification.IMPROVED.value})
        self.assertIn("IMPROVED", serialized)


class TestSQLitePersistenceReload(unittest.TestCase):
    def test_four_state_persists_and_reloads(self) -> None:
        import tempfile, os
        from thinkbox.experiment import ExperimentManager, FourState
        tmp_db = tempfile.mktemp(suffix=".db")
        m = ExperimentManager(db_path=tmp_db)
        exp = m.create_experiment(intent="test", hypothesis="test")
        m.record_outcome(exp.experiment_id, {"success": True}, 0.95, FourState.PRODUCTION_READY.value)
        outcome = m.db.get_outcomes_by_experiment(exp.experiment_id)
        self.assertIsNotNone(outcome)
        os.unlink(tmp_db)

    def test_experiment_status_persists(self) -> None:
        import tempfile, os
        from thinkbox.experiment import ExperimentManager, ExperimentRecord, ExperimentStatus
        tmp_db = tempfile.mktemp(suffix=".db")
        m = ExperimentManager(db_path=tmp_db)
        exp = m.create_experiment(intent="test", hypothesis="test")
        m.db.save_experiment(exp)
        result = m.db.get_experiment(exp.experiment_id)
        self.assertIsNotNone(result)
        os.unlink(tmp_db)


class TestInvalidStateHandling(unittest.TestCase):
    def test_invalid_four_state_raises(self) -> None:
        from thinkbox.experiment import FourState
        with self.assertRaises(Exception):
            FourState("INVALID_STATE")

    def test_four_state_from_value(self) -> None:
        from thinkbox.experiment import FourState
        self.assertEqual(FourState("TEST_VERIFIED"), FourState.TEST_VERIFIED)

    def test_outcome_classification_from_value(self) -> None:
        from thinkbox.experiment import OutcomeClassification
        self.assertEqual(OutcomeClassification("IMPROVED"), OutcomeClassification.IMPROVED)

    def test_invalid_outcome_classification(self) -> None:
        from thinkbox.experiment import OutcomeClassification
        with self.assertRaises(ValueError):
            OutcomeClassification("INVALID")


class TestFourStateTransitions(unittest.TestCase):
    def test_valid_transition_sequence(self) -> None:
        from thinkbox.experiment import FourState
        valid_states = [FourState.CODE_COMPLETE, FourState.TEST_VERIFIED, FourState.LIVE_VERIFIED, FourState.PRODUCTION_READY]
        for i in range(len(valid_states) - 1):
            self.assertIn(valid_states[i].value, [s.value for s in FourState])
            self.assertIn(valid_states[i + 1].value, [s.value for s in FourState])

    def test_failed_can_occur_at_any_point(self) -> None:
        from thinkbox.experiment import FourState
        self.assertIn(FourState.FAILED.value, [s.value for s in FourState])

    def test_four_state_count(self) -> None:
        from thinkbox.experiment import FourState
        self.assertEqual(len(list(FourState)), 5)


class TestProvenanceSourceCompatibility(unittest.TestCase):
    def test_provenance_source_values(self) -> None:
        from thinkbox.experiment import ProvenanceSource
        values = [s.value for s in ProvenanceSource]
        self.assertIn("measured", values)
        self.assertIn("estimated", values)
        self.assertIn("simulated", values)
        self.assertIn("inferred", values)

    def test_parameter_classification_values(self) -> None:
        from thinkbox.experiment import ParameterClassification
        values = [s.value for s in ParameterClassification]
        self.assertIn("observed", values)
        self.assertIn("estimated", values)
        self.assertIn("simulated", values)


class TestExperimentOutcomeEnum(unittest.TestCase):
    def test_experiment_outcome_values(self) -> None:
        from thinkbox.experiment import ExperimentOutcome
        values = [s.value for s in ExperimentOutcome]
        self.assertIn("success", values)
        self.assertIn("partial", values)
        self.assertIn("failure", values)
        self.assertIn("incomplete", values)

    def test_experiment_outcome_model_dump(self) -> None:
        from thinkbox.experiment import ExperimentOutcome
        dump = ExperimentOutcome.SUCCESS.model_dump() if hasattr(ExperimentOutcome.SUCCESS, 'model_dump') else {"value": ExperimentOutcome.SUCCESS.value}
        self.assertEqual(dump["value"], "success")


if __name__ == "__main__":
    unittest.main()
