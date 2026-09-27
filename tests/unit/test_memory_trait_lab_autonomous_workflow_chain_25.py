"""Hermetic tests for Trait Lab autonomous workflow chain bind F01–F25."""

from __future__ import annotations

import unittest

from thinkbox.autonomous_workflow_chain import (
    TRAIT_LAB_AUTONOMOUS_WORKFLOW_CHAIN_OPS,
    align_trait_lab_autonomous_run_to_chain,
    dry_run_trait_lab_autonomous_chained,
    export_trait_lab_autonomous_workflow_chain_from_run,
    open_trait_lab_autonomous_chained,
    refuse_trait_lab_autonomous_workflow_chain_live,
    require_trait_lab_autonomous_workflow_chain_provenance,
    run_trait_lab_autonomous_chained,
    sign_trait_lab_autonomous_workflow_chain_bind,
    trait_lab_autonomous_workflow_chain_status,
    verify_trait_lab_autonomous_workflow_chain_bind,
)
from core.memory.store import MemoryStore
from pathlib import Path
from thinkbox.autonomous_workflow import run_trait_lab_autonomous
from thinkbox.memory_layers import MemoryLayerError
import tempfile


class TestMemoryTraitLabAutonomousWorkflowChain25(unittest.TestCase):
    def test_f00_ops_catalog_has_25(self) -> None:
        self.assertEqual(len(TRAIT_LAB_AUTONOMOUS_WORKFLOW_CHAIN_OPS), 25)

    def test_f01_f02_live_and_provenance(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            refuse_trait_lab_autonomous_workflow_chain_live({"live_verified": True})
        self.assertEqual(err.exception.code, "live_claim")
        with self.assertRaises(MemoryLayerError) as prov:
            require_trait_lab_autonomous_workflow_chain_provenance(agent_id="", task_id="f02")
        self.assertEqual(prov.exception.code, "missing_provenance")

    def test_f04_f13_export_and_align(self) -> None:
        run_result = run_trait_lab_autonomous(agent_id="unit", task_id="f04", environ={})
        index = export_trait_lab_autonomous_workflow_chain_from_run(run_result)
        aligned = align_trait_lab_autonomous_run_to_chain(run_result, index)
        self.assertTrue(aligned["aligned"])
        bind = sign_trait_lab_autonomous_workflow_chain_bind(aligned)
        self.assertTrue(verify_trait_lab_autonomous_workflow_chain_bind(bind)["matched"])

    def test_f20_f24_chained_run(self) -> None:
        chained = run_trait_lab_autonomous_chained(agent_id="unit", task_id="f20", environ={})
        self.assertTrue(chained["chained"])
        self.assertTrue(chained["ok"])
        self.assertEqual(trait_lab_autonomous_workflow_chain_status(chained), "ready")
        opened = open_trait_lab_autonomous_chained(agent_id="unit", task_id="f24", environ={})
        self.assertTrue(opened["chained"])

    def test_f21_dry_run_chained(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        store = MemoryStore(Path(tmp.name) / "layers.db")
        try:
            out = dry_run_trait_lab_autonomous_chained(
                store, agent_id="unit", task_id="f21", environ={}
            )
            self.assertEqual(out["status"], "dry_run")
            self.assertFalse(out["wrote"])
        finally:
            store.close()
            tmp.cleanup()
