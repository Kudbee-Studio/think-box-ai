"""Unit tests for thinkbox/grounding.py — deterministic grounding scorer."""

import unittest

from thinkbox.grounding import GroundingScorer


class TestGroundingScorer(unittest.TestCase):
    def test_no_evidence_scores_zero(self):
        scorer = GroundingScorer()
        result = scorer.score("The answer is 4", None, reasoning="because")
        self.assertEqual(result.score, 0.0)
        self.assertFalse(result.evidence_present)

    def test_full_overlap_scores_high(self):
        scorer = GroundingScorer()
        result = scorer.score(
            "Paris is the capital of France",
            "fact_geo: Paris is the capital of France",
            reasoning="direct lookup",
        )
        self.assertGreaterEqual(result.score, 0.8)
        self.assertIn("paris", result.matched_terms)

    def test_numeric_facts_retained(self):
        scorer = GroundingScorer()
        result = scorer.score("2+2=4", "fact_arith: 2+2=4", reasoning="arithmetic")
        self.assertGreaterEqual(result.score, 0.9)
        self.assertEqual(result.numeric_ratio, 1.0)

    def test_evidence_without_overlap_scores_low(self):
        scorer = GroundingScorer()
        result = scorer.score("Paris is the capital", "fact: bananas are yellow")
        self.assertLess(result.score, 0.5)

    def test_reasoning_alone_not_grounded(self):
        scorer = GroundingScorer()
        result = scorer.score("claim", None, reasoning="lots of reasoning")
        self.assertEqual(result.score, 0.0)

    def test_classify_threshold(self):
        scorer = GroundingScorer(threshold=0.5)
        self.assertTrue(scorer.classify("2+2=4", "fact: 2+2=4", "why"))
        self.assertFalse(scorer.classify("unverified claim", None, "guess"))

    def test_empty_claim(self):
        scorer = GroundingScorer()
        result = scorer.score("", "fact: something")
        self.assertEqual(result.score, 0.0)


if __name__ == "__main__":
    unittest.main()