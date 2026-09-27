"""Hermetic tests for Trait Lab seed history (PR #211)."""

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
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabSeedHistory(unittest.TestCase):
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

    def test_history_orders_by_xp_and_matches_best(self) -> None:
        self._record_finish(5, "pr211-finish")
        self._record_draw_finish(5, "pr211-draw")
        history = trait_lab_seed_history(self.store, 5)
        self.assertEqual(history["seed"], 5)
        self.assertGreaterEqual(history["count"], 1)
        xp_values = [int(row["xp"] or 0) for row in history["runs"]]
        self.assertEqual(xp_values, sorted(xp_values, reverse=True))
        self.assertEqual(history["best"]["xp"], best_trait_lab_seed(self.store, 5)["xp"])
        self.assertFalse(history["live_verified"])

    def test_history_excludes_other_seeds(self) -> None:
        self._record_finish(1, "pr211-a")
        self._record_finish(2, "pr211-b")
        history = trait_lab_seed_history(self.store, 1)
        self.assertEqual(history["count"], 1)
        self.assertEqual(history["runs"][0]["seed"], 1)

    def test_missing_seed_and_invalid_limit(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            trait_lab_seed_history(self.store, 99)
        self.assertEqual(err.exception.code, "missing_seed")
        self._record_finish(3, "pr211-c")
        with self.assertRaises(MemoryLayerError) as err2:
            trait_lab_seed_history(self.store, 3, limit=0)
        self.assertEqual(err2.exception.code, "invalid_limit")
        with self.assertRaises(MemoryLayerError) as err3:
            trait_lab_seed_history(self.store, "nope")  # type: ignore[arg-type]
        self.assertEqual(err3.exception.code, "invalid_seed")


if __name__ == "__main__":
    unittest.main()
