"""Unit tests for thinkbox.consensus — multi-model voting, confidence scoring, disagreement, ranking, audit."""

import unittest

from thinkbox.consensus import (
    ModelOutput,
    ConsensusResult,
    ConfidenceScorer,
    MultiModelVoting,
    DisagreementResolver,
    ModelRankingEngine,
    ConsensusAuditTrail,
)


class TestModelOutput(unittest.TestCase):
    def test_default(self) -> None:
        output = ModelOutput(model_id="gpt-4", output="hello")
        self.assertEqual(output.model_id, "gpt-4")
        self.assertEqual(output.output, "hello")
        self.assertEqual(output.confidence, 0.5)
        self.assertEqual(output.token_count, 0)


class TestConsensusResult(unittest.TestCase):
    def test_default_init(self) -> None:
        result = ConsensusResult(
            consensus_id="c1", task_id="t1",
            winning_output="ok", winning_model="model1",
            agreement_score=0.8, model_outputs=[],
        )
        self.assertEqual(result.consensus_id, "c1")
        self.assertEqual(result.task_id, "t1")
        self.assertEqual(result.agreement_score, 0.8)
        self.assertIsNotNone(result.timestamp)


class TestConfidenceScorer(unittest.TestCase):
    def test_bayes_confidence_high_quality(self) -> None:
        code_output = "def foo():\n    return 42\n"
        confidence = ConfidenceScorer.bayes_confidence(code_output, model_reliability=0.9)
        self.assertGreater(confidence, 0.7)
        self.assertLessEqual(confidence, 1.0)

    def test_bayes_confidence_low_reliability(self) -> None:
        output = "some text"
        confidence = ConfidenceScorer.bayes_confidence(output, model_reliability=0.1)
        self.assertLess(confidence, 0.5)

    def test_bayes_confidence_empty(self) -> None:
        confidence = ConfidenceScorer.bayes_confidence("", model_reliability=0.5)
        self.assertEqual(confidence, 0.5)

    def test_length_score_in_range(self) -> None:
        score = ConfidenceScorer.length_score("a" * 100, expected_range=(50, 200))
        self.assertEqual(score, 1.0)

    def test_length_score_too_short(self) -> None:
        score = ConfidenceScorer.length_score("hi", expected_range=(50, 200))
        self.assertLess(score, 1.0)
        self.assertGreater(score, 0.0)

    def test_length_score_too_long(self) -> None:
        score = ConfidenceScorer.length_score("a" * 5000, expected_range=(50, 200))
        self.assertLess(score, 1.0)


class TestMultiModelVoting(unittest.TestCase):
    def setUp(self) -> None:
        self.voter = MultiModelVoting()

    def test_register_model(self) -> None:
        self.voter.register_model("model1", reliability=0.85)

    def test_vote_empty(self) -> None:
        result = self.voter.vote("task1", [])
        self.assertEqual(result.method, "no_outputs")
        self.assertEqual(result.agreement_score, 0.0)
        self.assertEqual(result.winning_model, "none")

    def test_vote_single(self) -> None:
        output = ModelOutput(model_id="m1", output="hello world", confidence=0.7)
        result = self.voter.vote("task1", [output])
        self.assertEqual(result.method, "single_model")
        self.assertEqual(result.agreement_score, 1.0)
        self.assertEqual(result.winning_model, "m1")

    def test_vote_multiple(self) -> None:
        # Register different reliabilities to get different confidences
        self.voter.register_model("m1", reliability=0.6)
        self.voter.register_model("m2", reliability=0.9)
        outputs = [
            ModelOutput(model_id="m1", output="answer A", confidence=0.0),
            ModelOutput(model_id="m2", output="answer B", confidence=0.0),
        ]
        result = self.voter.vote("task1", outputs)
        self.assertEqual(result.method, "weighted_vote")
        self.assertEqual(result.winning_model, "m2")
        self.assertGreater(result.agreement_score, 0.0)

    def test_vote_assigns_confidence(self) -> None:
        # Use multiple outputs to trigger confidence assignment (single-model returns early)
        outputs = [
            ModelOutput(model_id="m1", output="def foo():\n    return 42\n", confidence=0.0),
            ModelOutput(model_id="m2", output="print('hello')", confidence=0.0),
        ]
        self.voter.register_model("m1", reliability=0.9)
        self.voter.register_model("m2", reliability=0.8)
        result = self.voter.vote("task1", outputs)
        for out in result.model_outputs:
            self.assertGreater(out.confidence, 0.0)


