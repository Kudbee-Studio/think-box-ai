"""Hermetic tests for Trait Lab autonomous app regression J01–J25."""

from __future__ import annotations

import unittest

from thinkbox.autonomous_app_regression import (
    TRAIT_LAB_AUTONOMOUS_APP_REGRESSION_OPS,
    assert_trait_lab_autonomous_app_regression_ok,
    compare_trait_lab_autonomous_app_regression_reports,
    open_trait_lab_autonomous_app_regression,
    plan_trait_lab_autonomous_app_regression,
    refuse_trait_lab_autonomous_app_regression_live,
    sign_trait_lab_autonomous_app_regression,
    verify_trait_lab_autonomous_app_regression,
)
from thinkbox.memory_layers import MemoryLayerError


class TestMemoryTraitLabAutonomousAppRegression25(unittest.TestCase):
    def test_j00_ops_catalog(self) -> None:
        self.assertEqual(len(TRAIT_LAB_AUTONOMOUS_APP_REGRESSION_OPS), 25)

    def test_j01_j07_plan(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            refuse_trait_lab_autonomous_app_regression_live({"live_verified": True})
        self.assertEqual(err.exception.code, "live_claim")
        signed = sign_trait_lab_autonomous_app_regression(plan_trait_lab_autonomous_app_regression("compare"))
        self.assertTrue(verify_trait_lab_autonomous_app_regression(signed)["matched"])

    def test_j08_j13_capture_and_compare(self) -> None:
        captured = open_trait_lab_autonomous_app_regression(
            agent_id="unit", task_id="j08", environ={}
        )
        self.assertTrue(captured["regression_open"])
        self.assertIsNotNone(captured.get("baseline"))
        compared = open_trait_lab_autonomous_app_regression(
            agent_id="unit",
            task_id="j13",
            environ={},
            baseline=captured["baseline"],
        )
        self.assertTrue(compared["ok"])
        assert_trait_lab_autonomous_app_regression_ok(compared)
        cmp = compare_trait_lab_autonomous_app_regression_reports(
            captured["baseline"], compared["candidate"]
        )
        self.assertTrue(cmp["no_regression"])


if __name__ == "__main__":
    unittest.main()
