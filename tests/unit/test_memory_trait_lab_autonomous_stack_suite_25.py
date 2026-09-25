"""Hermetic tests for Trait Lab autonomous stack suite V01–V25."""

from __future__ import annotations

import unittest

from thinkbox.autonomous_stack_suite import (
    TRAIT_LAB_AUTONOMOUS_STACK_SUITE_OPS,
    assert_trait_lab_autonomous_stack_suite_ok,
    bundle_trait_lab_autonomous_stack_for_ci,
    export_trait_lab_autonomous_stack_suite_report,
    open_trait_lab_autonomous_stack_suite,
    plan_trait_lab_autonomous_stack_suite,
    refuse_trait_lab_autonomous_stack_suite_live,
    rematch_trait_lab_autonomous_stack_suite_full_smoke,
    run_trait_lab_autonomous_stack_suite,
    sign_trait_lab_autonomous_stack_suite,
    trait_lab_autonomous_stack_suite_run_ok,
    verify_trait_lab_autonomous_stack_suite,
    verify_trait_lab_autonomous_stack_suite_report,
)
from thinkbox.memory_layers import MemoryLayerError


class TestMemoryTraitLabAutonomousStackSuite25(unittest.TestCase):
    def test_v00_ops_catalog_has_25(self) -> None:
        self.assertEqual(len(TRAIT_LAB_AUTONOMOUS_STACK_SUITE_OPS), 25)

    def test_v01_v07_plan_sign_verify(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            refuse_trait_lab_autonomous_stack_suite_live({"live_verified": True})
        self.assertEqual(err.exception.code, "live_claim")
        plan = plan_trait_lab_autonomous_stack_suite(["dry", "run"])
        signed = sign_trait_lab_autonomous_stack_suite(plan)
        self.assertTrue(verify_trait_lab_autonomous_stack_suite(signed)["matched"])

    def test_v08_run_suite_partial(self) -> None:
        plan = sign_trait_lab_autonomous_stack_suite(plan_trait_lab_autonomous_stack_suite(["dry"]))
        ran = run_trait_lab_autonomous_stack_suite(
            plan, agent_id="unit", task_id="v08", environ={}
        )
        self.assertTrue(ran["ok"])
        self.assertEqual(len(ran["runs"]), 1)
        report = export_trait_lab_autonomous_stack_suite_report(ran)
        verify_trait_lab_autonomous_stack_suite_report(report)

    def test_v12_v21_full_suite_and_ci_bundle(self) -> None:
        plan = sign_trait_lab_autonomous_stack_suite(plan_trait_lab_autonomous_stack_suite())
        ran = run_trait_lab_autonomous_stack_suite(
            plan, agent_id="unit", task_id="v12", environ={}
        )
        self.assertTrue(ran["ok"])
        self.assertTrue(trait_lab_autonomous_stack_suite_run_ok(ran, "full"))
        assert_trait_lab_autonomous_stack_suite_ok(ran)
        bundle = bundle_trait_lab_autonomous_stack_for_ci(ran)
        self.assertFalse(bundle["live_verified"])
        self.assertTrue(bundle["report"]["ok"])

    def test_v25_open_stack_suite(self) -> None:
        opened = open_trait_lab_autonomous_stack_suite(
            agent_id="unit",
            task_id="v25",
            environ={},
            persist_artifact=True,
        )
        self.assertTrue(opened["suite_open"])
        self.assertTrue(opened["ok"])
        self.assertTrue(opened["suite_artifact"]["persisted"])
        rematch_trait_lab_autonomous_stack_suite_full_smoke(opened)


if __name__ == "__main__":
    unittest.main()
