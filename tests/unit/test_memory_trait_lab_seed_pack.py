"""Hermetic tests for Trait Lab seed pack export (PR #220)."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    record_trait_lab_run,
    export_trait_lab_seed_pack,
    trait_lab_seed_history,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabSeedPack(unittest.TestCase):
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

    def test_export_matches_history_and_is_not_live(self) -> None:
        self._record_finish(5, "pr220-a")
        history = trait_lab_seed_history(self.store, 5)
        pack = export_trait_lab_seed_pack(self.store, 5)
        self.assertEqual(pack["kind"], "trait-lab-seed-pack")
        self.assertEqual(pack["seed"], 5)
        self.assertEqual(pack["count"], history["count"])
        self.assertEqual(pack["best"]["proof_sha256"], history["best"]["proof_sha256"])
        self.assertEqual(len(pack["runs"]), len(history["runs"]))
        self.assertFalse(pack["live_verified"])
        self.assertEqual(len(pack["pack_sha256"]), 64)
        body = {
            "kind": pack["kind"],
            "seed": pack["seed"],
            "count": pack["count"],
            "best": pack["best"],
            "runs": pack["runs"],
            "live_verified": False,
        }
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.assertEqual(pack["pack_sha256"], hashlib.sha256(encoded).hexdigest())
        self.assertIn("exported_at", pack)

    def test_export_excludes_other_seeds(self) -> None:
        self._record_finish(1, "pr220-b")
        self._record_finish(2, "pr220-c")
        pack = export_trait_lab_seed_pack(self.store, 1)
        self.assertEqual(pack["count"], 1)
        self.assertEqual(pack["runs"][0]["seed"], 1)

    def test_missing_and_invalid_inputs(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            export_trait_lab_seed_pack(self.store, 99)
        self.assertEqual(err.exception.code, "missing_seed")
        self._record_finish(3, "pr220-d")
        with self.assertRaises(MemoryLayerError) as err2:
            export_trait_lab_seed_pack(self.store, 3, limit=0)
        self.assertEqual(err2.exception.code, "invalid_limit")
        with self.assertRaises(MemoryLayerError) as err3:
            export_trait_lab_seed_pack(self.store, "nope")  # type: ignore[arg-type]
        self.assertEqual(err3.exception.code, "invalid_seed")


if __name__ == "__main__":
    unittest.main()
