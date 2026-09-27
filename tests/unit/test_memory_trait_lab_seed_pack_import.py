"""Hermetic tests for Trait Lab seed pack verify/import (PR #221)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    export_trait_lab_seed_pack,
    import_trait_lab_seed_pack,
    read_verified,
    record_trait_lab_run,
    verify_trait_lab_seed_pack,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabSeedPackImport(unittest.TestCase):
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

    def test_verify_rematch_and_import_writes(self) -> None:
        self._record_finish(5, "pr221-a")
        pack = export_trait_lab_seed_pack(self.store, 5)
        verified = verify_trait_lab_seed_pack(pack)
        self.assertTrue(verified["matched"])
        self.assertEqual(verified["seed"], 5)
        self.assertEqual(verified["pack_sha256"], pack["pack_sha256"])
        self.assertFalse(verified["live_verified"])
        imported = import_trait_lab_seed_pack(
            self.store, pack, agent_id="unit", task_id="pr221-import"
        )
        self.assertTrue(imported["imported"])
        self.assertEqual(imported["fact_id"], f"trait-lab-pack-{pack['pack_sha256'][:16]}")
        viewed = read_verified(self.store, imported["fact_id"])
        self.assertIn("pack=", str(viewed["fact"]))
        self.assertFalse(imported["live_verified"])

    def test_live_claim_and_pack_mismatch(self) -> None:
        self._record_finish(4, "pr221-b")
        pack = export_trait_lab_seed_pack(self.store, 4)
        live = dict(pack)
        live["live_verified"] = True
        with self.assertRaises(MemoryLayerError) as err:
            verify_trait_lab_seed_pack(live)
        self.assertEqual(err.exception.code, "live_claim")
        tampered = dict(pack)
        tampered["count"] = int(pack["count"]) + 1
        with self.assertRaises(MemoryLayerError) as err2:
            verify_trait_lab_seed_pack(tampered)
        self.assertEqual(err2.exception.code, "pack_mismatch")

    def test_invalid_pack_and_missing_hash(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            verify_trait_lab_seed_pack("nope")  # type: ignore[arg-type]
        self.assertEqual(err.exception.code, "invalid_pack")
        with self.assertRaises(MemoryLayerError) as err2:
            verify_trait_lab_seed_pack({"kind": "other", "seed": 1, "count": 1, "best": {}, "runs": []})
        self.assertEqual(err2.exception.code, "invalid_pack")
        self._record_finish(3, "pr221-c")
        pack = export_trait_lab_seed_pack(self.store, 3)
        missing = dict(pack)
        missing.pop("pack_sha256")
        with self.assertRaises(MemoryLayerError) as err3:
            verify_trait_lab_seed_pack(missing)
        self.assertEqual(err3.exception.code, "missing_pack_hash")
        short = dict(pack)
        short["pack_sha256"] = "abc"
        with self.assertRaises(MemoryLayerError) as err4:
            verify_trait_lab_seed_pack(short)
        self.assertEqual(err4.exception.code, "missing_pack_hash")
        with self.assertRaises(MemoryLayerError) as err5:
            import_trait_lab_seed_pack(self.store, pack, agent_id="", task_id="pr221-d")
        self.assertEqual(err5.exception.code, "missing_provenance")


if __name__ == "__main__":
    unittest.main()
