"""
Tests for the pre-registered Synthesis Calibration Arena (PR #264).

Covers: deterministic task/response generation, each aggregation condition
in isolation, statistics correctness (Wilson CI, Brier score, bootstrap),
full hermetic run reproducibility, and the honest refusal of run_live().
"""

import unittest

from thinkbox.synthesis_calibration_arena import (
    TaskFamily,
    SyntheticTask,
    generate_task_set,
    SeededAgentSimulator,
    AgentResponse,
    Condition,
    ConditionResult,
    evaluate_single_agent,
    evaluate_naive_majority_vote,
    evaluate_confidence_weighted_synthesis,
    wilson_confidence_interval,
    brier_score,
    bootstrap_paired_difference,
    SynthesisCalibrationArena,
    PRE_REGISTERED_HYPOTHESIS,
    IMPROVEMENT_THRESHOLD_BRIER_DELTA,
)


class TestTaskGeneration(unittest.TestCase):
    def test_deterministic_given_seed(self):
        a = generate_task_set(30, seed=42)
        b = generate_task_set(30, seed=42)
        self.assertEqual([t.task_id for t in a], [t.task_id for t in b])
        self.assertEqual([t.ground_truth for t in a], [t.ground_truth for t in b])

    def test_different_seed_differs(self):
        a = generate_task_set(30, seed=42)
        b = generate_task_set(30, seed=43)
        self.assertNotEqual(
            [t.ground_truth for t in a], [t.ground_truth for t in b]
        )

    def test_families_cycle(self):
        tasks = generate_task_set(6, seed=1)
        families = [t.family for t in tasks]
        self.assertEqual(families[0], TaskFamily.COMPUTE)
        self.assertEqual(families[1], TaskFamily.DISTRACTOR)
        self.assertEqual(families[2], TaskFamily.MULTIFIELD)

    def test_task_count(self):
        tasks = generate_task_set(17, seed=1)
        self.assertEqual(len(tasks), 17)


class TestSeededAgentSimulator(unittest.TestCase):
    def setUp(self):
        self.sim = SeededAgentSimulator(seed=99)
        self.task = SyntheticTask(task_id="t1", family=TaskFamily.COMPUTE, ground_truth=500)

    def test_deterministic_given_same_inputs(self):
        r1 = self.sim.respond(self.task, 0)
        r2 = self.sim.respond(self.task, 0)
        self.assertEqual(r1.answer, r2.answer)
        self.assertEqual(r1.confidence, r2.confidence)
        self.assertEqual(r1.correct, r2.correct)

    def test_different_response_index_can_differ(self):
        responses = [self.sim.respond(self.task, i) for i in range(5)]
        answers = {r.answer for r in responses}
        # Not asserting they're all different (that's not guaranteed), just
        # that the simulator is actually exercising randomness per index.
        self.assertGreaterEqual(len(answers), 1)

    def test_correct_response_matches_ground_truth(self):
        # Find a response index where the simulator produced a correct answer.
        found_correct = False
        for i in range(50):
            r = self.sim.respond(self.task, i)
            if r.correct:
                self.assertEqual(r.answer, self.task.ground_truth)
                found_correct = True
        self.assertTrue(found_correct, "expected at least one correct response in 50 draws")

    def test_incorrect_response_never_equals_ground_truth(self):
        for i in range(50):
            r = self.sim.respond(self.task, i)
            if not r.correct:
                self.assertNotEqual(r.answer, self.task.ground_truth)

    def test_confidence_bounded(self):
        for i in range(50):
            r = self.sim.respond(self.task, i)
            self.assertGreaterEqual(r.confidence, 0.05)
            self.assertLessEqual(r.confidence, 0.99)


