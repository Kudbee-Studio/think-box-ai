"""Hermetic tests for Trait Lab seed pack catalog by seed (PR #225)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    catalog_trait_lab_seed_packs,
    catalog_trait_lab_seed_packs_for_seed,
    export_trait_lab_seed_pack,
    import_trait_lab_seed_pack,
    record_trait_lab_run,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabSeedPackCatalogSeed(unittest.TestCase):
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

    def test_filter_keeps_matching_seed_ordered_by_hash(self) -> None:
        self._record_finish(5, "pr225-a")
        pack_a = export_trait_lab_seed_pack(self.store, 5)
        self._record_draw_finish(5, "pr225-b")
        pack_b = export_trait_lab_seed_pack(self.store, 5)
        import_trait_lab_seed_pack(self.store, pack_a, agent_id="unit", task_id="pr225-imp-a")
        import_trait_lab_seed_pack(self.store, pack_b, agent_id="unit", task_id="pr225-imp-b")
        catalog = catalog_trait_lab_seed_packs_for_seed(self.store, 5)
        self.assertEqual(catalog["kind"], "trait-lab-seed-pack-catalog")
        self.assertEqual(catalog["seed"], 5)
        self.assertEqual(catalog["count"], 2)
        hashes = [row["pack_sha256"] for row in catalog["packs"]]
        self.assertEqual(hashes, sorted(hashes))
        self.assertEqual(set(hashes), {pack_a["pack_sha256"], pack_b["pack_sha256"]})
        self.assertFalse(catalog["live_verified"])

    def test_filter_excludes_other_seeds(self) -> None:
        self._record_finish(1, "pr225-c")
        self._record_finish(2, "pr225-d")
        pack_one = export_trait_lab_seed_pack(self.store, 1)
        pack_two = export_trait_lab_seed_pack(self.store, 2)
        import_trait_lab_seed_pack(self.store, pack_one, agent_id="unit", task_id="pr225-imp-1")
        import_trait_lab_seed_pack(self.store, pack_two, agent_id="unit", task_id="pr225-imp-2")
        catalog = catalog_trait_lab_seed_packs_for_seed(self.store, 1)
        self.assertEqual(catalog["count"], 1)
        self.assertEqual(catalog["packs"][0]["seed"], 1)
        self.assertEqual(catalog["packs"][0]["pack_sha256"], pack_one["pack_sha256"])
        self.assertEqual(catalog_trait_lab_seed_packs(self.store)["count"], 2)

    def test_missing_and_invalid_inputs(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            catalog_trait_lab_seed_packs_for_seed(self.store, 99)
        self.assertEqual(err.exception.code, "missing_seed")
        self._record_finish(3, "pr225-e")
        pack = export_trait_lab_seed_pack(self.store, 3)
        import_trait_lab_seed_pack(self.store, pack, agent_id="unit", task_id="pr225-imp-3")
        with self.assertRaises(MemoryLayerError) as err2:
            catalog_trait_lab_seed_packs_for_seed(self.store, 3, limit=0)
        self.assertEqual(err2.exception.code, "invalid_limit")
        with self.assertRaises(MemoryLayerError) as err3:
            catalog_trait_lab_seed_packs_for_seed(self.store, "nope")  # type: ignore[arg-type]
        self.assertEqual(err3.exception.code, "invalid_seed")


if __name__ == "__main__":
    unittest.main()
