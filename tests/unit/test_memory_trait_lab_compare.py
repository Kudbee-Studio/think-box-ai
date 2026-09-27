"""Hermetic tests for Trait Lab run index and compare (PR #208)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    compare_trait_lab_runs,
    list_trait_lab_runs,
    record_trait_lab_replay,
    record_trait_lab_run,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabCompare(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "layers.db")
        self.rules = load_rules()

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def _proof(self, seed: int) -> dict:
        state = act(self.rules, new_run(self.rules, seed=seed, difficulty="lab"), "finish")["state"]
        return proof_scorecard(state)

    def test_list_skips_replay_rows(self) -> None:
        state = act(self.rules, new_run(self.rules, seed=7, difficulty="lab"), "finish")["state"]
        record_trait_lab_replay(self.store, state, agent_id="unit", task_id="pr208-list")
        runs = list_trait_lab_runs(self.store)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["seed"], 7)
        self.assertFalse(runs[0]["live_verified"])
        self.assertIsInstance(runs[0]["xp"], int)

    def test_compare_two_seeds(self) -> None:
        a = self._proof(3)
        b = self._proof(9)
        record_trait_lab_run(self.store, a, agent_id="unit", task_id="pr208-a")
        record_trait_lab_run(self.store, b, agent_id="unit", task_id="pr208-b")
        compared = compare_trait_lab_runs(self.store, a["proof_sha256"], b["proof_sha256"])
        self.assertFalse(compared["same_seed"])
        self.assertEqual(compared["xp_delta"], int(a["xp"]) - int(b["xp"]))
        self.assertFalse(compared["live_verified"])

    def test_compare_same_run_rejected(self) -> None:
        proof = self._proof(4)
        record_trait_lab_run(self.store, proof, agent_id="unit", task_id="pr208-same")
        with self.assertRaises(MemoryLayerError) as err:
            compare_trait_lab_runs(self.store, proof["proof_sha256"], proof["proof_sha256"])
        self.assertEqual(err.exception.code, "same_run")

    def test_compare_missing_and_short_hash(self) -> None:
        proof = self._proof(5)
        record_trait_lab_run(self.store, proof, agent_id="unit", task_id="pr208-miss")
        other = "ab" * 32
        with self.assertRaises(MemoryLayerError) as err:
            compare_trait_lab_runs(self.store, proof["proof_sha256"], other)
        self.assertEqual(err.exception.code, "missing_verified")
        with self.assertRaises(MemoryLayerError) as err2:
            compare_trait_lab_runs(self.store, "short", "also-short")
        self.assertEqual(err2.exception.code, "missing_proof")

    def test_list_invalid_limit(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            list_trait_lab_runs(self.store, limit=0)
        self.assertEqual(err.exception.code, "invalid_limit")


if __name__ == "__main__":
    unittest.main()
