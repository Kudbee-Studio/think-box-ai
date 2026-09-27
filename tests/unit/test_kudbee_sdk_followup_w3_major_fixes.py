"""Unit tests for PR #192 Kudbee SDK wave 3 major fixes."""

from __future__ import annotations

import unittest

from thinkbox import kilo_pr192_kudbee_sdk_followup_w3_major_fixes as pr192
from thinkbox.kudbee_sdk_followup_w3_major_fixes.fixes.fix_registry import run_all_fixes


class TestKudbeeSdkFollowupW3MajorFixes(unittest.TestCase):
    def test_fixes_manifest(self) -> None:
        ok, violations = pr192.validate_fixes_manifest()
        self.assertTrue(ok, violations)

    def test_run_all_fixes(self) -> None:
        result = run_all_fixes()
        self.assertEqual(result["fix_count"], 35)
        self.assertTrue(result["all_hermetic"])
        self.assertFalse(result["live_api_called"])


if __name__ == "__main__":
    unittest.main()
