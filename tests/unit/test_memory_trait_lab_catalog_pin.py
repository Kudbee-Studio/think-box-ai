"""Hermetic tests for Trait Lab catalog pin (persist rematched catalog snapshots)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    count_trait_lab_seed_packs,
    export_trait_lab_seed_pack,
    export_trait_lab_seed_pack_catalog,
    get_trait_lab_catalog_pin,
    has_trait_lab_catalog_pin,
    import_trait_lab_seed_pack,
    list_trait_lab_catalog_pins,
    pin_trait_lab_seed_pack_catalog,
    record_trait_lab_run,
    unpin_trait_lab_catalog_pin,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabCatalogPin(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "layers.db")
        self.rules = load_rules()

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def _import_seed(self, seed: int, task_id: str) -> dict:
        state = act(self.rules, new_run(self.rules, seed=seed, difficulty="lab"), "finish")["state"]
        proof = proof_scorecard(state)
        record_trait_lab_run(self.store, proof, agent_id="unit", task_id=task_id)
        pack = export_trait_lab_seed_pack(self.store, seed)
        import_trait_lab_seed_pack(self.store, pack, agent_id="unit", task_id=f"imp-{task_id}")
        return pack

    def test_pin_get_and_list(self) -> None:
        pack = self._import_seed(1, "pin-a")
        catalog = export_trait_lab_seed_pack_catalog(self.store)
        pinned = pin_trait_lab_seed_pack_catalog(
            self.store, catalog, agent_id="unit", task_id="pin-write"
        )
        self.assertTrue(pinned["pinned"])
        self.assertEqual(pinned["count"], 1)
        self.assertEqual(pinned["ids"], [pack["pack_sha256"]])
        self.assertFalse(pinned["live_verified"])
        got = get_trait_lab_catalog_pin(self.store, catalog["catalog_sha256"])
        self.assertEqual(got["catalog_sha256"], catalog["catalog_sha256"])
        self.assertEqual(got["count"], 1)
        self.assertTrue(has_trait_lab_catalog_pin(self.store, catalog["catalog_sha256"]))
        listed = list_trait_lab_catalog_pins(self.store)
        self.assertEqual(listed["count"], 1)
        self.assertEqual(listed["pins"][0]["catalog_sha256"], catalog["catalog_sha256"])
        self.assertFalse(listed["live_verified"])

    def test_unpin_keeps_pack_facts(self) -> None:
        self._import_seed(2, "pin-b")
        catalog = export_trait_lab_seed_pack_catalog(self.store)
        pin_trait_lab_seed_pack_catalog(self.store, catalog, agent_id="unit", task_id="pin-keep")
        dropped = unpin_trait_lab_catalog_pin(self.store, catalog["catalog_sha256"])
        self.assertTrue(dropped["unpinned"])
        self.assertFalse(has_trait_lab_catalog_pin(self.store, catalog["catalog_sha256"]))
        self.assertEqual(count_trait_lab_seed_packs(self.store), 1)

    def test_live_claim_and_missing_provenance(self) -> None:
        self._import_seed(3, "pin-c")
        catalog = export_trait_lab_seed_pack_catalog(self.store)
        live = dict(catalog)
        live["live_verified"] = True
        with self.assertRaises(MemoryLayerError) as err:
            pin_trait_lab_seed_pack_catalog(self.store, live, agent_id="unit", task_id="pin-live")
        self.assertEqual(err.exception.code, "live_claim")
        with self.assertRaises(MemoryLayerError) as err2:
            pin_trait_lab_seed_pack_catalog(self.store, catalog, agent_id="", task_id="pin-d")
        self.assertEqual(err2.exception.code, "missing_provenance")

    def test_missing_pin_and_invalid_hash(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            get_trait_lab_catalog_pin(self.store, "ab" * 32)
        self.assertEqual(err.exception.code, "missing_pin")
        with self.assertRaises(MemoryLayerError) as err2:
            has_trait_lab_catalog_pin(self.store, "nope")
        self.assertEqual(err2.exception.code, "missing_catalog_hash")
        with self.assertRaises(MemoryLayerError) as err3:
            unpin_trait_lab_catalog_pin(self.store, "cd" * 32)
        self.assertEqual(err3.exception.code, "missing_pin")

    def test_invalid_catalog_and_empty_list(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            pin_trait_lab_seed_pack_catalog(
                self.store, "nope", agent_id="unit", task_id="pin-bad"
            )
        self.assertEqual(err.exception.code, "invalid_catalog")
        listed = list_trait_lab_catalog_pins(self.store)
        self.assertEqual(listed["count"], 0)
        self.assertEqual(listed["pins"], [])
        self.assertFalse(listed["live_verified"])


if __name__ == "__main__":
    unittest.main()
