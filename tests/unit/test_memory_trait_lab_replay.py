"""Hermetic tests for Trait Lab replay verify (PR #207)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    record_trait_lab_replay,
    record_trait_lab_run,
    verify_trait_lab_replay,
    write_verified,
)
from thinkbox.trait_game.engine import act, encode_replay, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabReplay(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "layers.db")
        self.rules = load_rules()

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def _state(self) -> dict:
        return act(self.rules, new_run(self.rules, seed=42, difficulty="lab"), "finish")["state"]

    def test_record_and_verify_replay(self) -> None:
        state = self._state()
        recorded = record_trait_lab_replay(
            self.store,
            state,
            agent_id="unit",
            task_id="pr207-replay",
        )
        self.assertFalse(recorded["live_verified"])
        self.assertIn("|", recorded["replay"])
        checked = verify_trait_lab_replay(self.store, recorded["proof_sha256"], self.rules)
        self.assertTrue(checked["matched"])
        self.assertEqual(checked["proof_sha256"], recorded["proof_sha256"])
        self.assertFalse(checked["live_verified"])

    def test_verify_without_replay_fails(self) -> None:
        state = self._state()
        proof = proof_scorecard(state)
        record_trait_lab_run(self.store, proof, agent_id="unit", task_id="pr207-proof-only")
        with self.assertRaises(MemoryLayerError) as err:
            verify_trait_lab_replay(self.store, proof["proof_sha256"], self.rules)
        self.assertEqual(err.exception.code, "missing_verified")

    def test_proof_mismatch_fails(self) -> None:
        state = self._state()
        recorded = record_trait_lab_replay(
            self.store,
            state,
            agent_id="unit",
            task_id="pr207-mismatch",
        )
        other = act(self.rules, new_run(self.rules, seed=1, difficulty="lab"), "finish")["state"]
        write_verified(
            self.store,
            {
                "id": f"trait-lab-replay-{recorded['proof_sha256'][:16]}",
                "fact": encode_replay(other),
                "how": "tamper",
                "corrects": recorded["proof_sha256"],
                "source": recorded["proof_sha256"],
                "agent_id": "unit",
                "task_id": "pr207-mismatch",
            },
        )
        with self.assertRaises(MemoryLayerError) as err:
            verify_trait_lab_replay(self.store, recorded["proof_sha256"], self.rules)
        self.assertEqual(err.exception.code, "proof_mismatch")

    def test_live_state_rejected(self) -> None:
        state = self._state()
        state["live_verified"] = True
        with self.assertRaises(MemoryLayerError) as err:
            record_trait_lab_replay(self.store, state, agent_id="unit", task_id="pr207")
        self.assertEqual(err.exception.code, "live_claim")

    def test_verify_requires_hash(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            verify_trait_lab_replay(self.store, "short", self.rules)
        self.assertEqual(err.exception.code, "missing_proof")


if __name__ == "__main__":
    unittest.main()
