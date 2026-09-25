"""Hermetic tests for Trait Lab seed pack diff (PR #223)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    diff_trait_lab_seed_packs,
    export_trait_lab_seed_pack,
    record_trait_lab_run,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabSeedPackDiff(unittest.TestCase):
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

    def test_diff_same_seed_two_packs(self) -> None:
        finish = self._record_finish(5, "pr223-a")
        pack_a = export_trait_lab_seed_pack(self.store, 5)
        draw = self._record_draw_finish(5, "pr223-b")
        pack_b = export_trait_lab_seed_pack(self.store, 5)
        diff = diff_trait_lab_seed_packs(pack_a, pack_b)
        self.assertEqual(diff["seed"], 5)
        self.assertTrue(diff["same_seed"])
        self.assertEqual(diff["a"]["count"], 1)
        self.assertEqual(diff["b"]["count"], 2)
        self.assertEqual(diff["count_delta"], -1)
        self.assertEqual(diff["shared"], [finish["proof_sha256"]])
        self.assertEqual(diff["only_a"], [])
        self.assertEqual(diff["only_b"], [draw["proof_sha256"]])
        self.assertFalse(diff["live_verified"])

    def test_seed_mismatch_and_same_pack(self) -> None:
        self._record_finish(1, "pr223-c")
        self._record_finish(2, "pr223-d")
        pack_one = export_trait_lab_seed_pack(self.store, 1)
        pack_two = export_trait_lab_seed_pack(self.store, 2)
        with self.assertRaises(MemoryLayerError) as err:
            diff_trait_lab_seed_packs(pack_one, pack_two)
        self.assertEqual(err.exception.code, "seed_mismatch")
        with self.assertRaises(MemoryLayerError) as err2:
            diff_trait_lab_seed_packs(pack_one, pack_one)
        self.assertEqual(err2.exception.code, "same_pack")

    def test_live_claim_and_invalid_pack(self) -> None:
        self._record_finish(3, "pr223-e")
        pack = export_trait_lab_seed_pack(self.store, 3)
        live = dict(pack)
        live["live_verified"] = True
        with self.assertRaises(MemoryLayerError) as err:
            diff_trait_lab_seed_packs(live, pack)
        self.assertEqual(err.exception.code, "live_claim")
        with self.assertRaises(MemoryLayerError) as err2:
            diff_trait_lab_seed_packs("nope", pack)  # type: ignore[arg-type]
        self.assertEqual(err2.exception.code, "invalid_pack")


if __name__ == "__main__":
    unittest.main()
