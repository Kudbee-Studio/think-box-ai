"""Hermetic tests for Trait Lab catalog pin-index compose."""

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
    import_trait_lab_catalog_pins,
    import_trait_lab_seed_pack,
    intersect_trait_lab_catalog_pin_indexes,
    merge_trait_lab_catalog_pin_indexes,
    pin_trait_lab_seed_pack_catalog,
    record_trait_lab_run,
    subtract_trait_lab_catalog_pin_indexes,
    verify_trait_lab_catalog_pins,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabCatalogPinCompose(unittest.TestCase):
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

    def test_merge_unions_two_indexes(self) -> None:
        left = self._pin_index_from_seeds([1], "merge-a")
        dest = MemoryStore(Path(self.tmp.name) / "merge-b.db")
        try:
            import_trait_lab_catalog_pins(dest, left, agent_id="unit", task_id="share-1")
            self._import_seed(dest, 2, "merge-b-2")
            self._pin_current(dest, "merge-b-pin-2")
            right = export_trait_lab_catalog_pins(dest)
        finally:
            dest.close()
        merged = merge_trait_lab_catalog_pin_indexes(left, right)
        self.assertEqual(merged["mode"], "merge")
        self.assertEqual(merged["count"], 2)
        self.assertFalse(merged["live_verified"])
        rematch = verify_trait_lab_catalog_pins(merged)
        self.assertTrue(rematch["matched"])

    def test_intersect_keeps_shared_pins(self) -> None:
        left = self._pin_index_from_seeds([3, 4], "int-a")
        dest = MemoryStore(Path(self.tmp.name) / "int-b.db")
        try:
            import_trait_lab_catalog_pins(dest, left, agent_id="unit", task_id="int-share")
            self._import_seed(dest, 5, "int-b-5")
            self._pin_current(dest, "int-b-pin-5")
            right = export_trait_lab_catalog_pins(dest)
        finally:
            dest.close()
        shared = intersect_trait_lab_catalog_pin_indexes(left, right)
        self.assertEqual(shared["mode"], "intersect")
        self.assertEqual(shared["count"], 2)
        self.assertFalse(shared["live_verified"])

    def test_subtract_drops_right_pins(self) -> None:
        left = self._pin_index_from_seeds([6, 7], "sub-a")
        right = self._signed_index([row for row in left["pins"] if row["count"] == 1])
        leftover = subtract_trait_lab_catalog_pin_indexes(left, right)
        self.assertEqual(leftover["mode"], "subtract")
        self.assertEqual(leftover["count"], 1)
        self.assertEqual(leftover["pins"][0]["count"], 2)
        self.assertFalse(leftover["live_verified"])

    def test_same_index_and_live_claim_fail_closed(self) -> None:
        index = self._pin_index_from_seeds([8], "same")
        with self.assertRaises(MemoryLayerError) as err:
            merge_trait_lab_catalog_pin_indexes(index, index)
        self.assertEqual(err.exception.code, "same_pin_index")
        live = dict(index)
        live["live_verified"] = True
        with self.assertRaises(MemoryLayerError) as err2:
            intersect_trait_lab_catalog_pin_indexes(index, live)
        self.assertEqual(err2.exception.code, "live_claim")

    def test_pin_conflict_and_invalid_index(self) -> None:
        row = {
            "catalog_sha256": "ab" * 32,
            "fact_id": "trait-lab-catalog-abababababababab",
            "kind": "trait-lab-seed-pack-catalog-pin",
            "count": 1,
            "ids": ["cd" * 32],
            "live_verified": False,
        }
        left = self._signed_index([row])
        conflicted = dict(row)
        conflicted["count"] = 2
        right = self._signed_index([conflicted])
        with self.assertRaises(MemoryLayerError) as err:
            merge_trait_lab_catalog_pin_indexes(left, right)
        self.assertEqual(err.exception.code, "pin_conflict")
        with self.assertRaises(MemoryLayerError) as err2:
            subtract_trait_lab_catalog_pin_indexes(left, "nope")
        self.assertEqual(err2.exception.code, "invalid_pin_index")

    def test_disjoint_intersect_is_empty_and_not_live(self) -> None:
        left = self._pin_index_from_seeds([9], "empty-a")
        right = self._pin_index_from_seeds([10], "empty-b")
        shared = intersect_trait_lab_catalog_pin_indexes(left, right)
        self.assertEqual(shared["count"], 0)
        self.assertEqual(shared["pins"], [])
        self.assertFalse(shared["live_verified"])
        rematch = verify_trait_lab_catalog_pins(shared)
        self.assertTrue(rematch["matched"])


if __name__ == "__main__":
    unittest.main()
