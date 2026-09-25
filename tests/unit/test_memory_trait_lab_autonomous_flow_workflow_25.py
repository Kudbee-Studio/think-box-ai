"""Hermetic tests for Trait Lab autonomous flow workflow major O01–O25."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.autonomous_flow_workflow import (
    TRAIT_LAB_AUTONOMOUS_FLOW_WORKFLOW_OPS,
    TRAIT_LAB_AUTONOMOUS_FLOW_WORKFLOW_STEPS,
    dry_run_trait_lab_autonomous_flow_workflow,
    export_trait_lab_autonomous_flow_workflow_artifacts,
    has_trait_lab_autonomous_flow_workflow_receipt,
    open_trait_lab_autonomous_flow_workflow,
    plan_trait_lab_autonomous_flow_workflow,
    refuse_trait_lab_autonomous_flow_workflow_live,
    run_trait_lab_autonomous_flow_workflow,
    sign_trait_lab_autonomous_flow_workflow,
    trait_lab_autonomous_flow_workflow_status,
    verify_trait_lab_autonomous_flow_workflow,
)
from thinkbox.memory_layers import MemoryLayerError


class TestMemoryTraitLabAutonomousFlowWorkflow25(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "layers.db")

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def test_o00_ops_and_steps(self) -> None:
        self.assertEqual(len(TRAIT_LAB_AUTONOMOUS_FLOW_WORKFLOW_OPS), 25)
        self.assertEqual(len(TRAIT_LAB_AUTONOMOUS_FLOW_WORKFLOW_STEPS), 2)

    def test_o01_o07_plan_sign_verify(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            refuse_trait_lab_autonomous_flow_workflow_live({"live_verified": True})
        self.assertEqual(err.exception.code, "live_claim")
        plan = plan_trait_lab_autonomous_flow_workflow(["run_chained"])
        signed = sign_trait_lab_autonomous_flow_workflow(plan)
        self.assertTrue(verify_trait_lab_autonomous_flow_workflow(signed)["matched"])

    def test_o10_dry_run_flow(self) -> None:
        plan = sign_trait_lab_autonomous_flow_workflow(plan_trait_lab_autonomous_flow_workflow(["dry_run"]))
        ran = dry_run_trait_lab_autonomous_flow_workflow(
            self.store, plan, agent_id="unit", task_id="o10", environ={}
        )
        self.assertEqual(trait_lab_autonomous_flow_workflow_status(ran), "dry_run")
        self.assertFalse(ran["wrote"])

    def test_o11_o13_run_flow_artifacts(self) -> None:
        plan = sign_trait_lab_autonomous_flow_workflow(plan_trait_lab_autonomous_flow_workflow(["run_chained"]))
        ran = run_trait_lab_autonomous_flow_workflow(
            plan, agent_id="unit", task_id="o11", environ={}
        )
        self.assertTrue(ran["ok"])
        artifacts = export_trait_lab_autonomous_flow_workflow_artifacts(ran)
        self.assertEqual(len(artifacts["autonomous_sha256"]), 64)

    def test_o25_open_flow(self) -> None:
        opened = open_trait_lab_autonomous_flow_workflow(agent_id="unit", task_id="o25", environ={})
        self.assertTrue(opened["opened"])
        self.assertTrue(opened["flow_persisted"])
        store = MemoryStore(Path(opened["results"][-1]["run"]["workspace"]["store_path"]))
        try:
            self.assertTrue(
                has_trait_lab_autonomous_flow_workflow_receipt(store, opened["flow_sha256"])
            )
        finally:
            store.close()
