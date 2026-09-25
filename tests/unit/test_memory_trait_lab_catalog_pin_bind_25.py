"""Hermetic tests for Trait Lab catalog↔pin bind operators B01–B25."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    TRAIT_LAB_CATALOG_PIN_BIND_OPS,
    best_bound_trait_lab_catalog_pin,
    catalog_from_trait_lab_catalog_pin,
    count_bound_packs_for_pin,
    count_bound_trait_lab_catalog_pins,
    count_unbound_packs_for_pin,
    export_trait_lab_catalog_pin_binds,
    export_trait_lab_catalog_pins,
    export_trait_lab_seed_pack,
    export_trait_lab_seed_pack_catalog,
    has_unbound_trait_lab_catalog_pin,
    import_retained_trait_lab_catalog_pin_index,
    import_trait_lab_catalog_pins,
    import_trait_lab_seed_pack,
    list_bound_packs_for_pin,
    list_bound_trait_lab_catalog_pin_ids,
    list_trait_lab_catalog_pin_binds_by_agent,
    list_unbound_packs_for_pin,
    list_unbound_trait_lab_catalog_pin_ids,
    page_trait_lab_catalog_pin_binds,
    pin_merged_trait_lab_seed_pack_catalogs,
    pin_retained_trait_lab_seed_pack_catalog,
    pin_trait_lab_seed_pack_catalog,
    pin_xor_trait_lab_seed_pack_catalogs,
    public_trait_lab_catalog_pin_bind_row,
    purge_trait_lab_seed_pack,
    record_trait_lab_run,
    refuse_trait_lab_catalog_pin_bind_live,
    rematch_trait_lab_catalog_pin_against_store,
    report_trait_lab_catalog_pin_bind,
    trait_lab_catalog_pin_binds_digest,
    trait_lab_catalog_pin_binds_etag,
    trait_lab_catalog_pin_is_bound,
    verify_trait_lab_catalog_pin_binds,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabCatalogPinBind25(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "layers.db")
        self.rules = load_rules()

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def _import_seed(self, store: MemoryStore, seed: int, task_id: str) -> dict:
        state = act(self.rules, new_run(self.rules, seed=seed, difficulty="lab"), "finish")["state"]
        proof = proof_scorecard(state)
        record_trait_lab_run(store, proof, agent_id="unit", task_id=task_id)
        pack = export_trait_lab_seed_pack(store, seed)
        import_trait_lab_seed_pack(store, pack, agent_id="unit", task_id=f"imp-{task_id}")
        return pack

    def _pin_current(self, store: MemoryStore, task_id: str) -> dict:
        catalog = export_trait_lab_seed_pack_catalog(store)
        return pin_trait_lab_seed_pack_catalog(store, catalog, agent_id="unit", task_id=task_id)

    def _catalog_from_seeds(self, seeds: list[int], label: str) -> dict:
        store = MemoryStore(Path(self.tmp.name) / f"{label}.db")
        try:
            for seed in seeds:
                self._import_seed(store, seed, f"{label}-{seed}")
            return export_trait_lab_seed_pack_catalog(store)
        finally:
            store.close()

    def test_b00_ops_catalog_has_25(self) -> None:
        self.assertEqual(len(TRAIT_LAB_CATALOG_PIN_BIND_OPS), 25)
        self.assertEqual(len(set(TRAIT_LAB_CATALOG_PIN_BIND_OPS)), 25)

    def test_b01_b11_rematch_and_report_bound(self) -> None:
        pack = self._import_seed(self.store, 1, "b01")
        pinned = self._pin_current(self.store, "b01-pin")
        rematch = rematch_trait_lab_catalog_pin_against_store(self.store, pinned["catalog_sha256"])
        self.assertTrue(rematch["bound"])
        self.assertEqual(rematch["bound_ids"], [pack["pack_sha256"]])
        self.assertEqual(rematch["unbound_ids"], [])
        self.assertFalse(rematch["live_verified"])
        report = report_trait_lab_catalog_pin_bind(self.store, pinned["catalog_sha256"])
        self.assertEqual(report["catalog_sha256"], rematch["catalog_sha256"])
        self.assertTrue(trait_lab_catalog_pin_is_bound(self.store, pinned["catalog_sha256"]))

    def test_b02_b06_unbound_after_purge(self) -> None:
        pack = self._import_seed(self.store, 2, "b02")
        extra = self._import_seed(self.store, 3, "b02b")
        pinned = self._pin_current(self.store, "b02-pin")
        self.assertEqual(count_bound_packs_for_pin(self.store, pinned["catalog_sha256"]), 2)
        self.assertEqual(count_unbound_packs_for_pin(self.store, pinned["catalog_sha256"]), 0)
        purge_trait_lab_seed_pack(self.store, extra["pack_sha256"])
        self.assertFalse(trait_lab_catalog_pin_is_bound(self.store, pinned["catalog_sha256"]))
        self.assertEqual(list_bound_packs_for_pin(self.store, pinned["catalog_sha256"]), [pack["pack_sha256"]])
        self.assertEqual(list_unbound_packs_for_pin(self.store, pinned["catalog_sha256"]), [extra["pack_sha256"]])
        self.assertEqual(count_bound_packs_for_pin(self.store, pinned["catalog_sha256"]), 1)
        self.assertEqual(count_unbound_packs_for_pin(self.store, pinned["catalog_sha256"]), 1)

    def test_b07_b10_bound_and_unbound_pin_ids(self) -> None:
        self._import_seed(self.store, 4, "b07")
        bound_pin = self._pin_current(self.store, "b07-bound")
        dest = MemoryStore(Path(self.tmp.name) / "unbound.db")
        try:
            imported = import_trait_lab_catalog_pins(
                dest,
                export_trait_lab_catalog_pins(self.store),
                agent_id="unit",
                task_id="b07-import",
            )
            self.assertEqual(imported["count"], 1)
            self.assertEqual(list_bound_trait_lab_catalog_pin_ids(dest), [])
            self.assertEqual(list_unbound_trait_lab_catalog_pin_ids(dest), [bound_pin["catalog_sha256"]])
            self.assertEqual(count_bound_trait_lab_catalog_pins(dest), 0)
            self.assertTrue(has_unbound_trait_lab_catalog_pin(dest))
        finally:
            dest.close()
        self.assertEqual(list_bound_trait_lab_catalog_pin_ids(self.store), [bound_pin["catalog_sha256"]])
        self.assertEqual(list_unbound_trait_lab_catalog_pin_ids(self.store), [])
        self.assertEqual(count_bound_trait_lab_catalog_pins(self.store), 1)
        self.assertFalse(has_unbound_trait_lab_catalog_pin(self.store))

    def test_b12_b13_b20_b21_export_verify_digest(self) -> None:
        self._import_seed(self.store, 5, "b12")
        self._pin_current(self.store, "b12-pin")
        exported = export_trait_lab_catalog_pin_binds(self.store)
        rematch = verify_trait_lab_catalog_pin_binds(exported)
        self.assertTrue(rematch["matched"])
        self.assertEqual(rematch["count"], 1)
        self.assertTrue(rematch["binds"][0]["bound"])
        self.assertEqual(trait_lab_catalog_pin_binds_digest(self.store), exported["bind_index_sha256"])
        self.assertEqual(trait_lab_catalog_pin_binds_etag(self.store), exported["bind_index_sha256"][:16])
        tampered = dict(exported)
        row = dict(exported["binds"][0])
        row["count"] = int(row["count"]) + 1
        tampered["binds"] = [row]
        with self.assertRaises(MemoryLayerError) as err:
            verify_trait_lab_catalog_pin_binds(tampered)
        self.assertEqual(err.exception.code, "bind_mismatch")

    def test_b14_refuse_live(self) -> None:
        self._import_seed(self.store, 6, "b14")
        self._pin_current(self.store, "b14-pin")
        live = export_trait_lab_catalog_pin_binds(self.store)
        live["live_verified"] = True
        with self.assertRaises(MemoryLayerError) as err:
            refuse_trait_lab_catalog_pin_bind_live(live)
        self.assertEqual(err.exception.code, "live_claim")
        with self.assertRaises(MemoryLayerError) as err2:
            verify_trait_lab_catalog_pin_binds(live)
        self.assertEqual(err2.exception.code, "live_claim")

    def test_b15_pin_retained_catalog(self) -> None:
        catalog = self._catalog_from_seeds([7, 8], "b15")
        pinned = pin_retained_trait_lab_seed_pack_catalog(
            self.store, catalog, agent_id="unit", task_id="b15-pin", keep=1
        )
        self.assertEqual(pinned["count"], 1)
        self.assertFalse(pinned["live_verified"])
        with self.assertRaises(MemoryLayerError) as err:
            pin_retained_trait_lab_seed_pack_catalog(
                self.store, catalog, agent_id="unit", task_id="b15-bad", keep=0
            )
        self.assertEqual(err.exception.code, "invalid_keep")

    def test_b16_b17_pin_xor_and_merged(self) -> None:
        left = self._catalog_from_seeds([9], "b16-a")
        right = self._catalog_from_seeds([10], "b16-b")
        xor_pin = pin_xor_trait_lab_seed_pack_catalogs(
            self.store, left, right, agent_id="unit", task_id="b16-xor"
        )
        self.assertEqual(xor_pin["count"], 2)
        merged = pin_merged_trait_lab_seed_pack_catalogs(
            self.store, left, right, agent_id="unit", task_id="b16-merge"
        )
        self.assertEqual(merged["count"], 2)
        with self.assertRaises(MemoryLayerError) as err:
            pin_xor_trait_lab_seed_pack_catalogs(
                self.store, left, left, agent_id="unit", task_id="b16-same"
            )
        self.assertEqual(err.exception.code, "same_catalog")

    def test_b18_catalog_from_pin(self) -> None:
        self._import_seed(self.store, 11, "b18")
        catalog = export_trait_lab_seed_pack_catalog(self.store)
        pinned = pin_trait_lab_seed_pack_catalog(
            self.store, catalog, agent_id="unit", task_id="b18-pin"
        )
        rebuilt = catalog_from_trait_lab_catalog_pin(self.store, pinned["catalog_sha256"])
        self.assertTrue(rebuilt["matched"])
        self.assertEqual(rebuilt["catalog_sha256"], pinned["catalog_sha256"])
        dest = MemoryStore(Path(self.tmp.name) / "b18-unbound.db")
        try:
            import_trait_lab_catalog_pins(
                dest,
                export_trait_lab_catalog_pins(self.store),
                agent_id="unit",
                task_id="b18-import",
            )
            with self.assertRaises(MemoryLayerError) as err:
                catalog_from_trait_lab_catalog_pin(dest, pinned["catalog_sha256"])
            self.assertEqual(err.exception.code, "unbound_pin")
        finally:
            dest.close()

    def test_b19_b22_public_row_and_page(self) -> None:
        self._import_seed(self.store, 12, "b19a")
        first = self._pin_current(self.store, "b19-pin-a")
        self._import_seed(self.store, 13, "b19b")
        self._pin_current(self.store, "b19-pin-b")
        report = report_trait_lab_catalog_pin_bind(self.store, first["catalog_sha256"])
        public = public_trait_lab_catalog_pin_bind_row(report)
        self.assertEqual(public["catalog_sha256"], first["catalog_sha256"])
        self.assertNotIn("agent_id", public)
        page = page_trait_lab_catalog_pin_binds(self.store, offset=1, limit=1)
        self.assertEqual(len(page["binds"]), 1)
        self.assertEqual(page["count"], 2)
        self.assertEqual(page["offset"], 1)
        with self.assertRaises(MemoryLayerError) as err:
            page_trait_lab_catalog_pin_binds(self.store, offset=-1)
        self.assertEqual(err.exception.code, "invalid_offset")

    def test_b23_best_bound_pin(self) -> None:
        self._import_seed(self.store, 14, "b23")
        pinned = self._pin_current(self.store, "b23-pin")
        best = best_bound_trait_lab_catalog_pin(self.store)
        self.assertEqual(best["catalog_sha256"], pinned["catalog_sha256"])
        self.assertTrue(best["bound"])
        empty = MemoryStore(Path(self.tmp.name) / "b23-empty.db")
        try:
            with self.assertRaises(MemoryLayerError) as err:
                best_bound_trait_lab_catalog_pin(empty)
            self.assertEqual(err.exception.code, "missing_pin")
        finally:
            empty.close()

    def test_b24_import_retained_pin_index(self) -> None:
        self._import_seed(self.store, 15, "b24a")
        first = self._pin_current(self.store, "b24-pin-a")
        self._import_seed(self.store, 16, "b24b")
        self._pin_current(self.store, "b24-pin-b")
        index = export_trait_lab_catalog_pins(self.store)
        dest = MemoryStore(Path(self.tmp.name) / "b24-dest.db")
        try:
            imported = import_retained_trait_lab_catalog_pin_index(
                dest, index, agent_id="unit", task_id="b24-import", keep=1
            )
            self.assertEqual(imported["count"], 1)
            expected = sorted(
                index["pins"],
                key=lambda row: (-int(row["count"]), str(row["catalog_sha256"])),
            )[0]
            self.assertEqual(imported["ids"], [expected["catalog_sha256"]])
        finally:
            dest.close()
        self.assertEqual(first["count"], 1)

    def test_b25_binds_by_agent(self) -> None:
        self._import_seed(self.store, 17, "b25")
        pinned = self._pin_current(self.store, "b25-pin")
        by_agent = list_trait_lab_catalog_pin_binds_by_agent(self.store, "unit")
        self.assertEqual(by_agent["count"], 1)
        self.assertEqual(by_agent["binds"][0]["catalog_sha256"], pinned["catalog_sha256"])
        self.assertTrue(by_agent["binds"][0]["bound"])
        with self.assertRaises(MemoryLayerError) as err:
            list_trait_lab_catalog_pin_binds_by_agent(self.store, "other")
        self.assertEqual(err.exception.code, "missing_agent")
        with self.assertRaises(MemoryLayerError) as err2:
            rematch_trait_lab_catalog_pin_against_store(self.store, "0" * 64)
        self.assertEqual(err2.exception.code, "missing_pin")


if __name__ == "__main__":
    unittest.main()
