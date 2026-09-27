"""Hermetic tests for Trait Lab seed history daily filter (PR #216)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    record_trait_lab_run,
    trait_lab_seed_history_by_daily,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabSeedDaily(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "layers.db")
        self.rules = load_rules()

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def _record_finish(self, seed: int, task_id: str, *, daily: bool) -> dict:
        state = act(
            self.rules,
            new_run(self.rules, seed=seed, difficulty="lab", daily=daily),
            "finish",
        )["state"]
        proof = proof_scorecard(state)
        record_trait_lab_run(self.store, proof, agent_id="unit", task_id=task_id)
        return proof

    def test_filter_keeps_matching_daily_flag(self) -> None:
        daily = self._record_finish(5, "pr216-daily", daily=True)
        off = self._record_finish(5, "pr216-off", daily=False)
        filtered = trait_lab_seed_history_by_daily(self.store, 5, True)
        self.assertEqual(filtered["seed"], 5)
        self.assertTrue(filtered["daily"])
        self.assertEqual(filtered["count"], 1)
        self.assertTrue(filtered["runs"][0]["daily"])
        self.assertEqual(filtered["best"]["proof_sha256"], daily["proof_sha256"])
        self.assertFalse(filtered["live_verified"])
        other = trait_lab_seed_history_by_daily(self.store, 5, False)
        self.assertEqual(other["count"], 1)
        self.assertFalse(other["daily"])
        self.assertEqual(other["best"]["proof_sha256"], off["proof_sha256"])

    def test_filter_excludes_other_seeds(self) -> None:
        self._record_finish(1, "pr216-a", daily=True)
        self._record_finish(2, "pr216-b", daily=True)
        filtered = trait_lab_seed_history_by_daily(self.store, 1, True)
        self.assertEqual(filtered["count"], 1)
        self.assertEqual(filtered["runs"][0]["seed"], 1)

    def test_missing_and_invalid_inputs(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            trait_lab_seed_history_by_daily(self.store, 99, True)
        self.assertEqual(err.exception.code, "missing_seed")
        self._record_finish(3, "pr216-c", daily=False)
        with self.assertRaises(MemoryLayerError) as err2:
            trait_lab_seed_history_by_daily(self.store, 3, True)
        self.assertEqual(err2.exception.code, "missing_daily")
        with self.assertRaises(MemoryLayerError) as err3:
            trait_lab_seed_history_by_daily(self.store, 3, "yes")  # type: ignore[arg-type]
        self.assertEqual(err3.exception.code, "invalid_daily")
        with self.assertRaises(MemoryLayerError) as err4:
            trait_lab_seed_history_by_daily(self.store, 3, None)  # type: ignore[arg-type]
        self.assertEqual(err4.exception.code, "invalid_daily")
        with self.assertRaises(MemoryLayerError) as err5:
            trait_lab_seed_history_by_daily(self.store, 3, False, limit=0)
        self.assertEqual(err5.exception.code, "invalid_limit")


if __name__ == "__main__":
    unittest.main()
