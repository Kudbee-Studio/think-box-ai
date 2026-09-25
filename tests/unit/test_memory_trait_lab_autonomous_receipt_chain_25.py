"""Hermetic tests for Trait Lab autonomous receipt chain R01–R25."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.autonomous_receipt_chain import (
    TRAIT_LAB_AUTONOMOUS_RECEIPT_CHAIN_OPS,
    chain_from_trait_lab_autonomous_receipt,
    diff_trait_lab_autonomous_receipt_chain_indexes,
    export_trait_lab_autonomous_receipt_chain_index,
    persist_trait_lab_autonomous_receipt_chain_index,
    refuse_trait_lab_autonomous_receipt_chain_live,
    require_trait_lab_autonomous_receipt_chain_provenance,
    require_trait_lab_autonomous_receipt_green_chain,
    retain_best_trait_lab_autonomous_receipt_chain,
    sign_trait_lab_autonomous_receipt_chain,
    trait_lab_autonomous_receipt_chain_has,
    verify_trait_lab_autonomous_receipt_chain,
    verify_trait_lab_autonomous_receipt_chain_index,
)
from thinkbox.autonomous_workflow import run_trait_lab_autonomous
from thinkbox.memory_layers import MemoryLayerError


class TestMemoryTraitLabAutonomousReceiptChain25(unittest.TestCase):
    def test_r00_ops_catalog_has_25(self) -> None:
        self.assertEqual(len(TRAIT_LAB_AUTONOMOUS_RECEIPT_CHAIN_OPS), 25)
        self.assertEqual(len(set(TRAIT_LAB_AUTONOMOUS_RECEIPT_CHAIN_OPS)), 25)

    def test_r01_r02_live_and_provenance(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            refuse_trait_lab_autonomous_receipt_chain_live({"live_verified": True})
        self.assertEqual(err.exception.code, "live_claim")
        with self.assertRaises(MemoryLayerError) as prov:
            require_trait_lab_autonomous_receipt_chain_provenance(agent_id="", task_id="r02")
        self.assertEqual(prov.exception.code, "missing_provenance")

    def test_r03_r08_sign_verify_index(self) -> None:
        row = sign_trait_lab_autonomous_receipt_chain(
            {
                "prep_sha256": "a" * 64,
                "session_sha256": "b" * 64,
                "autonomous_sha256": "c" * 64,
                "status": "dry_run",
            }
        )
        rematch = verify_trait_lab_autonomous_receipt_chain(row)
        self.assertTrue(rematch["matched"])
        tmp = tempfile.TemporaryDirectory()
        store = MemoryStore(Path(tmp.name) / "empty.db")
        try:
            index = export_trait_lab_autonomous_receipt_chain_index(store)
            self.assertEqual(index["count"], 0)
            verify_trait_lab_autonomous_receipt_chain_index(index)
        finally:
            store.close()
            tmp.cleanup()
        public_row = {
            "prep_sha256": row["prep_sha256"],
            "session_sha256": row["session_sha256"],
            "autonomous_sha256": row["autonomous_sha256"],
            "status": row["status"],
            "live_verified": False,
        }
        index: dict = {
            "kind": "trait-lab-autonomous-receipt-chain-index",
            "chains": [public_row],
            "count": 1,
            "live_verified": False,
        }
        import hashlib
        import json

        body = {
            "kind": "trait-lab-autonomous-receipt-chain-index",
            "chains": [public_row],
            "count": 1,
            "live_verified": False,
        }
        index["chain_index_sha256"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        verified = verify_trait_lab_autonomous_receipt_chain_index(index)
        self.assertTrue(verified["matched"])
        self.assertTrue(trait_lab_autonomous_receipt_chain_has(index, autonomous_sha256="c" * 64))

    def test_r16_r25_green_chain_and_persist(self) -> None:
        out = run_trait_lab_autonomous(agent_id="unit", task_id="r25", environ={})
        store = MemoryStore(Path(out["workspace"]["store_path"]))
        try:
            auto_sha = out["autonomous"]["autonomous_sha256"]
            chain = chain_from_trait_lab_autonomous_receipt(store, auto_sha)
            green = require_trait_lab_autonomous_receipt_green_chain(store, chain)
            self.assertTrue(green["green"])
            index = export_trait_lab_autonomous_receipt_chain_index(store)
            self.assertGreaterEqual(index["count"], 1)
            best = retain_best_trait_lab_autonomous_receipt_chain(index)
            self.assertEqual(best["autonomous_sha256"], auto_sha)
            persisted = persist_trait_lab_autonomous_receipt_chain_index(
                store, index, agent_id="unit", task_id="r25"
            )
            self.assertTrue(persisted["persisted"])
            index2 = export_trait_lab_autonomous_receipt_chain_index(store)
            diff = diff_trait_lab_autonomous_receipt_chain_indexes(index, index2)
            self.assertEqual(diff["only_a"], diff["only_b"])
        finally:
            store.close()
