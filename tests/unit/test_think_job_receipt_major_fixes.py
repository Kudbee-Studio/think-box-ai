"""Unit tests for PR #187 receipt major fixes."""

from __future__ import annotations

import unittest

from thinkbox import kilo_pr187_think_job_receipt_major_fixes as pr187
from thinkbox.think_job_run_receipt_deepen.fixes.fix_registry import run_all_fixes


class TestThinkJobReceiptMajorFixes(unittest.TestCase):
    def test_fixes_manifest(self) -> None:
        ok, violations = pr187.validate_fixes_manifest()
        self.assertTrue(ok, violations)

    def test_run_all_fixes(self) -> None:
        result = run_all_fixes()
        self.assertEqual(result["fix_count"], 25)
        self.assertTrue(result["all_hermetic"])
        self.assertFalse(result["live_api_called"])


if __name__ == "__main__":
    unittest.main()
