"""Hermetic tests for Trait Lab autonomous stack harness U01–U25."""

from __future__ import annotations

import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.autonomous_stack_harness import (
    TRAIT_LAB_AUTONOMOUS_STACK_HARNESS_OPS,
    TRAIT_LAB_AUTONOMOUS_STACK_SMOKE_MODES,
    assert_trait_lab_autonomous_stack_smoke_ok,
    bundle_trait_lab_autonomous_stack_for_app,
    export_trait_lab_autonomous_stack_smoke_report,
    open_trait_lab_autonomous_stack_harness,
    plan_trait_lab_autonomous_stack_smoke,
    refuse_trait_lab_autonomous_stack_harness_live,
    rematch_trait_lab_autonomous_stack_flow_receipt,
    run_trait_lab_autonomous_stack_smoke,
    sign_trait_lab_autonomous_stack_smoke,
    verify_trait_lab_autonomous_stack_smoke,
    verify_trait_lab_autonomous_stack_smoke_report,
)
from thinkbox.memory_layers import MemoryLayerError


class TestMemoryTraitLabAutonomousStackHarness25(unittest.TestCase):
    def test_u00_ops_and_modes(self) -> None:
        self.assertEqual(len(TRAIT_LAB_AUTONOMOUS_STACK_HARNESS_OPS), 25)
        self.assertEqual(len(TRAIT_LAB_AUTONOMOUS_STACK_SMOKE_MODES), 3)

    def test_u01_u07_plan_sign_verify(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            refuse_trait_lab_autonomous_stack_harness_live({"live_verified": True})
        self.assertEqual(err.exception.code, "live_claim")
        plan = plan_trait_lab_autonomous_stack_smoke("run")
        signed = sign_trait_lab_autonomous_stack_smoke(plan)
        self.assertTrue(verify_trait_lab_autonomous_stack_smoke(signed)["matched"])

    def test_u08_dry_smoke(self) -> None:
        plan = sign_trait_lab_autonomous_stack_smoke(plan_trait_lab_autonomous_stack_smoke("dry"))
        ran = run_trait_lab_autonomous_stack_smoke(
            plan, agent_id="unit", task_id="u08-dry", environ={}
        )
        report = export_trait_lab_autonomous_stack_smoke_report(ran)
        self.assertEqual(report["mode"], "dry")
        self.assertTrue(report["ok"])
        verify_trait_lab_autonomous_stack_smoke_report(report)

    def test_u08_run_smoke(self) -> None:
        plan = sign_trait_lab_autonomous_stack_smoke(plan_trait_lab_autonomous_stack_smoke("run"))
        ran = run_trait_lab_autonomous_stack_smoke(
            plan, agent_id="unit", task_id="u08-run", environ={}
        )
        self.assertTrue(ran["ok"])
        report = export_trait_lab_autonomous_stack_smoke_report(ran)
        self.assertEqual(report["mode"], "run")
        self.assertTrue(trait_lab_autonomous_stack_phase_ok_helper(ran, "autonomous"))

    def test_u25_open_full_harness(self) -> None:
        opened = open_trait_lab_autonomous_stack_harness(
            mode="full",
            agent_id="unit",
            task_id="u25",
            environ={},
            persist_artifact=True,
        )
        self.assertTrue(opened["harness_open"])
        self.assertTrue(opened["ok"])
        assert_trait_lab_autonomous_stack_smoke_ok(opened)
        bundle = bundle_trait_lab_autonomous_stack_for_app(opened)
        self.assertFalse(bundle["live_verified"])
        store = MemoryStore(Path(opened["report"]["store_path"]))
        try:
            rematch = rematch_trait_lab_autonomous_stack_flow_receipt(store, opened)
            self.assertTrue(rematch["rematched"])
        finally:
            store.close()


def trait_lab_autonomous_stack_phase_ok_helper(run, phase: str) -> bool:
    from thinkbox.autonomous_stack_harness import trait_lab_autonomous_stack_phase_ok

    return trait_lab_autonomous_stack_phase_ok(run, phase)


if __name__ == "__main__":
    unittest.main()
