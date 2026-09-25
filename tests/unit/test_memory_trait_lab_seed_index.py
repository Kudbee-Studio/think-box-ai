"""Hermetic tests for Trait Lab seed index (PR #212)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    best_trait_lab_seed,
    record_trait_lab_run,
    trait_lab_seed_history,
    trait_lab_seed_index,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabSeedIndex(unittest.TestCase):
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

    def test_empty_index_is_not_live(self) -> None:
        index = trait_lab_seed_index(self.store)
        self.assertEqual(index["count"], 0)
        self.assertEqual(index["seeds"], [])
        self.assertFalse(index["live_verified"])

    def test_same_seed_counts_and_matches_best(self) -> None:
        first = self._record_finish(5, "pr212-finish")
        second = self._record_draw_finish(5, "pr212-draw")
        index = trait_lab_seed_index(self.store)
        self.assertEqual(index["count"], 1)
        row = index["seeds"][0]
        self.assertEqual(row["seed"], 5)
        self.assertGreaterEqual(row["count"], 1)
        self.assertEqual(row["best_xp"], max(int(first["xp"]), int(second["xp"])))
        self.assertEqual(row["best"]["xp"], best_trait_lab_seed(self.store, 5)["xp"])
        self.assertEqual(row["count"], trait_lab_seed_history(self.store, 5)["count"])
        self.assertFalse(index["live_verified"])

    def test_two_seeds_ordered_by_best_xp(self) -> None:
        self._record_finish(1, "pr212-a")
        self._record_finish(2, "pr212-b")
        index = trait_lab_seed_index(self.store)
        self.assertEqual(index["count"], 2)
        seeds = {row["seed"] for row in index["seeds"]}
        self.assertEqual(seeds, {1, 2})
        xp_values = [int(row["best_xp"]) for row in index["seeds"]]
        self.assertEqual(xp_values, sorted(xp_values, reverse=True))

    def test_invalid_limit(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            trait_lab_seed_index(self.store, limit=0)
        self.assertEqual(err.exception.code, "invalid_limit")


if __name__ == "__main__":
    unittest.main()
