"""Hermetic tests for Trait Lab autonomous receipt chain compose M01–M25."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.autonomous_receipt_chain import verify_trait_lab_autonomous_receipt_chain_index
from thinkbox.autonomous_receipt_chain_compose import (
    TRAIT_LAB_AUTONOMOUS_RECEIPT_CHAIN_COMPOSE_OPS,
    export_trait_lab_autonomous_receipt_chain_compose_as_index,
    guard_same_trait_lab_autonomous_receipt_chain_index,
    intersect_trait_lab_autonomous_receipt_chain_indexes,
    merge_trait_lab_autonomous_receipt_chain_indexes,
    persist_trait_lab_autonomous_receipt_chain_compose_snapshot,
    refuse_trait_lab_autonomous_receipt_chain_compose_live,
    subtract_trait_lab_autonomous_receipt_chain_indexes,
    symmetric_diff_sets_trait_lab_autonomous_receipt_chain_compose,
    symmetric_diff_trait_lab_autonomous_receipt_chain_indexes,
    verify_trait_lab_autonomous_receipt_chain_compose,
    verify_trait_lab_autonomous_receipt_chain_compose_pair,
)
from thinkbox.autonomous_workflow import run_trait_lab_autonomous
from thinkbox.memory_layers import MemoryLayerError


def _signed_index(chains: list[dict]) -> dict:
    body = {
        "kind": "trait-lab-autonomous-receipt-chain-index",
        "chains": chains,
        "count": len(chains),
        "live_verified": False,
    }
    sha = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {**body, "chain_index_sha256": sha}


class TestMemoryTraitLabAutonomousReceiptChainCompose25(unittest.TestCase):
    def test_m00_ops_catalog_has_25(self) -> None:
        self.assertEqual(len(TRAIT_LAB_AUTONOMOUS_RECEIPT_CHAIN_COMPOSE_OPS), 25)

    def test_m01_m02_live_and_guard(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            refuse_trait_lab_autonomous_receipt_chain_compose_live({"live_verified": True})
        self.assertEqual(err.exception.code, "live_claim")
        idx = _signed_index([])
        with self.assertRaises(MemoryLayerError) as same:
            guard_same_trait_lab_autonomous_receipt_chain_index(idx, idx)
        self.assertEqual(same.exception.code, "same_chain_index")

    def test_m03_m06_compose_modes(self) -> None:
        row_a = {
            "prep_sha256": "a" * 64,
            "session_sha256": "b" * 64,
            "autonomous_sha256": "c" * 64,
            "status": "dry_run",
            "live_verified": False,
        }
        row_b = {
            "prep_sha256": "d" * 64,
            "session_sha256": "e" * 64,
            "autonomous_sha256": "f" * 64,
            "status": "ready",
            "live_verified": False,
        }
        left = _signed_index([row_a])
        right = _signed_index([row_b])
        verify_trait_lab_autonomous_receipt_chain_compose_pair(left, right)
        merged = merge_trait_lab_autonomous_receipt_chain_indexes(left, right)
        self.assertEqual(merged["mode"], "merge")
        self.assertEqual(merged["count"], 2)
        verify_trait_lab_autonomous_receipt_chain_compose(merged)
        inter = intersect_trait_lab_autonomous_receipt_chain_indexes(left, right)
        self.assertEqual(inter["count"], 0)
        sub = subtract_trait_lab_autonomous_receipt_chain_indexes(left, right)
        self.assertEqual(sub["count"], 1)
        xor = symmetric_diff_trait_lab_autonomous_receipt_chain_indexes(left, right)
        self.assertEqual(xor["count"], 2)
        sets = symmetric_diff_sets_trait_lab_autonomous_receipt_chain_compose(left, right)
        self.assertEqual(set(sets["autos"]), {"c" * 64, "f" * 64})

    def test_m19_m25_export_and_persist(self) -> None:
        out = run_trait_lab_autonomous(agent_id="unit", task_id="m25", environ={})
        store = MemoryStore(Path(out["workspace"]["store_path"]))
        try:
            auto = out["autonomous"]["autonomous_sha256"]
            row = {
                "prep_sha256": out["autonomous"]["prep_sha256"],
                "session_sha256": out["autonomous"]["session_sha256"],
                "autonomous_sha256": auto,
                "status": "ready",
                "live_verified": False,
            }
            left = _signed_index([row])
            right = _signed_index([])
            merged = merge_trait_lab_autonomous_receipt_chain_indexes(left, right)
            exported = export_trait_lab_autonomous_receipt_chain_compose_as_index(merged)
            verify_trait_lab_autonomous_receipt_chain_index(exported)
            snap = persist_trait_lab_autonomous_receipt_chain_compose_snapshot(
                store, merged, agent_id="unit", task_id="m25"
            )
            self.assertTrue(snap["persisted"])
        finally:
            store.close()
