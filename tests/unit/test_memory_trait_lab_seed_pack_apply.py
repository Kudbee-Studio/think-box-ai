"""Hermetic tests for Trait Lab seed pack apply (PR #222)."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    apply_trait_lab_seed_pack,
    export_trait_lab_seed_pack,
    record_trait_lab_run,
    trait_lab_seed_history,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabSeedPackApply(unittest.TestCase):
    def setUp(self) -> None:
        self.src_tmp = tempfile.TemporaryDirectory()
        self.dst_tmp = tempfile.TemporaryDirectory()
        self.src = MemoryStore(Path(self.src_tmp.name) / "src.db")
        self.dst = MemoryStore(Path(self.dst_tmp.name) / "dst.db")
        self.rules = load_rules()

    def tearDown(self) -> None:
        self.src.close()
        self.dst.close()
        self.src_tmp.cleanup()
        self.dst_tmp.cleanup()

    def _record_finish(self, seed: int, task_id: str) -> dict:
        state = act(self.rules, new_run(self.rules, seed=seed, difficulty="lab"), "finish")["state"]
        proof = proof_scorecard(state)
        record_trait_lab_run(self.src, proof, agent_id="unit", task_id=task_id)
        return proof

    def _signed_pack(self, seed: int, runs: list[dict]) -> dict:
        body = {
            "kind": "trait-lab-seed-pack",
            "seed": seed,
            "count": len(runs),
            "best": runs[0] if runs else {},
            "runs": runs,
            "live_verified": False,
        }
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {**body, "pack_sha256": hashlib.sha256(encoded).hexdigest()}

    def test_apply_writes_runs_into_destination(self) -> None:
        self._record_finish(5, "pr222-a")
        pack = export_trait_lab_seed_pack(self.src, 5)
        applied = apply_trait_lab_seed_pack(
            self.dst, pack, agent_id="unit", task_id="pr222-apply"
        )
        self.assertTrue(applied["applied"])
        self.assertEqual(applied["seed"], 5)
        self.assertEqual(applied["count"], 1)
        self.assertFalse(applied["live_verified"])
        history = trait_lab_seed_history(self.dst, 5)
        self.assertEqual(history["count"], 1)
        self.assertEqual(history["best"]["proof_sha256"], pack["runs"][0]["proof_sha256"])
        self.assertFalse(history["live_verified"])

    def test_live_claim_and_pack_mismatch(self) -> None:
        self._record_finish(4, "pr222-b")
        pack = export_trait_lab_seed_pack(self.src, 4)
        live = dict(pack)
        live["live_verified"] = True
        with self.assertRaises(MemoryLayerError) as err:
            apply_trait_lab_seed_pack(self.dst, live, agent_id="unit", task_id="pr222-live")
        self.assertEqual(err.exception.code, "live_claim")
        tampered = dict(pack)
        tampered["count"] = int(pack["count"]) + 1
        with self.assertRaises(MemoryLayerError) as err2:
            apply_trait_lab_seed_pack(self.dst, tampered, agent_id="unit", task_id="pr222-mismatch")
        self.assertEqual(err2.exception.code, "pack_mismatch")

    def test_invalid_run_and_missing_provenance(self) -> None:
        pack = self._signed_pack(
            3,
            [{"proof_sha256": "abc", "seed": 3, "fact": "seed 3 xp=0 grade=D", "xp": 0}],
        )
        with self.assertRaises(MemoryLayerError) as err:
            apply_trait_lab_seed_pack(self.dst, pack, agent_id="unit", task_id="pr222-run")
        self.assertEqual(err.exception.code, "invalid_run")
        empty = self._signed_pack(3, [])
        with self.assertRaises(MemoryLayerError) as err2:
            apply_trait_lab_seed_pack(self.dst, empty, agent_id="unit", task_id="pr222-empty")
        self.assertEqual(err2.exception.code, "missing_run")
        self._record_finish(2, "pr222-c")
        good = export_trait_lab_seed_pack(self.src, 2)
        with self.assertRaises(MemoryLayerError) as err3:
            apply_trait_lab_seed_pack(self.dst, good, agent_id="", task_id="pr222-d")
        self.assertEqual(err3.exception.code, "missing_provenance")


if __name__ == "__main__":
    unittest.main()
