"""Unit tests for thinkbox/reasoning.py — reasoning-channel normalization."""

import unittest

from thinkbox.reasoning import NormalizedCompletion, ReasoningNormalizer, capture_completion
from thinkbox.thinktrace import ThinkTraceCapture


class TestParseResponse(unittest.TestCase):
    def test_reasoning_and_content(self):
        normalizer = ReasoningNormalizer()
        completion = normalizer.parse_response(
            {"choices": [{"message": {"content": "4", "reasoning": "2+2"}, "finish_reason": "stop"}]}
        )
        self.assertEqual(completion.content, "4")
        self.assertEqual(completion.reasoning, "2+2")
        self.assertTrue(completion.had_reasoning)

    def test_without_reasoning(self):
        normalizer = ReasoningNormalizer()
        completion = normalizer.parse_response({"choices": [{"message": {"content": "hi"}}]})
        self.assertFalse(completion.had_reasoning)

    def test_empty_choices(self):
        normalizer = ReasoningNormalizer()
        completion = normalizer.parse_response({})
        self.assertEqual(completion.content, "")
        self.assertEqual(completion.reasoning, "")

    def test_content_parts_list(self):
        normalizer = ReasoningNormalizer()
        completion = normalizer.parse_response(
            {"choices": [{"message": {"content": [{"type": "text", "text": "he"}, {"type": "text", "text": "llo"}]}}]}
        )
        self.assertEqual(completion.content, "hello")

    def test_usage_captured(self):
        normalizer = ReasoningNormalizer()
        completion = normalizer.parse_response(
            {"choices": [{"message": {"content": "x"}}], "usage": {"total_tokens": 7}}
        )
        self.assertEqual(completion.usage["total_tokens"], 7)


class TestParseStreamLine(unittest.TestCase):
    def test_content_delta(self):
        normalizer = ReasoningNormalizer()
        chunk = normalizer.parse_stream_line('data: {"choices":[{"delta":{"content":"Hi"}}]}')
        self.assertIsNotNone(chunk)
        self.assertEqual(chunk.content, "Hi")

    def test_reasoning_delta(self):
        normalizer = ReasoningNormalizer()
        chunk = normalizer.parse_stream_line('data: {"choices":[{"delta":{"reasoning":"step 1"}}]}')
        self.assertEqual(chunk.reasoning, "step 1")

    def test_done_marker(self):
        normalizer = ReasoningNormalizer()
        self.assertIsNone(normalizer.parse_stream_line("data: [DONE]"))

    def test_malformed_line(self):
        normalizer = ReasoningNormalizer()
        self.assertIsNone(normalizer.parse_stream_line("not json"))

    def test_blank_line(self):
        normalizer = ReasoningNormalizer()
        self.assertIsNone(normalizer.parse_stream_line("   "))


class TestNormalizeStream(unittest.TestCase):
    def test_concatenates_content_and_reasoning(self):
        normalizer = ReasoningNormalizer()
        lines = [
            'data: {"choices":[{"delta":{"reasoning":"think "}}]}',
            'data: {"choices":[{"delta":{"reasoning":"more"}}]}',
            'data: {"choices":[{"delta":{"content":"Hel"}}]}',
            'data: {"choices":[{"delta":{"content":"lo"},"finish_reason":"stop"}]}',
            "data: [DONE]",
        ]
        completion = normalizer.normalize_stream(lines)
        self.assertEqual(completion.content, "Hello")
        self.assertEqual(completion.reasoning, "think more")
        self.assertEqual(completion.finish_reason, "stop")

    def test_empty_stream(self):
        normalizer = ReasoningNormalizer()
        completion = normalizer.normalize_stream([])
        self.assertEqual(completion.content, "")


class TestExtractReasoning(unittest.TestCase):
    def test_from_message(self):
        normalizer = ReasoningNormalizer()
        self.assertEqual(
            normalizer.extract_reasoning({"choices": [{"message": {"reasoning": "r"}}]}), "r"
        )

    def test_from_delta(self):
        normalizer = ReasoningNormalizer()
        self.assertEqual(
            normalizer.extract_reasoning({"choices": [{"delta": {"reasoning": "d"}}]}), "d"
        )

    def test_top_level_reasoning(self):
        normalizer = ReasoningNormalizer()
        self.assertEqual(normalizer.extract_reasoning({"reasoning": "top"}), "top")

    def test_missing(self):
        normalizer = ReasoningNormalizer()
        self.assertEqual(normalizer.extract_reasoning({}), "")


class TestCaptureCompletion(unittest.TestCase):
    def test_capture_grounded_preserves_reasoning(self):
        capture = ThinkTraceCapture()
        completion = NormalizedCompletion(content="4", reasoning="2+2", finish_reason="stop")
        trace = capture_completion(capture, "alice", completion, evidence_refs=["fact"])
        self.assertTrue(trace.grounded)
        self.assertEqual(trace.metadata["reasoning"], "2+2")
        self.assertIn("reasoning", trace.tags)

    def test_capture_ungrounded_without_evidence(self):
        capture = ThinkTraceCapture()
        completion = NormalizedCompletion(content="4", reasoning="trust me")
        trace = capture_completion(capture, "alice", completion)
        self.assertFalse(trace.grounded)

    def test_capture_without_reasoning(self):
        capture = ThinkTraceCapture()
        trace = capture_completion(capture, "alice", NormalizedCompletion(content="hi"))
        self.assertNotIn("reasoning", trace.tags)


if __name__ == "__main__":
    unittest.main()