"""Hermetic tests for Trait Lab seed history grade filter (PR #213)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    record_trait_lab_run,
    trait_lab_seed_history_by_grade,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabSeedGrade(unittest.TestCase):
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

    def test_filter_keeps_matching_grade(self) -> None:
        proof = self._record_finish(5, "pr213-finish")
        grade = str(proof["grade"])
        filtered = trait_lab_seed_history_by_grade(self.store, 5, grade)
        self.assertEqual(filtered["seed"], 5)
        self.assertEqual(filtered["grade"], grade.upper())
        self.assertGreaterEqual(filtered["count"], 1)
        self.assertTrue(all(str(row["grade"]).upper() == grade.upper() for row in filtered["runs"]))
        self.assertEqual(filtered["best"]["grade"].upper(), grade.upper())
        self.assertFalse(filtered["live_verified"])

    def test_filter_excludes_other_seeds(self) -> None:
        first = self._record_finish(1, "pr213-a")
        self._record_finish(2, "pr213-b")
        filtered = trait_lab_seed_history_by_grade(self.store, 1, first["grade"])
        self.assertEqual(filtered["count"], 1)
        self.assertEqual(filtered["runs"][0]["seed"], 1)

    def test_missing_and_invalid_inputs(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            trait_lab_seed_history_by_grade(self.store, 99, "D")
        self.assertEqual(err.exception.code, "missing_seed")
        proof = self._record_finish(3, "pr213-c")
        missing = "S" if str(proof["grade"]).upper() != "S" else "A"
        with self.assertRaises(MemoryLayerError) as err2:
            trait_lab_seed_history_by_grade(self.store, 3, missing)
        self.assertEqual(err2.exception.code, "missing_grade")
        with self.assertRaises(MemoryLayerError) as err3:
            trait_lab_seed_history_by_grade(self.store, 3, "")
        self.assertEqual(err3.exception.code, "invalid_grade")
        with self.assertRaises(MemoryLayerError) as err4:
            trait_lab_seed_history_by_grade(self.store, 3, "Z")
        self.assertEqual(err4.exception.code, "invalid_grade")
        with self.assertRaises(MemoryLayerError) as err5:
            trait_lab_seed_history_by_grade(self.store, 3, proof["grade"], limit=0)
        self.assertEqual(err5.exception.code, "invalid_limit")


if __name__ == "__main__":
    unittest.main()
