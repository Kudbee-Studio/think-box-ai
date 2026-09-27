"""Hermetic tests for best Trait Lab run per seed (PR #210)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    best_trait_lab_by_seed,
    best_trait_lab_seed,
    record_trait_lab_run,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabBestSeed(unittest.TestCase):
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
        bundle = best_trait_lab_by_seed(self.store)
        self.assertEqual(bundle["seeds"], 0)
        self.assertEqual(bundle["by_seed"], {})
        self.assertFalse(bundle["live_verified"])

    def test_keeps_highest_xp_for_one_seed(self) -> None:
        first = self._record_finish(5, "pr210-finish")
        second = self._record_draw_finish(5, "pr210-draw")
        bundle = best_trait_lab_by_seed(self.store)
        self.assertEqual(bundle["seeds"], 1)
        best = bundle["by_seed"][5]
        self.assertEqual(best["xp"], max(int(first["xp"]), int(second["xp"])))
        picked = best_trait_lab_seed(self.store, 5)
        self.assertEqual(picked["xp"], best["xp"])
        self.assertFalse(picked["live_verified"])

    def test_two_seeds_stay_separate(self) -> None:
        self._record_finish(1, "pr210-a")
        self._record_finish(2, "pr210-b")
        bundle = best_trait_lab_by_seed(self.store)
        self.assertEqual(bundle["seeds"], 2)
        self.assertIn(1, bundle["by_seed"])
        self.assertIn(2, bundle["by_seed"])

    def test_missing_seed_and_invalid_limit(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            best_trait_lab_seed(self.store, 99)
        self.assertEqual(err.exception.code, "missing_seed")
        with self.assertRaises(MemoryLayerError) as err2:
            best_trait_lab_by_seed(self.store, limit=0)
        self.assertEqual(err2.exception.code, "invalid_limit")
        with self.assertRaises(MemoryLayerError) as err3:
            best_trait_lab_seed(self.store, "nope")  # type: ignore[arg-type]
        self.assertEqual(err3.exception.code, "invalid_seed")


if __name__ == "__main__":
    unittest.main()
