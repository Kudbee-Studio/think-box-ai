"""Hermetic tests for Trait Lab catalog compose (merge / intersect / subtract)."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    export_trait_lab_seed_pack,
    export_trait_lab_seed_pack_catalog,
    import_trait_lab_seed_pack,
    import_trait_lab_seed_pack_catalog,
    intersect_trait_lab_seed_pack_catalogs,
    merge_trait_lab_seed_pack_catalogs,
    record_trait_lab_run,
    subtract_trait_lab_seed_pack_catalogs,
    verify_trait_lab_seed_pack_catalog,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabCatalogCompose(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "layers.db")
        self.rules = load_rules()

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def _record_finish(self, store: MemoryStore, seed: int, task_id: str) -> dict:
        state = act(self.rules, new_run(self.rules, seed=seed, difficulty="lab"), "finish")["state"]
        proof = proof_scorecard(state)
        record_trait_lab_run(store, proof, agent_id="unit", task_id=task_id)
        return proof

    def _import_seed(self, store: MemoryStore, seed: int, task_id: str) -> dict:
        self._record_finish(store, seed, task_id)
        pack = export_trait_lab_seed_pack(store, seed)
        import_trait_lab_seed_pack(store, pack, agent_id="unit", task_id=f"imp-{task_id}")
        return pack

    def _catalog_from_seeds(self, seeds: list[int], label: str) -> dict:
        store = MemoryStore(Path(self.tmp.name) / f"{label}.db")
        try:
            for seed in seeds:
                self._import_seed(store, seed, f"{label}-{seed}")
            return export_trait_lab_seed_pack_catalog(store)
        finally:
            store.close()

    def _signed_catalog(self, packs: list[dict]) -> dict:
        body = {
            "kind": "trait-lab-seed-pack-catalog",
            "packs": packs,
            "count": len(packs),
            "live_verified": False,
        }
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {**body, "catalog_sha256": hashlib.sha256(encoded).hexdigest()}

    def test_merge_unions_two_catalogs(self) -> None:
        left = self._catalog_from_seeds([1, 2], "merge-a")
        dest = MemoryStore(Path(self.tmp.name) / "merge-b.db")
        try:
            shared = self._signed_catalog([row for row in left["packs"] if row["seed"] == 2])
            import_trait_lab_seed_pack_catalog(dest, shared, agent_id="unit", task_id="share-2")
            self._import_seed(dest, 3, "merge-b-3")
            right = export_trait_lab_seed_pack_catalog(dest)
        finally:
            dest.close()
        merged = merge_trait_lab_seed_pack_catalogs(left, right)
        self.assertEqual(merged["mode"], "merge")
        self.assertEqual(merged["count"], 3)
        self.assertFalse(merged["live_verified"])
        rematch = verify_trait_lab_seed_pack_catalog(merged)
        self.assertTrue(rematch["matched"])
        self.assertEqual({row["seed"] for row in merged["packs"]}, {1, 2, 3})

    def test_intersect_keeps_shared_packs(self) -> None:
        left = self._catalog_from_seeds([4, 5], "int-a")
        dest = MemoryStore(Path(self.tmp.name) / "int-b.db")
        try:
            import_trait_lab_seed_pack_catalog(dest, left, agent_id="unit", task_id="int-share")
            self._import_seed(dest, 6, "int-b-6")
            right = export_trait_lab_seed_pack_catalog(dest)
        finally:
            dest.close()
        shared = intersect_trait_lab_seed_pack_catalogs(left, right)
        self.assertEqual(shared["mode"], "intersect")
        self.assertEqual(shared["count"], 2)
        self.assertEqual({row["seed"] for row in shared["packs"]}, {4, 5})
        self.assertFalse(shared["live_verified"])

    def test_subtract_drops_right_packs(self) -> None:
        left = self._catalog_from_seeds([7, 8], "sub-a")
        right = self._signed_catalog([row for row in left["packs"] if row["seed"] == 7])
        leftover = subtract_trait_lab_seed_pack_catalogs(left, right)
        self.assertEqual(leftover["mode"], "subtract")
        self.assertEqual(leftover["count"], 1)
        self.assertEqual(leftover["packs"][0]["seed"], 8)
        self.assertFalse(leftover["live_verified"])

    def test_same_catalog_and_live_claim_fail_closed(self) -> None:
        catalog = self._catalog_from_seeds([9], "same")
        with self.assertRaises(MemoryLayerError) as err:
            merge_trait_lab_seed_pack_catalogs(catalog, catalog)
        self.assertEqual(err.exception.code, "same_catalog")
        live = dict(catalog)
        live["live_verified"] = True
        with self.assertRaises(MemoryLayerError) as err2:
            intersect_trait_lab_seed_pack_catalogs(catalog, live)
        self.assertEqual(err2.exception.code, "live_claim")

    def test_pack_conflict_and_invalid_catalog(self) -> None:
        row = {
            "pack_sha256": "ab" * 32,
            "fact_id": "trait-lab-pack-abababababababab",
            "kind": "trait-lab-seed-pack",
            "seed": 1,
            "count": 1,
            "live_verified": False,
        }
        left = self._signed_catalog([row])
        conflicted = dict(row)
        conflicted["count"] = 2
        right = self._signed_catalog([conflicted])
        with self.assertRaises(MemoryLayerError) as err:
            merge_trait_lab_seed_pack_catalogs(left, right)
        self.assertEqual(err.exception.code, "pack_conflict")
        with self.assertRaises(MemoryLayerError) as err2:
            subtract_trait_lab_seed_pack_catalogs(left, "nope")
        self.assertEqual(err2.exception.code, "invalid_catalog")

    def test_disjoint_intersect_is_empty_and_not_live(self) -> None:
        left = self._catalog_from_seeds([10], "empty-a")
        right = self._catalog_from_seeds([11], "empty-b")
        shared = intersect_trait_lab_seed_pack_catalogs(left, right)
        self.assertEqual(shared["count"], 0)
        self.assertEqual(shared["packs"], [])
        self.assertFalse(shared["live_verified"])
        rematch = verify_trait_lab_seed_pack_catalog(shared)
        self.assertTrue(rematch["matched"])


if __name__ == "__main__":
    unittest.main()
