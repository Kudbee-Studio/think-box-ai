"""Unit tests for the Dynamic Token Whip Protocol."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


class TestTokenEstimation(unittest.TestCase):
    def test_estimate_tokens_basic(self):
        from thinkbox.whip import estimate_tokens
        self.assertGreater(estimate_tokens("hello world"), 0)

    def test_estimate_tokens_empty(self):
        from thinkbox.whip import estimate_tokens
        self.assertEqual(estimate_tokens(""), 1)

    def test_estimate_tokens_long(self):
        from thinkbox.whip import estimate_tokens
        text = "x" * 400
        self.assertAlmostEqual(estimate_tokens(text), 100, delta=5)


class TestBracketDetection(unittest.TestCase):
    def test_closed_brackets(self):
        from thinkbox.whip import has_unclosed_brackets
        self.assertFalse(has_unclosed_brackets("def foo(): pass"))
        self.assertFalse(has_unclosed_brackets("[1, 2, 3]"))
        self.assertFalse(has_unclosed_brackets("{'a': 1}"))

    def test_unclosed_paren(self):
        from thinkbox.whip import has_unclosed_brackets
        self.assertTrue(has_unclosed_brackets("def foo("))
        self.assertTrue(has_unclosed_brackets("print('hello'"))

    def test_unclosed_bracket(self):
        from thinkbox.whip import has_unclosed_brackets
        self.assertTrue(has_unclosed_brackets("[1, 2, 3"))
        self.assertTrue(has_unclosed_brackets("{'a': 1"))

    def test_unclosed_brace(self):
        from thinkbox.whip import has_unclosed_brackets
        self.assertTrue(has_unclosed_brackets("{'a': 1"))

    def test_brackets_in_strings(self):
        from thinkbox.whip import has_unclosed_brackets
        self.assertFalse(has_unclosed_brackets("print('hello ( world')"))
        self.assertFalse(has_unclosed_brackets('print("hello [ world")'))


class TestDiffHunkDetection(unittest.TestCase):
    def test_complete_diff(self):
        from thinkbox.whip import has_incomplete_diff_hunk
        diff = "--- a/file.py\n+++ b/file.py\n@@ -1,3 +1,3 @@\n-old\n+new\n"
        self.assertFalse(has_incomplete_diff_hunk(diff))

    def test_incomplete_diff_no_at(self):
        from thinkbox.whip import has_incomplete_diff_hunk
        diff = "--- a/file.py\n+++ b/file.py\n-old\n"
        self.assertTrue(has_incomplete_diff_hunk(diff))

    def test_incomplete_diff_bad_at(self):
        from thinkbox.whip import has_incomplete_diff_hunk
        diff = "--- a/file.py\n+++ b/file.py\n@@ broken @@\n"
        self.assertTrue(has_incomplete_diff_hunk(diff))


class TestCodeBlockDetection(unittest.TestCase):
    def test_closed_code_block(self):
        from thinkbox.whip import has_unclosed_code_block
        code = "```python\nprint('hello')\n```"
        self.assertFalse(has_unclosed_code_block(code))

    def test_unclosed_code_block(self):
        from thinkbox.whip import has_unclosed_code_block
        code = "```python\nprint('hello')\n"
        self.assertTrue(has_unclosed_code_block(code))


class TestCompletionDensity(unittest.TestCase):
    def test_complete_code(self):
        from thinkbox.whip import calculate_completion_density
        code = "x = 1\ny = 2\nreturn x + y\n"
        density = calculate_completion_density(code)
        self.assertGreater(density, 0.5)

    def test_empty_density(self):
        from thinkbox.whip import calculate_completion_density
        self.assertEqual(calculate_completion_density(""), 0.0)

    def test_low_density(self):
        from thinkbox.whip import calculate_completion_density
        text = "incomplete\nunfinished\nbroken"
        density = calculate_completion_density(text)
        self.assertLess(density, 0.5)


class TestWhipProtocol(unittest.TestCase):
    def test_within_budget(self):
        from thinkbox.whip import TokenWhipProtocol, WhipDecision
        whip = TokenWhipProtocol()
        output = "x" * 100
        result, receipt = whip.evaluate("task_1", output)
        self.assertEqual(receipt.decision, WhipDecision.WITHIN_BUDGET)
        self.assertEqual(result, output)

    def test_over_ceiling_truncated(self):
        from thinkbox.whip import TokenWhipProtocol, WhipDecision, MAX_TOKEN_CEILING, TOKEN_CHAR_RATIO
        whip = TokenWhipProtocol()
        output = "x" * (MAX_TOKEN_CEILING * TOKEN_CHAR_RATIO + 1000)
        result, receipt = whip.evaluate("task_1", output)
        self.assertEqual(receipt.decision, WhipDecision.DENIED_TRUNCATED)
        self.assertLessEqual(len(result), MAX_TOKEN_CEILING * TOKEN_CHAR_RATIO)

    def test_syntax_extension_unclosed_bracket(self):
        from thinkbox.whip import TokenWhipProtocol, WhipDecision, STANDARD_TOKEN_ALLOWANCE
        whip = TokenWhipProtocol()
        output = "def foo(" + "x" * (STANDARD_TOKEN_ALLOWANCE * 4)
        result, receipt = whip.evaluate("task_1", output)
        self.assertEqual(receipt.decision, WhipDecision.AUTO_GRANTED)
        self.assertGreater(receipt.extension_granted, 0)

    def test_leader_approves_high_density(self):
        from thinkbox.whip import TokenWhipProtocol, WhipDecision
        whip = TokenWhipProtocol()
        line = "x = 1;"
        chars_per_line = len(line) + 1
        target_chars = 550 * 4
        num_lines = target_chars // chars_per_line
        output = ("\n".join([line] * num_lines)).strip()
        result, receipt = whip.evaluate("task_1", output)
        self.assertEqual(receipt.decision, WhipDecision.LEADER_APPROVED)

    def test_leader_rejects_low_density(self):
        from thinkbox.whip import TokenWhipProtocol, WhipDecision, STANDARD_TOKEN_ALLOWANCE
        whip = TokenWhipProtocol()
        output = "incomplete\nunfinished\nbroken\n" * 200
        result, receipt = whip.evaluate("task_1", output)
        self.assertEqual(receipt.decision, WhipDecision.DENIED_TRUNCATED)

    def test_whip_receipts_tracked(self):
        from thinkbox.whip import TokenWhipProtocol, WhipDecision
        whip = TokenWhipProtocol()
        output = "x" * 100
        whip.evaluate("task_1", output)
        self.assertEqual(len(whip.receipts), 1)
        self.assertEqual(whip.receipts[0].task_id, "task_1")

    def test_whip_receipt_to_dict(self):
        from thinkbox.whip import WhipReceipt, WhipDecision, WhipEvaluationState
        receipt = WhipReceipt(
            task_id="test",
            original_tokens=100,
            final_tokens=100,
            decision=WhipDecision.WITHIN_BUDGET,
            state=WhipEvaluationState.COMPLETED,
        )
        d = receipt.to_dict()
        self.assertEqual(d["task_id"], "test")
        self.assertEqual(d["decision"], "WITHIN_BUDGET")


class TestWhipIntegration(unittest.TestCase):
    def test_whip_with_session(self):
        from thinkbox.whip import TokenWhipProtocol, WhipDecision
        from thinkbox.session import create_session, clear_session, get_current_session
        clear_session()
        create_session(environment="test", actor="test-user")
        whip = TokenWhipProtocol()
        output = "x" * 100
        result, receipt = whip.evaluate("task_1", output)
        self.assertEqual(receipt.session_id, get_current_session().session_id)
        clear_session()

    def test_whip_audit_recording(self):
        from thinkbox.whip import TokenWhipProtocol, WhipDecision
        whip = TokenWhipProtocol()
        output = "x" * 100
        result, receipt = whip.evaluate("task_1", output)
        whip.record_to_audit(receipt)
        from backend.audit_storage import list_audits
        audits = list_audits(session_id=receipt.session_id)
        self.assertGreater(len(audits), 0)


if __name__ == "__main__":
    unittest.main()
