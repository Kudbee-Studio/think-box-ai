"""Hermetic tests for Trait Lab pin-index follow-through after compose."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    export_trait_lab_catalog_pins,
    export_trait_lab_seed_pack,
    export_trait_lab_seed_pack_catalog,
    get_trait_lab_catalog_pin_by_fact_id,
    import_trait_lab_catalog_pins,
    import_trait_lab_seed_pack,
    merge_trait_lab_catalog_pin_indexes,
    pin_trait_lab_seed_pack_catalog,
    record_trait_lab_run,
    retain_trait_lab_catalog_pin_index,
    symmetric_diff_trait_lab_catalog_pin_indexes,
    verify_trait_lab_catalog_pins,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabCatalogPinFollow(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.rules = load_rules()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _import_seed(self, store: MemoryStore, seed: int, task_id: str) -> dict:
        state = act(self.rules, new_run(self.rules, seed=seed, difficulty="lab"), "finish")["state"]
        proof = proof_scorecard(state)
        record_trait_lab_run(store, proof, agent_id="unit", task_id=task_id)
        pack = export_trait_lab_seed_pack(store, seed)
        import_trait_lab_seed_pack(store, pack, agent_id="unit", task_id=f"imp-{task_id}")
        return pack

    def _pin_current(self, store: MemoryStore, task_id: str) -> dict:
        catalog = export_trait_lab_seed_pack_catalog(store)
        return pin_trait_lab_seed_pack_catalog(store, catalog, agent_id="unit", task_id=task_id)

    def _pin_index_from_seeds(self, seeds: list[int], label: str) -> dict:
        store = MemoryStore(Path(self.tmp.name) / f"{label}.db")
        try:
            for seed in seeds:
                self._import_seed(store, seed, f"{label}-{seed}")
                self._pin_current(store, f"{label}-pin-{seed}")
            return export_trait_lab_catalog_pins(store)
        finally:
            store.close()

    def _signed_index(self, pins: list[dict]) -> dict:
        body = {
            "kind": "trait-lab-seed-pack-catalog-pin-index",
            "pins": pins,
            "count": len(pins),
            "live_verified": False,
        }
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {**body, "pin_index_sha256": hashlib.sha256(encoded).hexdigest()}

    def test_symmetric_diff_keeps_exclusive_pins(self) -> None:
        left = self._pin_index_from_seeds([1, 2], "xor-a")
        dest = MemoryStore(Path(self.tmp.name) / "xor-b.db")
        try:
            import_trait_lab_catalog_pins(dest, left, agent_id="unit", task_id="xor-share")
            self._import_seed(dest, 3, "xor-b-3")
            extra = self._pin_current(dest, "xor-b-pin-3")
            right = export_trait_lab_catalog_pins(dest)
        finally:
            dest.close()
        xor = symmetric_diff_trait_lab_catalog_pin_indexes(left, right)
        self.assertEqual(xor["mode"], "xor")
        self.assertEqual(xor["count"], 1)
        self.assertEqual(xor["pins"][0]["catalog_sha256"], extra["catalog_sha256"])
        self.assertFalse(xor["live_verified"])
        rematch = verify_trait_lab_catalog_pins(xor)
        self.assertTrue(rematch["matched"])

    def test_retain_keeps_highest_count(self) -> None:
        index = self._pin_index_from_seeds([4, 5], "retain")
        kept = retain_trait_lab_catalog_pin_index(index, keep=1)
        self.assertEqual(kept["kept"], 1)
        self.assertEqual(kept["keep"], 1)
        self.assertEqual(kept["count"], 1)
        self.assertEqual(kept["pins"][0]["count"], 2)
        self.assertFalse(kept["live_verified"])
        rematch = verify_trait_lab_catalog_pins(kept)
        self.assertTrue(rematch["matched"])

    def test_id_order_does_not_conflict(self) -> None:
        row = {
            "catalog_sha256": "ab" * 32,
            "fact_id": "trait-lab-catalog-abababababababab",
            "kind": "trait-lab-seed-pack-catalog-pin",
            "count": 2,
            "ids": ["cd" * 32, "ef" * 32],
            "live_verified": False,
        }
        flipped = dict(row)
        flipped["ids"] = list(reversed(row["ids"]))
        left = self._signed_index([row])
        right = self._signed_index([flipped])
        merged = merge_trait_lab_catalog_pin_indexes(left, right)
        self.assertEqual(merged["count"], 1)
        self.assertEqual(merged["mode"], "merge")

    def test_fact_id_rejects_non_hex_suffix(self) -> None:
        store = MemoryStore(Path(self.tmp.name) / "fact.db")
        try:
            with self.assertRaises(MemoryLayerError) as err:
                get_trait_lab_catalog_pin_by_fact_id(store, "trait-lab-catalog-zzzzzzzzzzzzzzzz")
            self.assertEqual(err.exception.code, "missing_pin")
        finally:
            store.close()

    def test_invalid_keep_and_empty_retain(self) -> None:
        index = self._pin_index_from_seeds([6], "keep")
        with self.assertRaises(MemoryLayerError) as err:
            retain_trait_lab_catalog_pin_index(index, keep=0)
        self.assertEqual(err.exception.code, "invalid_keep")
        empty = self._signed_index([])
        with self.assertRaises(MemoryLayerError) as err2:
            retain_trait_lab_catalog_pin_index(empty)
        self.assertEqual(err2.exception.code, "missing_pin")
        live = dict(index)
        live["live_verified"] = True
        with self.assertRaises(MemoryLayerError) as err3:
            retain_trait_lab_catalog_pin_index(live)
        self.assertEqual(err3.exception.code, "live_claim")


if __name__ == "__main__":
    unittest.main()
