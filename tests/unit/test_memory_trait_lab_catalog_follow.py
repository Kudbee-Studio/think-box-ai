"""Hermetic tests for Trait Lab catalog compose follow-through (xor / retain)."""

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
    record_trait_lab_run,
    retain_trait_lab_seed_pack_catalog,
    symmetric_diff_trait_lab_seed_pack_catalogs,
    verify_trait_lab_seed_pack_catalog,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabCatalogFollow(unittest.TestCase):
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

    def test_symmetric_diff_keeps_exclusive_packs(self) -> None:
        left = self._catalog_from_seeds([1, 2], "xor-a")
        dest = MemoryStore(Path(self.tmp.name) / "xor-b.db")
        try:
            import_trait_lab_seed_pack_catalog(dest, left, agent_id="unit", task_id="xor-share")
            extra = self._import_seed(dest, 3, "xor-b-3")
            right = export_trait_lab_seed_pack_catalog(dest)
        finally:
            dest.close()
        xor = symmetric_diff_trait_lab_seed_pack_catalogs(left, right)
        self.assertEqual(xor["mode"], "xor")
        self.assertEqual(xor["count"], 1)
        self.assertEqual(xor["packs"][0]["pack_sha256"], extra["pack_sha256"])
        self.assertFalse(xor["live_verified"])
        rematch = verify_trait_lab_seed_pack_catalog(xor)
        self.assertTrue(rematch["matched"])

    def test_retain_keeps_one_pack(self) -> None:
        catalog = self._catalog_from_seeds([4, 5], "retain")
        kept = retain_trait_lab_seed_pack_catalog(catalog, keep=1)
        self.assertEqual(kept["kept"], 1)
        self.assertEqual(kept["keep"], 1)
        self.assertEqual(kept["count"], 1)
        self.assertFalse(kept["live_verified"])
        rematch = verify_trait_lab_seed_pack_catalog(kept)
        self.assertTrue(rematch["matched"])
        expected = sorted(catalog["packs"], key=lambda row: (-int(row["count"]), str(row["pack_sha256"])))[0]
        self.assertEqual(kept["packs"][0]["pack_sha256"], expected["pack_sha256"])

    def test_same_catalog_xor_and_live_claim(self) -> None:
        catalog = self._catalog_from_seeds([6], "same")
        with self.assertRaises(MemoryLayerError) as err:
            symmetric_diff_trait_lab_seed_pack_catalogs(catalog, catalog)
        self.assertEqual(err.exception.code, "same_catalog")
        live = dict(catalog)
        live["live_verified"] = True
        with self.assertRaises(MemoryLayerError) as err2:
            retain_trait_lab_seed_pack_catalog(live)
        self.assertEqual(err2.exception.code, "live_claim")

    def test_invalid_keep_and_empty_retain(self) -> None:
        catalog = self._catalog_from_seeds([7], "keep")
        with self.assertRaises(MemoryLayerError) as err:
            retain_trait_lab_seed_pack_catalog(catalog, keep=0)
        self.assertEqual(err.exception.code, "invalid_keep")
        empty = self._signed_catalog([])
        with self.assertRaises(MemoryLayerError) as err2:
            retain_trait_lab_seed_pack_catalog(empty)
        self.assertEqual(err2.exception.code, "missing_pack")


if __name__ == "__main__":
    unittest.main()
