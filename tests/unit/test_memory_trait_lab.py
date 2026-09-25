"""Hermetic tests for Trait Lab → four-layer ledger (PR #206)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.schema import MemoryLayer
from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    query_by_provenance,
    read_organizational,
    read_session,
    read_verified,
    record_trait_lab_run,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabLedger(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "layers.db")
        self.rules = load_rules()

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def _proof(self) -> dict:
        state = act(self.rules, new_run(self.rules, seed=42, difficulty="lab"), "finish")["state"]
        return proof_scorecard(state)

    def test_record_run_writes_all_four_layers(self) -> None:
        proof = self._proof()
        result = record_trait_lab_run(
            self.store,
            proof,
            agent_id="unit",
            task_id="pr206-trait-lab",
        )
        self.assertFalse(result["live_verified"])
        self.assertEqual(result["proof_sha256"], proof["proof_sha256"])
        session = read_session(self.store, result["session_id"])
        self.assertEqual(session.value["source"], proof["proof_sha256"])
        viewed = read_verified(self.store, f"trait-lab-{proof['proof_sha256'][:16]}")
        self.assertIn("xp=", viewed["fact"])
        self.assertFalse(viewed["live_verified"])
        org = read_organizational(self.store, f"trait-lab-seed-{proof['seed']}")
        self.assertIn(proof["proof_sha256"], org.value["evidence"])
        self.assertGreaterEqual(self.store.count(MemoryLayer.TASK), 1)

    def test_query_by_provenance(self) -> None:
        proof = self._proof()
        record_trait_lab_run(self.store, proof, agent_id="unit", task_id="pr206-trait-lab")
        rows = query_by_provenance(self.store, agent_id="unit", task_id="pr206-trait-lab")
        self.assertGreaterEqual(len(rows), 4)
        sourced = query_by_provenance(self.store, source=proof["proof_sha256"])
        self.assertGreaterEqual(len(sourced), 3)

    def test_reject_live_claim(self) -> None:
        proof = self._proof()
        proof["live_verified"] = True
        with self.assertRaises(MemoryLayerError) as err:
            record_trait_lab_run(self.store, proof, agent_id="unit", task_id="pr206")
        self.assertEqual(err.exception.code, "live_claim")

    def test_reject_missing_proof_and_provenance(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            record_trait_lab_run(self.store, {"game_id": "trait-lab"}, agent_id="unit", task_id="pr206")
        self.assertEqual(err.exception.code, "missing_proof")
        proof = self._proof()
        with self.assertRaises(MemoryLayerError) as err2:
            record_trait_lab_run(self.store, proof, agent_id="", task_id="pr206")
        self.assertEqual(err2.exception.code, "missing_provenance")

    def test_reject_wrong_game(self) -> None:
        proof = self._proof()
        proof["game_id"] = "other"
        with self.assertRaises(MemoryLayerError) as err:
            record_trait_lab_run(self.store, proof, agent_id="unit", task_id="pr206")
        self.assertEqual(err.exception.code, "wrong_game")


if __name__ == "__main__":
    unittest.main()