class TestDisagreementResolver(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = DisagreementResolver(consensus_threshold=0.6)

    def test_accept_high_agreement(self) -> None:
        result = ConsensusResult(
            consensus_id="c1", task_id="t1", winning_output="ok",
            winning_model="m1", agreement_score=0.9, model_outputs=[],
        )
        decision, output = self.resolver.resolve(result)
        self.assertEqual(decision, "accepted")
        self.assertEqual(output, "ok")

    def test_escalate_low_agreement(self) -> None:
        result = ConsensusResult(
            consensus_id="c1", task_id="t1", winning_output="ok",
            winning_model="m1", agreement_score=0.2, model_outputs=[],
        )
        decision, output = self.resolver.resolve(result)
        self.assertEqual(decision, "escalate")

    def test_caution_medium_agreement(self) -> None:
        result = ConsensusResult(
            consensus_id="c1", task_id="t1", winning_output="ok",
            winning_model="m1", agreement_score=0.5,
            model_outputs=[ModelOutput(model_id="m1", output="ok", confidence=0.5)],
        )
        decision, output = self.resolver.resolve(result)
        self.assertEqual(decision, "accepted_with_caution")
        decision, output = self.resolver.resolve(result)
        self.assertEqual(decision, "accepted_with_caution")

    def test_invalid_threshold(self) -> None:
        with self.assertRaises(ValueError):
            DisagreementResolver(consensus_threshold=1.5)


class TestModelRankingEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = ModelRankingEngine()

    def test_record_result(self) -> None:
        self.engine.record_result("m1", "coding", True, 100.0, quality=0.8)
        ranking = self.engine.get_ranking("coding")
        self.assertEqual(len(ranking), 0)

    def test_ranking_requires_min_tasks(self) -> None:
        for i in range(5):
            self.engine.record_result("m1", "coding", True, 100.0, quality=0.8)
        ranking = self.engine.get_ranking("coding")
        self.assertEqual(len(ranking), 1)
        self.assertEqual(ranking[0][0], "m1")

    def test_get_best_model(self) -> None:
        for i in range(5):
            self.engine.record_result("m1", "coding", True, 100.0, quality=0.8)
            self.engine.record_result("m2", "coding", True, 200.0, quality=0.6)
        best = self.engine.get_best_model("coding")
        self.assertEqual(best, "m1")

    def test_empty_ranking(self) -> None:
        self.assertEqual(self.engine.get_ranking("nonexistent"), [])
        self.assertIsNone(self.engine.get_best_model("nonexistent"))


class TestConsensusAuditTrail(unittest.TestCase):
    def setUp(self) -> None:
        self.trail = ConsensusAuditTrail()

    def test_record(self) -> None:
        result = ConsensusResult(
            consensus_id="c1", task_id="t1", winning_output="ok",
            winning_model="m1", agreement_score=0.8, model_outputs=[],
        )
        hash_val = self.trail.record(result)
        self.assertIsNotNone(hash_val)
        self.assertEqual(len(hash_val), 16)

    def test_get_trail(self) -> None:
        result = ConsensusResult(
            consensus_id="c1", task_id="t1", winning_output="ok",
            winning_model="m1", agreement_score=0.8, model_outputs=[],
        )
        self.trail.record(result)
        records = self.trail.get_trail()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["consensus_id"], "c1")