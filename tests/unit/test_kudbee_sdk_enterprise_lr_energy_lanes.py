"""Enterprise lr-energy lane tests (PR #195)."""

from __future__ import annotations

import unittest

from thinkbox import kilo_pr195_kudbee_sdk_enterprise_lr_energy as pr195
from thinkbox.kudbee_sdk_enterprise_lr_energy import enterprise_status_snapshot
from thinkbox.kudbee_sdk_enterprise_lr_energy.lanes.lane_registry import run_all_lanes


class TestKudbeeSdkEnterpriseLrEnergyLanes(unittest.TestCase):
    def test_lanes_manifest(self) -> None:
        ok, violations = pr195.validate_lanes_manifest()
        self.assertTrue(ok, violations)

    def test_run_all_lanes(self) -> None:
        result = run_all_lanes()
        self.assertEqual(result["lane_count"], 25)
        self.assertTrue(result["all_hermetic"])
        self.assertFalse(result["live_api_called"])
        self.assertEqual(result["tier"], "enterprise")

    def test_enterprise_hub(self) -> None:
        snap = enterprise_status_snapshot()
        self.assertFalse(snap["live_api_called"])
        self.assertEqual(snap["tier"], "enterprise")


if __name__ == "__main__":
    unittest.main()