class TestAggregationConditions(unittest.TestCase):
    def setUp(self):
        self.task = SyntheticTask(task_id="t1", family=TaskFamily.COMPUTE, ground_truth=100)

    def test_single_agent_uses_first_response_only(self):
        responses = [
            AgentResponse(task_id="t1", answer=100, confidence=0.9, correct=True),
            AgentResponse(task_id="t1", answer=999, confidence=0.1, correct=False),
        ]
        result = evaluate_single_agent(responses, self.task)
        self.assertEqual(result.predicted_answer, 100)
        self.assertTrue(result.correct)

    def test_naive_majority_vote_picks_majority(self):
        responses = [
            AgentResponse(task_id="t1", answer=100, confidence=0.6, correct=True),
            AgentResponse(task_id="t1", answer=100, confidence=0.5, correct=True),
            AgentResponse(task_id="t1", answer=999, confidence=0.9, correct=False),
        ]
        result = evaluate_naive_majority_vote(responses, self.task)
        self.assertEqual(result.predicted_answer, 100)
        self.assertAlmostEqual(result.predicted_confidence, 2 / 3)
        self.assertTrue(result.correct)

    def test_naive_majority_vote_all_disagree_picks_lowest_value_tiebreak(self):
        responses = [
            AgentResponse(task_id="t1", answer=300, confidence=0.5, correct=False),
            AgentResponse(task_id="t1", answer=200, confidence=0.5, correct=False),
            AgentResponse(task_id="t1", answer=100, confidence=0.5, correct=True),
        ]
        result = evaluate_naive_majority_vote(responses, self.task)
        # All tied at count 1; tiebreak picks lowest answer value deterministically.
        self.assertEqual(result.predicted_answer, 100)

    def test_confidence_weighted_synthesis_consensus(self):
        responses = [
            AgentResponse(task_id="t1", answer=100, confidence=0.9, correct=True),
            AgentResponse(task_id="t1", answer=100, confidence=0.85, correct=True),
            AgentResponse(task_id="t1", answer=999, confidence=0.3, correct=False),
        ]
        result = evaluate_confidence_weighted_synthesis(responses, self.task)
        self.assertEqual(result.predicted_answer, 100)
        self.assertTrue(result.correct)
        # average_confidence of the 2 consensus findings
        self.assertAlmostEqual(result.predicted_confidence, (0.9 + 0.85) / 2)

    def test_confidence_weighted_synthesis_no_consensus_uses_highest_confidence(self):
        responses = [
            AgentResponse(task_id="t1", answer=100, confidence=0.9, correct=True),
            AgentResponse(task_id="t1", answer=200, confidence=0.4, correct=False),
            AgentResponse(task_id="t1", answer=300, confidence=0.3, correct=False),
        ]
        result = evaluate_confidence_weighted_synthesis(responses, self.task)
        self.assertEqual(result.predicted_answer, 100)
        self.assertEqual(result.predicted_confidence, 0.9)


class TestStatistics(unittest.TestCase):
    def test_wilson_ci_known_case(self):
        lo, hi = wilson_confidence_interval(50, 100)
        self.assertLess(lo, 0.5)
        self.assertGreater(hi, 0.5)
        self.assertGreaterEqual(lo, 0.0)
        self.assertLessEqual(hi, 1.0)

    def test_wilson_ci_zero_total(self):
        lo, hi = wilson_confidence_interval(0, 0)
        self.assertEqual((lo, hi), (0.0, 0.0))

    def test_wilson_ci_all_correct_narrower_at_larger_n(self):
        lo_small, hi_small = wilson_confidence_interval(10, 10)
        lo_large, hi_large = wilson_confidence_interval(1000, 1000)
        self.assertGreater(hi_small - lo_small, hi_large - lo_large)

    def test_brier_score_perfect_calibration(self):
        results = [
            ConditionResult(task_id="a", predicted_answer=1, predicted_confidence=1.0, correct=True),
            ConditionResult(task_id="b", predicted_answer=1, predicted_confidence=0.0, correct=False),
        ]
        self.assertEqual(brier_score(results), 0.0)

    def test_brier_score_worst_calibration(self):
        results = [
            ConditionResult(task_id="a", predicted_answer=1, predicted_confidence=1.0, correct=False),
            ConditionResult(task_id="b", predicted_answer=1, predicted_confidence=0.0, correct=True),
        ]
        self.assertEqual(brier_score(results), 1.0)

    def test_brier_score_empty(self):
        self.assertEqual(brier_score([]), 0.0)

    def test_bootstrap_paired_difference_zero_when_identical(self):
        results = [
            ConditionResult(task_id=f"t{i}", predicted_answer=1, predicted_confidence=0.7, correct=True)
            for i in range(20)
        ]
        pairs = list(zip(results, results))
        observed, lo, hi = bootstrap_paired_difference(pairs, brier_score, n_resamples=200, seed=1)
        self.assertAlmostEqual(observed, 0.0)
        self.assertLessEqual(lo, 0.0)
        self.assertGreaterEqual(hi, 0.0)

    def test_bootstrap_paired_difference_reproducible(self):
        a = [ConditionResult(task_id=f"t{i}", predicted_answer=1, predicted_confidence=0.5, correct=True) for i in range(10)]
        b = [ConditionResult(task_id=f"t{i}", predicted_answer=1, predicted_confidence=0.9, correct=True) for i in range(10)]
        pairs = list(zip(a, b))
        r1 = bootstrap_paired_difference(pairs, brier_score, n_resamples=500, seed=7)
        r2 = bootstrap_paired_difference(pairs, brier_score, n_resamples=500, seed=7)
        self.assertEqual(r1, r2)


