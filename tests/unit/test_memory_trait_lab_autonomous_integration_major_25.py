"""Hermetic tests for Trait Lab autonomous integration major K01–K25."""

from __future__ import annotations

import unittest

from thinkbox.autonomous_integration_major import (
    TRAIT_LAB_AUTONOMOUS_INTEGRATION_MAJOR_OPS,
    assert_trait_lab_autonomous_integration_major_ok,
    bundle_trait_lab_autonomous_integration_major_for_ci,
    manifest_trait_lab_autonomous_integration_major_layers,
    open_trait_lab_autonomous_integration_major,
    plan_trait_lab_autonomous_integration_major,
    refuse_trait_lab_autonomous_integration_major_live,
    sign_trait_lab_autonomous_integration_major,
    verify_trait_lab_autonomous_integration_major,
)
from thinkbox.memory_layers import MemoryLayerError


class TestMemoryTraitLabAutonomousIntegrationMajor25(unittest.TestCase):
    def test_k00_ops_catalog(self) -> None:
        self.assertEqual(len(TRAIT_LAB_AUTONOMOUS_INTEGRATION_MAJOR_OPS), 25)

    def test_k01_k07_plan(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            refuse_trait_lab_autonomous_integration_major_live({"live_verified": True})
        self.assertEqual(err.exception.code, "live_claim")
        signed = sign_trait_lab_autonomous_integration_major(
            plan_trait_lab_autonomous_integration_major("gate_regression")
        )
        self.assertTrue(verify_trait_lab_autonomous_integration_major(signed)["matched"])
        manifest = manifest_trait_lab_autonomous_integration_major_layers(signed)
        self.assertEqual(len(manifest["layers"]), 2)

    def test_k08_k25_gate_only(self) -> None:
        opened = open_trait_lab_autonomous_integration_major(
            agent_id="unit",
            task_id="k25-gate",
            environ={},
            mode="gate",
        )
        self.assertTrue(opened["integration_open"])
        self.assertEqual(len(opened["layer_results"]), 1)
        assert_trait_lab_autonomous_integration_major_ok(opened)
        bundle = bundle_trait_lab_autonomous_integration_major_for_ci(opened)
        self.assertTrue(bundle["report"]["ok"])

    def test_k08_k25_gate_regression(self) -> None:
        opened = open_trait_lab_autonomous_integration_major(
            agent_id="unit",
            task_id="k25-full",
            environ={},
            mode="gate_regression",
        )
        self.assertTrue(opened["ok"])
        self.assertEqual(len(opened["layer_results"]), 2)
        assert_trait_lab_autonomous_integration_major_ok(opened)


if __name__ == "__main__":
    unittest.main()
