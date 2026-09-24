"""Expansion pack tests for PR #192 (long-range + energy loops)."""

from __future__ import annotations

import unittest

from thinkbox import kilo_pr192_kudbee_sdk_followup_w3_major_fixes as pr192
from thinkbox.kudbee_sdk_followup_w3_expansion.energy_loop import EnergyLoop
from thinkbox.kudbee_sdk_followup_w3_expansion.long_range import LongRangeLink
from thinkbox.kudbee_sdk_followup_w3_expansion.packs.pack_registry import run_all_packs


class TestKudbeeSdkFollowupW3ExpansionPacks(unittest.TestCase):
    def test_expansion_manifest(self) -> None:
        ok, violations = pr192.validate_expansion_manifest()
        self.assertTrue(ok, violations)

    def test_run_all_packs(self) -> None:
        result = run_all_packs()
        self.assertEqual(result["pack_count"], 26)
        self.assertTrue(result["all_hermetic"])
        self.assertFalse(result["live_api_called"])

    def test_long_range_and_energy_primitives(self) -> None:
        link = LongRangeLink.open("lr-test")
        link.advance_hop("c1")
        loop = EnergyLoop.open("e-test", capacity_units=5.0)
        loop.deposit(2.0)
        self.assertTrue(link.ping()["reachable"])
        self.assertTrue(loop.conserved())


if __name__ == "__main__":
    unittest.main()
