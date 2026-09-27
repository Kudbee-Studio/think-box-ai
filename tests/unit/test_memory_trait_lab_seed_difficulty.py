"""Hermetic tests for Trait Lab seed history difficulty filter (PR #214)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    record_trait_lab_run,
    trait_lab_seed_history_by_difficulty,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabSeedDifficulty(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "layers.db")
        self.rules = load_rules()

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def _record_finish(self, seed: int, task_id: str, difficulty: str = "lab") -> dict:
        state = act(
            self.rules,
            new_run(self.rules, seed=seed, difficulty=difficulty),
            "finish",
        )["state"]
        proof = proof_scorecard(state)
        record_trait_lab_run(self.store, proof, agent_id="unit", task_id=task_id)
        return proof

    def test_filter_keeps_matching_difficulty(self) -> None:
        lab = self._record_finish(5, "pr214-lab", "lab")
        thesis = self._record_finish(5, "pr214-thesis", "thesis")
        filtered = trait_lab_seed_history_by_difficulty(self.store, 5, "lab")
        self.assertEqual(filtered["seed"], 5)
        self.assertEqual(filtered["difficulty"], "lab")
        self.assertEqual(filtered["count"], 1)
        self.assertEqual(filtered["runs"][0]["difficulty"], "lab")
        self.assertEqual(filtered["best"]["proof_sha256"], lab["proof_sha256"])
        self.assertFalse(filtered["live_verified"])
        other = trait_lab_seed_history_by_difficulty(self.store, 5, "THESIS")
        self.assertEqual(other["count"], 1)
        self.assertEqual(other["best"]["proof_sha256"], thesis["proof_sha256"])

    def test_filter_excludes_other_seeds(self) -> None:
        self._record_finish(1, "pr214-a", "lab")
        self._record_finish(2, "pr214-b", "lab")
        filtered = trait_lab_seed_history_by_difficulty(self.store, 1, "lab")
        self.assertEqual(filtered["count"], 1)
        self.assertEqual(filtered["runs"][0]["seed"], 1)

    def test_missing_and_invalid_inputs(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            trait_lab_seed_history_by_difficulty(self.store, 99, "lab")
        self.assertEqual(err.exception.code, "missing_seed")
        self._record_finish(3, "pr214-c", "lab")
        with self.assertRaises(MemoryLayerError) as err2:
            trait_lab_seed_history_by_difficulty(self.store, 3, "thesis")
        self.assertEqual(err2.exception.code, "missing_difficulty")
        with self.assertRaises(MemoryLayerError) as err3:
            trait_lab_seed_history_by_difficulty(self.store, 3, "")
        self.assertEqual(err3.exception.code, "invalid_difficulty")
        with self.assertRaises(MemoryLayerError) as err4:
            trait_lab_seed_history_by_difficulty(self.store, 3, "arcade")
        self.assertEqual(err4.exception.code, "invalid_difficulty")
        with self.assertRaises(MemoryLayerError) as err5:
            trait_lab_seed_history_by_difficulty(self.store, 3, "lab", limit=0)
        self.assertEqual(err5.exception.code, "invalid_limit")


if __name__ == "__main__":
    unittest.main()
