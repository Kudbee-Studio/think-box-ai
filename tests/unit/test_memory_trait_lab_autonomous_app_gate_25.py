"""Hermetic tests for Trait Lab autonomous app gate G01–G25."""

from __future__ import annotations

import unittest

from thinkbox.autonomous_app_gate import (
    TRAIT_LAB_AUTONOMOUS_APP_GATE_OPS,
    assert_trait_lab_autonomous_app_gate_pass,
    bundle_trait_lab_autonomous_app_gate_for_ci,
    export_trait_lab_autonomous_app_gate_report,
    open_trait_lab_autonomous_app_gate,
    plan_trait_lab_autonomous_app_gate,
    refuse_trait_lab_autonomous_app_gate_live,
    rematch_trait_lab_autonomous_app_gate_suite_report,
    run_trait_lab_autonomous_app_gate,
    sign_trait_lab_autonomous_app_gate,
    trait_lab_autonomous_app_gate_contract_summary,
    verify_trait_lab_autonomous_app_gate,
    verify_trait_lab_autonomous_app_gate_report,
)
from thinkbox.memory_layers import MemoryLayerError


class TestMemoryTraitLabAutonomousAppGate25(unittest.TestCase):
    def test_g00_ops_and_contract(self) -> None:
        self.assertEqual(len(TRAIT_LAB_AUTONOMOUS_APP_GATE_OPS), 25)
        summary = trait_lab_autonomous_app_gate_contract_summary()
        self.assertTrue(summary["hermetic_operator_ok"])
        self.assertFalse(summary["live_verified"])

    def test_g01_g07_plan_sign_verify(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            refuse_trait_lab_autonomous_app_gate_live({"live_verified": True})
        self.assertEqual(err.exception.code, "live_claim")
        plan = plan_trait_lab_autonomous_app_gate()
        signed = sign_trait_lab_autonomous_app_gate(plan)
        self.assertTrue(verify_trait_lab_autonomous_app_gate(signed)["matched"])

    def test_g08_g12_run_and_assert(self) -> None:
        plan = sign_trait_lab_autonomous_app_gate(plan_trait_lab_autonomous_app_gate())
        ran = run_trait_lab_autonomous_app_gate(
            plan, agent_id="unit", task_id="g08", environ={}
        )
        self.assertTrue(ran["ok"])
        report = export_trait_lab_autonomous_app_gate_report(ran)
        verify_trait_lab_autonomous_app_gate_report(report)
        assert_trait_lab_autonomous_app_gate_pass(ran)
        rematch_trait_lab_autonomous_app_gate_suite_report(ran)

    def test_g20_g25_ci_bundle_and_open(self) -> None:
        opened = open_trait_lab_autonomous_app_gate(
            agent_id="unit",
            task_id="g25",
            environ={},
            persist_artifact=True,
        )
        self.assertTrue(opened["gate_open"])
        self.assertTrue(opened["passed"])
        bundle = bundle_trait_lab_autonomous_app_gate_for_ci(opened)
        self.assertTrue(bundle["gate"]["passed"])
        self.assertFalse(bundle["live_verified"])


if __name__ == "__main__":
    unittest.main()
