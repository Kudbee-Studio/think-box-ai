"""Hermetic tests for the local Trait Lab board (PR #209)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import MemoryLayerError, board_trait_lab_runs, record_trait_lab_run
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabBoard(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "layers.db")
        self.rules = load_rules()

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def _record(self, seed: int, task_id: str) -> dict:
        state = act(self.rules, new_run(self.rules, seed=seed, difficulty="lab"), "finish")["state"]
        proof = proof_scorecard(state)
        record_trait_lab_run(self.store, proof, agent_id="unit", task_id=task_id)
        return proof

    def test_empty_board_is_not_live(self) -> None:
        board = board_trait_lab_runs(self.store)
        self.assertEqual(board["count"], 0)
        self.assertEqual(board["board"], [])
        self.assertFalse(board["live_verified"])

    def test_board_orders_by_xp(self) -> None:
        self._record(2, "pr209-a")
        self._record(11, "pr209-b")
        board = board_trait_lab_runs(self.store, limit=10)
        self.assertEqual(board["count"], 2)
        self.assertEqual(len(board["board"]), 2)
        xp_values = [int(row["xp"]) for row in board["board"]]
        self.assertEqual(xp_values, sorted(xp_values, reverse=True))
        self.assertFalse(board["live_verified"])
        self.assertIn("proof_sha256", board["board"][0])

    def test_board_respects_limit(self) -> None:
        self._record(3, "pr209-c")
        self._record(8, "pr209-d")
        board = board_trait_lab_runs(self.store, limit=1)
        self.assertEqual(len(board["board"]), 1)
        self.assertEqual(board["count"], 2)

    def test_invalid_limit(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            board_trait_lab_runs(self.store, limit=0)
        self.assertEqual(err.exception.code, "invalid_limit")


if __name__ == "__main__":
    unittest.main()
