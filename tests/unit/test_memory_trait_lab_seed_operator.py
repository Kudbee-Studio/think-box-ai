"""Hermetic tests for Trait Lab seed history operator filter (PR #215)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    record_trait_lab_run,
    trait_lab_seed_history_by_operator,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabSeedOperator(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "layers.db")
        self.rules = load_rules()

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def _record_finish(self, seed: int, task_id: str, operator: str) -> dict:
        state = act(
            self.rules,
            new_run(self.rules, seed=seed, difficulty="lab", operator=operator),
            "finish",
        )["state"]
        proof = proof_scorecard(state)
        record_trait_lab_run(self.store, proof, agent_id="unit", task_id=task_id)
        return proof

    def test_filter_keeps_matching_operator(self) -> None:
        first = self._record_finish(5, "pr215-ada", "ada")
        second = self._record_finish(5, "pr215-bev", "bev")
        filtered = trait_lab_seed_history_by_operator(self.store, 5, "ada")
        self.assertEqual(filtered["seed"], 5)
        self.assertEqual(filtered["operator"], "ada")
        self.assertEqual(filtered["count"], 1)
        self.assertEqual(filtered["runs"][0]["operator"], "ada")
        self.assertEqual(filtered["best"]["proof_sha256"], first["proof_sha256"])
        self.assertFalse(filtered["live_verified"])
        other = trait_lab_seed_history_by_operator(self.store, 5, "bev")
        self.assertEqual(other["count"], 1)
        self.assertEqual(other["best"]["proof_sha256"], second["proof_sha256"])

    def test_filter_excludes_other_seeds(self) -> None:
        self._record_finish(1, "pr215-a", "ada")
        self._record_finish(2, "pr215-b", "ada")
        filtered = trait_lab_seed_history_by_operator(self.store, 1, "ada")
        self.assertEqual(filtered["count"], 1)
        self.assertEqual(filtered["runs"][0]["seed"], 1)

    def test_missing_and_invalid_inputs(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            trait_lab_seed_history_by_operator(self.store, 99, "ada")
        self.assertEqual(err.exception.code, "missing_seed")
        self._record_finish(3, "pr215-c", "ada")
        with self.assertRaises(MemoryLayerError) as err2:
            trait_lab_seed_history_by_operator(self.store, 3, "bev")
        self.assertEqual(err2.exception.code, "missing_operator")
        with self.assertRaises(MemoryLayerError) as err3:
            trait_lab_seed_history_by_operator(self.store, 3, "")
        self.assertEqual(err3.exception.code, "invalid_operator")
        with self.assertRaises(MemoryLayerError) as err4:
            trait_lab_seed_history_by_operator(self.store, 3, "Ada Lovelace")
        self.assertEqual(err4.exception.code, "invalid_operator")
        with self.assertRaises(MemoryLayerError) as err5:
            trait_lab_seed_history_by_operator(self.store, 3, "ada", limit=0)
        self.assertEqual(err5.exception.code, "invalid_limit")


if __name__ == "__main__":
    unittest.main()
