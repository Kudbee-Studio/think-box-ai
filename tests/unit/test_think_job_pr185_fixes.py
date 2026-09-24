"""Unit tests for PR #185 lifecycle fix pack."""

from __future__ import annotations

import unittest

from thinkbox import kilo_pr185_think_job_lifecycle_fixes as pr185
from thinkbox.think_job_lifecycle_fixes.fixes.fix_registry import run_all_fixes


class TestThinkJobPr185Fixes(unittest.TestCase):
    def test_fixes_manifest(self) -> None:
        ok, violations = pr185.validate_fixes_manifest()
        self.assertTrue(ok, violations)

    def test_run_all_fixes(self) -> None:
        result = run_all_fixes()
        self.assertEqual(result["fix_count"], 25)
        self.assertTrue(result["all_hermetic"])
        self.assertFalse(result["live_api_called"])
