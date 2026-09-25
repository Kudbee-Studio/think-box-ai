"""Hermetic tests for Trait Lab seed pack catalog (PR #224)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.schema import MemoryEntry, MemoryEntryType, MemoryLayer
from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    apply_trait_lab_seed_pack,
    catalog_trait_lab_seed_packs,
    diff_trait_lab_seed_packs,
    export_trait_lab_seed_pack,
    get_trait_lab_seed_pack,
    import_trait_lab_seed_pack,
    record_trait_lab_run,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabSeedPackCatalog(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "layers.db")
        self.rules = load_rules()

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def _record_finish(self, seed: int, task_id: str) -> dict:
        state = act(self.rules, new_run(self.rules, seed=seed, difficulty="lab"), "finish")["state"]
        proof = proof_scorecard(state)
        record_trait_lab_run(self.store, proof, agent_id="unit", task_id=task_id)
        return proof

    def _record_draw_finish(self, seed: int, task_id: str) -> dict:
        state = new_run(self.rules, seed=seed, difficulty="lab")
        state = act(self.rules, state, "draw")["state"]
        state = act(self.rules, state, "finish")["state"]
        proof = proof_scorecard(state)
        record_trait_lab_run(self.store, proof, agent_id="unit", task_id=task_id)
        return proof

    def test_catalog_discovers_import_and_apply(self) -> None:
        empty = catalog_trait_lab_seed_packs(self.store)
        self.assertEqual(empty["kind"], "trait-lab-seed-pack-catalog")
        self.assertEqual(empty["count"], 0)
        self.assertEqual(empty["packs"], [])
        self.assertFalse(empty["live_verified"])
        self._record_finish(5, "pr224-a")
        pack = export_trait_lab_seed_pack(self.store, 5)
        dest = MemoryStore(Path(self.tmp.name) / "dest.db")
        try:
            apply_trait_lab_seed_pack(dest, pack, agent_id="unit", task_id="pr224-apply")
            catalog = catalog_trait_lab_seed_packs(dest)
            self.assertEqual(catalog["count"], 1)
            row = catalog["packs"][0]
            self.assertEqual(row["pack_sha256"], pack["pack_sha256"])
            self.assertEqual(row["fact_id"], f"trait-lab-pack-{pack['pack_sha256'][:16]}")
            self.assertEqual(row["seed"], 5)
            self.assertEqual(row["count"], 1)
            self.assertEqual(row["kind"], "trait-lab-seed-pack")
            self.assertFalse(row["live_verified"])
            selected = get_trait_lab_seed_pack(dest, pack["pack_sha256"])
            self.assertEqual(selected["pack_sha256"], pack["pack_sha256"])
        finally:
            dest.close()

    def test_catalog_orders_by_seed_then_hash(self) -> None:
        self._record_finish(2, "pr224-b")
        self._record_finish(1, "pr224-c")
        pack_two = export_trait_lab_seed_pack(self.store, 2)
        pack_one = export_trait_lab_seed_pack(self.store, 1)
        import_trait_lab_seed_pack(self.store, pack_two, agent_id="unit", task_id="pr224-imp-2")
        import_trait_lab_seed_pack(self.store, pack_one, agent_id="unit", task_id="pr224-imp-1")
        catalog = catalog_trait_lab_seed_packs(self.store)
        self.assertEqual(catalog["count"], 2)
        seeds = [row["seed"] for row in catalog["packs"]]
        self.assertEqual(seeds, [1, 2])
        ids = [row["pack_sha256"] for row in catalog["packs"]]
        self.assertEqual(ids, [pack_one["pack_sha256"], pack_two["pack_sha256"]])
        self.assertEqual(len(ids[0]), 64)
        again = catalog_trait_lab_seed_packs(self.store)
        self.assertEqual([row["pack_sha256"] for row in again["packs"]], ids)

    def test_malformed_pack_row_skipped_and_invalid_inputs(self) -> None:
        self.store.put(
            MemoryEntry(
                key="verified:trait-lab-pack-deadbeefdeadbeef",
                layer=MemoryLayer.VERIFIED_KNOWLEDGE,
                entry_type=MemoryEntryType.FACT,
                value={"source": "abc", "seed": 9, "fact": "bad", "kind": "trait-lab-seed-pack"},
                agent_id="unit",
                task_id="pr224-bad",
            )
        )
        catalog = catalog_trait_lab_seed_packs(self.store)
        self.assertEqual(catalog["count"], 0)
        with self.assertRaises(MemoryLayerError) as err:
            catalog_trait_lab_seed_packs(self.store, limit=0)
        self.assertEqual(err.exception.code, "invalid_limit")
        with self.assertRaises(MemoryLayerError) as err2:
            get_trait_lab_seed_pack(self.store, "abc")
        self.assertEqual(err2.exception.code, "missing_pack_hash")
        missing = "ab" * 32
        with self.assertRaises(MemoryLayerError) as err3:
            get_trait_lab_seed_pack(self.store, missing)
        self.assertEqual(err3.exception.code, "missing_pack")

    def test_catalog_does_not_break_diff(self) -> None:
        self._record_finish(5, "pr224-d")
        pack_a = export_trait_lab_seed_pack(self.store, 5)
        self._record_draw_finish(5, "pr224-e")
        pack_b = export_trait_lab_seed_pack(self.store, 5)
        import_trait_lab_seed_pack(self.store, pack_a, agent_id="unit", task_id="pr224-imp-a")
        import_trait_lab_seed_pack(self.store, pack_b, agent_id="unit", task_id="pr224-imp-b")
        catalog = catalog_trait_lab_seed_packs(self.store)
        self.assertEqual(catalog["count"], 2)
        hashes = {row["pack_sha256"] for row in catalog["packs"]}
        self.assertEqual(hashes, {pack_a["pack_sha256"], pack_b["pack_sha256"]})
        diff = diff_trait_lab_seed_packs(pack_a, pack_b)
        self.assertEqual(diff["seed"], 5)
        self.assertTrue(diff["same_seed"])
        self.assertFalse(diff["live_verified"])


if __name__ == "__main__":
    unittest.main()
