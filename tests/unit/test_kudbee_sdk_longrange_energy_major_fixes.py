"""Unit tests for PR #194 Kudbee SDK lr-energy major fixes."""

from __future__ import annotations

import unittest

from thinkbox import kilo_pr194_kudbee_sdk_longrange_energy_major_fixes as pr194
from thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.fix_registry import run_all_fixes


class TestKudbeeSdkLongrangeEnergyMajorFixes(unittest.TestCase):
    def test_fixes_manifest(self) -> None:
        ok, violations = pr194.validate_fixes_manifest()
        self.assertTrue(ok, violations)

    def test_run_all_fixes(self) -> None:
        result = run_all_fixes()
        self.assertEqual(result["fix_count"], 25)
        self.assertTrue(result["all_hermetic"])
        self.assertFalse(result["live_api_called"])


if __name__ == "__main__":
    unittest.main()
