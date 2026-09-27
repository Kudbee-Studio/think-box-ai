"""Deepen pack tests for PR #193 (long-range + energy loops)."""

from __future__ import annotations

import unittest

from thinkbox import kilo_pr193_kudbee_sdk_longrange_energy as pr193
from thinkbox.kudbee_sdk_longrange_energy_deepen.packs.pack_registry import run_all_packs


class TestKudbeeSdkLongrangeEnergyDeepenPacks(unittest.TestCase):
    def test_deepen_manifest(self) -> None:
        ok, violations = pr193.validate_deepen_manifest()
        self.assertTrue(ok, violations)

    def test_run_all_packs(self) -> None:
        result = run_all_packs()
        self.assertEqual(result["pack_count"], 30)
        self.assertTrue(result["all_hermetic"])
        self.assertFalse(result["live_api_called"])


if __name__ == "__main__":
    unittest.main()
