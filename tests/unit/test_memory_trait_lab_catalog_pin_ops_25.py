"""Hermetic tests for Trait Lab catalog pin operator pack P01–P25."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.schema import MemoryEntry, MemoryEntryType, MemoryLayer
from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    TRAIT_LAB_CATALOG_PIN_OPS,
    best_trait_lab_catalog_pin,
    catalog_pin_has_count,
    catalog_pin_has_pack,
    catalog_trait_lab_pin_etag,
    catalog_trait_lab_pins_by_agent,
    catalog_trait_lab_pins_by_count_band,
    catalog_trait_lab_pins_by_count_ceiling,
    catalog_trait_lab_pins_by_count_floor,
    catalog_trait_lab_pins_by_task,
    catalog_trait_lab_pins_digest,
    catalog_trait_lab_pins_page,
    count_trait_lab_catalog_pins,
    count_trait_lab_catalog_pins_for_pack,
    diff_trait_lab_catalog_pin_indexes,
    export_trait_lab_catalog_pins,
    export_trait_lab_seed_pack,
    export_trait_lab_seed_pack_catalog,
    get_trait_lab_catalog_pin,
    get_trait_lab_catalog_pin_by_fact_id,
    has_trait_lab_catalog_pin,
    import_trait_lab_catalog_pins,
    import_trait_lab_seed_pack,
    list_trait_lab_catalog_pin_ids,
    list_trait_lab_catalog_pin_ids_for_agent,
    list_trait_lab_catalog_pin_ids_for_pack,
    pin_trait_lab_seed_pack_catalog,
    pin_trait_lab_seed_pack_catalog_from_store,
    public_trait_lab_catalog_pin_row,
    record_trait_lab_run,
    refuse_trait_lab_catalog_pin_live,
    report_malformed_trait_lab_catalog_pins,
    verify_trait_lab_catalog_pins,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabCatalogPinOps25(unittest.TestCase):
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

    def _pin_current(self, task_id: str) -> dict:
        catalog = export_trait_lab_seed_pack_catalog(self.store)
        return pin_trait_lab_seed_pack_catalog(
            self.store, catalog, agent_id="unit", task_id=task_id
        )

    def test_p00_ops_catalog_has_25(self) -> None:
        self.assertEqual(len(TRAIT_LAB_CATALOG_PIN_OPS), 25)
        self.assertEqual(len(set(TRAIT_LAB_CATALOG_PIN_OPS)), 25)

    def test_p01_p02_list_ids_and_count(self) -> None:
        self.assertEqual(count_trait_lab_catalog_pins(self.store), 0)
        self._import_seed(1, "p01")
        pinned = self._pin_current("p01-pin")
        self.assertEqual(list_trait_lab_catalog_pin_ids(self.store), [pinned["catalog_sha256"]])
        self.assertEqual(count_trait_lab_catalog_pins(self.store), 1)

    def test_p03_page(self) -> None:
        self._import_seed(1, "p03a")
        self._pin_current("p03-pin-a")
        self._import_seed(2, "p03b")
        self._pin_current("p03-pin-b")
        page = catalog_trait_lab_pins_page(self.store, offset=1, limit=1)
        self.assertEqual(len(page["pins"]), 1)
        self.assertEqual(page["count"], 2)
        self.assertEqual(page["offset"], 1)

    def test_p04_p05_p25_by_agent_and_task(self) -> None:
        self._import_seed(3, "p04")
        pinned = self._pin_current("p04-pin")
        by_agent = catalog_trait_lab_pins_by_agent(self.store, "unit")
        self.assertEqual(by_agent["count"], 1)
        self.assertEqual(
            list_trait_lab_catalog_pin_ids_for_agent(self.store, "unit"),
            [pinned["catalog_sha256"]],
        )
        by_task = catalog_trait_lab_pins_by_task(self.store, "p04-pin")
        self.assertEqual(by_task["count"], 1)
        with self.assertRaises(MemoryLayerError) as err:
            catalog_trait_lab_pins_by_agent(self.store, "other")
        self.assertEqual(err.exception.code, "missing_agent")
        with self.assertRaises(MemoryLayerError) as err2:
            catalog_trait_lab_pins_by_task(self.store, "missing")
        self.assertEqual(err2.exception.code, "missing_task")

    def test_p06_p07_p08_count_bounds(self) -> None:
        self._import_seed(4, "p06")
        self._pin_current("p06-pin")
        self.assertEqual(catalog_trait_lab_pins_by_count_floor(self.store, 1)["count"], 1)
        self.assertEqual(catalog_trait_lab_pins_by_count_ceiling(self.store, 1)["count"], 1)
        self.assertEqual(catalog_trait_lab_pins_by_count_band(self.store, 1, 1)["count"], 1)
        with self.assertRaises(MemoryLayerError) as err:
            catalog_trait_lab_pins_by_count_floor(self.store, 9)
        self.assertEqual(err.exception.code, "missing_floor")
        with self.assertRaises(MemoryLayerError) as err2:
            catalog_trait_lab_pins_by_count_band(self.store, 3, 1)
        self.assertEqual(err2.exception.code, "invalid_band")

    def test_p09_p10_p11_p12_export_verify_digest(self) -> None:
        self._import_seed(5, "p09")
        self._pin_current("p09-pin")
        exported = export_trait_lab_catalog_pins(self.store)
        self.assertEqual(len(exported["pin_index_sha256"]), 64)
        self.assertEqual(catalog_trait_lab_pins_digest(self.store), exported["pin_index_sha256"])
        self.assertEqual(catalog_trait_lab_pin_etag(self.store), exported["pin_index_sha256"][:16])
        verified = verify_trait_lab_catalog_pins(exported)
        self.assertTrue(verified["matched"])
        tampered = dict(exported)
        changed = dict(exported["pins"][0])
        changed["count"] = int(changed["count"]) + 1
        tampered["pins"] = [changed]
        with self.assertRaises(MemoryLayerError) as err:
            verify_trait_lab_catalog_pins(tampered)
        self.assertEqual(err.exception.code, "pin_index_mismatch")

    def test_p13_import_index(self) -> None:
        self._import_seed(6, "p13")
        self._pin_current("p13-pin")
        exported = export_trait_lab_catalog_pins(self.store)
        dest = MemoryStore(Path(self.tmp.name) / "pins.db")
        try:
            imported = import_trait_lab_catalog_pins(
                dest, exported, agent_id="unit", task_id="p13-imp"
            )
            self.assertTrue(imported["imported"])
            self.assertEqual(count_trait_lab_catalog_pins(dest), 1)
            self.assertTrue(has_trait_lab_catalog_pin(dest, exported["pins"][0]["catalog_sha256"]))
        finally:
            dest.close()

    def test_p14_malformed_report(self) -> None:
        self.store.put(
            MemoryEntry(
                key="verified:trait-lab-catalog-deadbeefdeadbeef",
                layer=MemoryLayer.VERIFIED_KNOWLEDGE,
                entry_type=MemoryEntryType.FACT,
                value={"source": "abc", "count": 1},
                agent_id="unit",
                task_id="p14",
            )
        )
        report = report_malformed_trait_lab_catalog_pins(self.store)
        self.assertEqual(report["count"], 1)
        self.assertTrue(report["keys"][0].startswith("verified:trait-lab-catalog-"))

    def test_p15_best_pin(self) -> None:
        self._import_seed(7, "p15a")
        first = self._pin_current("p15-pin-a")
        self._import_seed(8, "p15b")
        second = self._pin_current("p15-pin-b")
        best = best_trait_lab_catalog_pin(self.store)
        self.assertEqual(best["catalog_sha256"], second["catalog_sha256"])
        self.assertEqual(best["count"], 2)
        self.assertNotEqual(best["catalog_sha256"], first["catalog_sha256"])

    def test_p16_diff_indexes(self) -> None:
        self._import_seed(9, "p16a")
        self._pin_current("p16-pin-a")
        first = export_trait_lab_catalog_pins(self.store)
        self._import_seed(10, "p16b")
        self._pin_current("p16-pin-b")
        second = export_trait_lab_catalog_pins(self.store)
        diff = diff_trait_lab_catalog_pin_indexes(first, second)
        self.assertEqual(len(diff["only_b"]), 1)
        self.assertFalse(diff["live_verified"])
        with self.assertRaises(MemoryLayerError) as err:
            diff_trait_lab_catalog_pin_indexes(first, first)
        self.assertEqual(err.exception.code, "same_pin_index")

    def test_p17_p18_public_row_and_refuse_live(self) -> None:
        self._import_seed(11, "p17")
        pinned = self._pin_current("p17-pin")
        row = get_trait_lab_catalog_pin(self.store, pinned["catalog_sha256"])
        public = public_trait_lab_catalog_pin_row(row)
        self.assertEqual(public["catalog_sha256"], pinned["catalog_sha256"])
        self.assertNotIn("agent_id", public)
        self.assertFalse(public["live_verified"])
        with self.assertRaises(MemoryLayerError) as err:
            refuse_trait_lab_catalog_pin_live({"live_verified": True})
        self.assertEqual(err.exception.code, "live_claim")

    def test_p19_p20_p24_pack_membership(self) -> None:
        pack = self._import_seed(12, "p19")
        self._pin_current("p19-pin")
        self.assertTrue(catalog_pin_has_pack(self.store, pack["pack_sha256"]))
        self.assertFalse(catalog_pin_has_pack(self.store, "ab" * 32))
        ids = list_trait_lab_catalog_pin_ids_for_pack(self.store, pack["pack_sha256"])
        self.assertEqual(len(ids), 1)
        self.assertEqual(count_trait_lab_catalog_pins_for_pack(self.store, pack["pack_sha256"]), 1)

    def test_p21_get_by_fact_id(self) -> None:
        self._import_seed(13, "p21")
        pinned = self._pin_current("p21-pin")
        got = get_trait_lab_catalog_pin_by_fact_id(self.store, pinned["fact_id"])
        self.assertEqual(got["catalog_sha256"], pinned["catalog_sha256"])
        with self.assertRaises(MemoryLayerError) as err:
            get_trait_lab_catalog_pin_by_fact_id(self.store, "trait-lab-catalog-ffffffffffffffff")
        self.assertEqual(err.exception.code, "missing_pin")

    def test_p22_p23_pin_from_store_and_has_count(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            pin_trait_lab_seed_pack_catalog_from_store(
                self.store, agent_id="unit", task_id="p22-empty"
            )
        self.assertEqual(err.exception.code, "missing_catalog")
        self._import_seed(14, "p22")
        pinned = pin_trait_lab_seed_pack_catalog_from_store(
            self.store, agent_id="unit", task_id="p22-pin"
        )
        self.assertTrue(pinned["pinned"])
        self.assertTrue(has_trait_lab_catalog_pin(self.store, pinned["catalog_sha256"]))
        self.assertTrue(catalog_pin_has_count(self.store, 1))
        self.assertFalse(catalog_pin_has_count(self.store, 9))


if __name__ == "__main__":
    unittest.main()
