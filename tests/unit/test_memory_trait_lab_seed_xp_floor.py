"""Hermetic tests for Trait Lab seed history XP floor (PR #217)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    record_trait_lab_run,
    trait_lab_seed_history_by_xp_floor,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabSeedXpFloor(unittest.TestCase):
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

    def test_filter_keeps_runs_at_or_above_floor(self) -> None:
        first = self._record_finish(5, "pr217-finish")
        second = self._record_draw_finish(5, "pr217-draw")
        low = min(int(first["xp"]), int(second["xp"]))
        high = max(int(first["xp"]), int(second["xp"]))
        filtered = trait_lab_seed_history_by_xp_floor(self.store, 5, low)
        self.assertEqual(filtered["seed"], 5)
        self.assertEqual(filtered["floor"], low)
        self.assertGreaterEqual(filtered["count"], 1)
        self.assertTrue(all(int(row["xp"] or 0) >= low for row in filtered["runs"]))
        self.assertEqual(filtered["best"]["xp"], high)
        self.assertFalse(filtered["live_verified"])
        tight = trait_lab_seed_history_by_xp_floor(self.store, 5, high)
        self.assertTrue(all(int(row["xp"] or 0) >= high for row in tight["runs"]))

    def test_filter_excludes_other_seeds(self) -> None:
        proof = self._record_finish(1, "pr217-a")
        self._record_finish(2, "pr217-b")
        filtered = trait_lab_seed_history_by_xp_floor(self.store, 1, int(proof["xp"]))
        self.assertEqual(filtered["count"], 1)
        self.assertEqual(filtered["runs"][0]["seed"], 1)

    def test_missing_and_invalid_inputs(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            trait_lab_seed_history_by_xp_floor(self.store, 99, 0)
        self.assertEqual(err.exception.code, "missing_seed")
        proof = self._record_finish(3, "pr217-c")
        with self.assertRaises(MemoryLayerError) as err2:
            trait_lab_seed_history_by_xp_floor(self.store, 3, int(proof["xp"]) + 1)
        self.assertEqual(err2.exception.code, "missing_floor")
        with self.assertRaises(MemoryLayerError) as err3:
            trait_lab_seed_history_by_xp_floor(self.store, 3, "nope")  # type: ignore[arg-type]
        self.assertEqual(err3.exception.code, "invalid_floor")
        with self.assertRaises(MemoryLayerError) as err4:
            trait_lab_seed_history_by_xp_floor(self.store, 3, -1)
        self.assertEqual(err4.exception.code, "invalid_floor")
        with self.assertRaises(MemoryLayerError) as err5:
            trait_lab_seed_history_by_xp_floor(self.store, 3, 0, limit=0)
        self.assertEqual(err5.exception.code, "invalid_limit")


if __name__ == "__main__":
    unittest.main()