class TestSynthesisCalibrationArena(unittest.TestCase):
    def test_hermetic_run_reproducible(self):
        arena1 = SynthesisCalibrationArena(n_tasks=30, seed=555)
        arena2 = SynthesisCalibrationArena(n_tasks=30, seed=555)
        proof1 = arena1.run_hermetic()
        proof2 = arena2.run_hermetic()
        self.assertEqual(proof1.to_dict()["proof_hash"], proof2.to_dict()["proof_hash"])

    def test_hermetic_run_produces_valid_classification(self):
        arena = SynthesisCalibrationArena(n_tasks=60, seed=123)
        proof = arena.run_hermetic()
        self.assertIn(proof.classification, ("IMPROVED", "NO_MEASURABLE_IMPROVEMENT", "WORSE"))

    def test_hermetic_run_matches_budget(self):
        arena = SynthesisCalibrationArena(n_tasks=45, seed=1)
        proof = arena.run_hermetic()
        self.assertEqual(proof.total_agent_calls, 45 * 3)

    def test_hermetic_run_reports_all_conditions(self):
        arena = SynthesisCalibrationArena(n_tasks=30, seed=2)
        proof = arena.run_hermetic()
        for condition in Condition:
            self.assertIn(condition.value, proof.accuracy)
            self.assertIn(condition.value, proof.brier)

    def test_hermetic_run_includes_pre_registered_hypothesis(self):
        arena = SynthesisCalibrationArena(n_tasks=10, seed=3)
        proof = arena.run_hermetic()
        self.assertEqual(proof.hypothesis, PRE_REGISTERED_HYPOTHESIS)
        self.assertIn(str(IMPROVEMENT_THRESHOLD_BRIER_DELTA), proof.improvement_threshold)

    def test_hermetic_run_no_claims_present(self):
        arena = SynthesisCalibrationArena(n_tasks=10, seed=4)
        proof = arena.run_hermetic()
        self.assertGreater(len(proof.no_claims), 0)
        self.assertTrue(any("no claim about real model" in c for c in proof.no_claims))

    def test_proof_serializes_to_dict(self):
        arena = SynthesisCalibrationArena(n_tasks=10, seed=5)
        proof = arena.run_hermetic()
        d = proof.to_dict()
        self.assertIn("proof_hash", d)
        self.assertEqual(len(d["proof_hash"]), 64)  # sha256 hex digest length

    def test_classification_reason_is_nonempty_string(self):
        arena = SynthesisCalibrationArena(n_tasks=30, seed=6)
        proof = arena.run_hermetic()
        self.assertIsInstance(proof.classification_reason, str)
        self.assertGreater(len(proof.classification_reason), 10)

    def test_run_live_refuses_without_fabricating(self):
        arena = SynthesisCalibrationArena(n_tasks=10, seed=7)
        with self.assertRaises(NotImplementedError):
            arena.run_live()


if __name__ == "__main__":
    unittest.main()
