"""Hermetic tests for Trait Lab autonomous flow workflow compose P01–P25."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.autonomous_flow_workflow import (
    export_trait_lab_autonomous_flow_workflow_receipt_index,
    open_trait_lab_autonomous_flow_workflow,
    verify_trait_lab_autonomous_flow_workflow_receipt_index,
)
from thinkbox.autonomous_flow_workflow_compose import (
    TRAIT_LAB_AUTONOMOUS_FLOW_WORKFLOW_COMPOSE_OPS,
    export_trait_lab_autonomous_flow_workflow_compose_as_index,
    guard_same_trait_lab_autonomous_flow_workflow_receipt_index,
    intersect_trait_lab_autonomous_flow_workflow_receipt_indexes,
    merge_trait_lab_autonomous_flow_workflow_receipt_indexes,
    persist_trait_lab_autonomous_flow_workflow_compose_snapshot,
    refuse_trait_lab_autonomous_flow_workflow_compose_live,
    subtract_trait_lab_autonomous_flow_workflow_receipt_indexes,
    symmetric_diff_sets_trait_lab_autonomous_flow_workflow_compose,
    symmetric_diff_trait_lab_autonomous_flow_workflow_receipt_indexes,
    verify_trait_lab_autonomous_flow_workflow_compose,
    verify_trait_lab_autonomous_flow_workflow_compose_pair,
)
from thinkbox.memory_layers import MemoryLayerError


def _signed_index(flows: list[dict]) -> dict:
    body = {
        "kind": "trait-lab-autonomous-flow-workflow-receipt-index",
        "flows": flows,
        "count": len(flows),
        "live_verified": False,
    }
    flows_sorted = sorted(flows, key=lambda row: str(row["flow_sha256"]))
    body["flows"] = flows_sorted
    sha = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {**body, "flow_receipt_index_sha256": sha}


class TestMemoryTraitLabAutonomousFlowWorkflowCompose25(unittest.TestCase):
    def test_p00_ops_catalog_has_25(self) -> None:
        self.assertEqual(len(TRAIT_LAB_AUTONOMOUS_FLOW_WORKFLOW_COMPOSE_OPS), 25)

    def test_p01_p02_live_and_guard(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            refuse_trait_lab_autonomous_flow_workflow_compose_live({"live_verified": True})
        self.assertEqual(err.exception.code, "live_claim")
        idx = _signed_index([])
        with self.assertRaises(MemoryLayerError) as same:
            guard_same_trait_lab_autonomous_flow_workflow_receipt_index(idx, idx)
        self.assertEqual(same.exception.code, "same_flow_index")

    def test_p03_p06_compose_modes(self) -> None:
        row_a = {
            "flow_sha256": "a" * 64,
            "bind_sha256": "b" * 64,
            "chain_index_sha256": "c" * 64,
            "autonomous_sha256": "d" * 64,
            "status": "dry_run",
            "live_verified": False,
        }
        row_b = {
            "flow_sha256": "e" * 64,
            "bind_sha256": "f" * 64,
            "chain_index_sha256": "0" * 64,
            "autonomous_sha256": "1" * 64,
            "status": "ready",
            "live_verified": False,
        }
        left = _signed_index([row_a])
        right = _signed_index([row_b])
        verify_trait_lab_autonomous_flow_workflow_compose_pair(left, right)
        merged = merge_trait_lab_autonomous_flow_workflow_receipt_indexes(left, right)
        self.assertEqual(merged["mode"], "merge")
        self.assertEqual(merged["count"], 2)
        verify_trait_lab_autonomous_flow_workflow_compose(merged)
        inter = intersect_trait_lab_autonomous_flow_workflow_receipt_indexes(left, right)
        self.assertEqual(inter["count"], 0)
        sub = subtract_trait_lab_autonomous_flow_workflow_receipt_indexes(left, right)
        self.assertEqual(sub["count"], 1)
        xor = symmetric_diff_trait_lab_autonomous_flow_workflow_receipt_indexes(left, right)
        self.assertEqual(xor["count"], 2)
        sets = symmetric_diff_sets_trait_lab_autonomous_flow_workflow_compose(left, right)
        self.assertEqual(set(sets["flows"]), {"a" * 64, "e" * 64})

    def test_p19_p25_export_and_persist(self) -> None:
        opened = open_trait_lab_autonomous_flow_workflow(agent_id="unit", task_id="p25", environ={})
        store = MemoryStore(Path(opened["results"][-1]["run"]["workspace"]["store_path"]))
        try:
            exported = export_trait_lab_autonomous_flow_workflow_receipt_index(store)
            verify_trait_lab_autonomous_flow_workflow_receipt_index(exported)
            row = list(exported["flows"])[0]
            left = _signed_index([row])
            right = _signed_index([])
            merged = merge_trait_lab_autonomous_flow_workflow_receipt_indexes(left, right)
            as_index = export_trait_lab_autonomous_flow_workflow_compose_as_index(merged)
            verify_trait_lab_autonomous_flow_workflow_receipt_index(as_index)
            snap = persist_trait_lab_autonomous_flow_workflow_compose_snapshot(
                store, merged, agent_id="unit", task_id="p25"
            )
            self.assertTrue(snap["persisted"])
        finally:
            store.close()
