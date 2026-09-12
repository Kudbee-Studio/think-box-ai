"""Unit tests for thinkbox/thinktrace.py — grounding scoring."""

import unittest
from thinkbox.thinktrace import ThinkTraceCapture


class TestThinkTraceCapture(unittest.TestCase):
    def test_capture_grounded(self):
        capture = ThinkTraceCapture()
        trace = capture.capture("a1", "reading fact-card", evidence_refs=["fc_1"])
        self.assertTrue(trace.grounded)
        self.assertEqual(trace.confidence, 1.0)

    def test_capture_ungrounded(self):
        capture = ThinkTraceCapture()
        trace = capture.capture("a1", "speculative guess")
        self.assertFalse(trace.grounded)
        self.assertEqual(trace.confidence, 0.0)

    def test_count(self):
        capture = ThinkTraceCapture()
        capture.capture("a1", "grounded thought", evidence_refs=["fc_1"])
        capture.capture("a1", "twin thought")
        self.assertEqual(capture.count(), 2)
        self.assertEqual(capture.count(grounded=True), 1)
        self.assertEqual(capture.count(grounded=False), 1)

    def test_pairs_match_agent(self):
        capture = ThinkTraceCapture()
        capture.capture("a1", "proposal based on evidence", evidence_refs=["fc_1"])
        capture.capture("a1", "proposal with no evidence")
        capture.capture("a2", "other grounded", evidence_refs=["fc_2"])
        pairs = capture.pairs()
        self.assertEqual(len(pairs), 1)
        g, u = pairs[0]
        self.assertEqual(g.agent_id, u.agent_id)
        self.assertTrue(g.grounded)
        self.assertFalse(u.grounded)

    def test_similarity(self):
        score = ThinkTraceCapture._similarity("alpha beta gamma", "alpha beta delta")
        self.assertGreaterEqual(score, 0.5)


if __name__ == "__main__":
    unittest.main()