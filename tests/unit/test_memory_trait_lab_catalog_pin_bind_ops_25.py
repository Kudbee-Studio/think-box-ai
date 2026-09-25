"""Hermetic tests for Trait Lab catalog pin bind lane operators D01–D25."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    TRAIT_LAB_CATALOG_PIN_BIND_LANE_OPS,
    catalog_pin_bind_has_pack,
    catalog_pin_binds_by_count_band,
    catalog_pin_binds_by_count_ceiling,
    catalog_pin_binds_by_count_floor,
    catalogs_from_bound_trait_lab_catalog_pins,
    count_trait_lab_catalog_pin_binds,
    count_trait_lab_catalog_pin_binds_for_pack,
    count_unbound_trait_lab_catalog_pins,
    diff_trait_lab_catalog_pin_bind_indexes,
    drop_unbound_trait_lab_catalog_pins,
    export_bound_trait_lab_catalog_pin_binds,
    export_trait_lab_catalog_pin_binds,
    export_trait_lab_catalog_pins,
    export_trait_lab_seed_pack,
    export_trait_lab_seed_pack_catalog,
    get_trait_lab_catalog_pin_bind_by_fact_id,
    has_bound_trait_lab_catalog_pin,
    has_trait_lab_catalog_pin,
    import_trait_lab_catalog_pins,
    import_trait_lab_seed_pack,
    intersect_trait_lab_catalog_pin_bind_indexes,
    list_bound_only_trait_lab_catalog_pin_binds,
    list_trait_lab_catalog_pin_bind_ids,
    list_trait_lab_catalog_pin_bind_ids_for_agent,
    list_trait_lab_catalog_pin_bind_ids_for_pack,
    list_trait_lab_catalog_pin_binds_by_task,
    list_unbound_only_trait_lab_catalog_pin_binds,
    merge_trait_lab_catalog_pin_bind_indexes,
    pin_trait_lab_seed_pack_catalog,
    record_trait_lab_run,
    rematch_trait_lab_catalog_pin_bind_index,
    retain_trait_lab_catalog_pin_binds,
    subtract_trait_lab_catalog_pin_bind_indexes,
    symmetric_diff_trait_lab_catalog_pin_bind_indexes,
    verify_trait_lab_catalog_pin_binds,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabCatalogPinBindOps25(unittest.TestCase):
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

    def test_d00_ops_catalog_has_25(self) -> None:
        self.assertEqual(len(TRAIT_LAB_CATALOG_PIN_BIND_LANE_OPS), 25)
        self.assertEqual(len(set(TRAIT_LAB_CATALOG_PIN_BIND_LANE_OPS)), 25)

    def test_d01_d02_list_ids_and_count(self) -> None:
        self.assertEqual(count_trait_lab_catalog_pin_binds(self.store), 0)
        self._import_seed(self.store, 1, "d01")
        pinned = self._pin_current(self.store, "d01-pin")
        self.assertEqual(list_trait_lab_catalog_pin_bind_ids(self.store), [pinned["catalog_sha256"]])
        self.assertEqual(count_trait_lab_catalog_pin_binds(self.store), 1)

    def test_d03_d23_by_task_and_agent_ids(self) -> None:
        self._import_seed(self.store, 2, "d03")
        pinned = self._pin_current(self.store, "d03-pin")
        by_task = list_trait_lab_catalog_pin_binds_by_task(self.store, "d03-pin")
        self.assertEqual(by_task["count"], 1)
        self.assertEqual(
            list_trait_lab_catalog_pin_bind_ids_for_agent(self.store, "unit"),
            [pinned["catalog_sha256"]],
        )
        with self.assertRaises(MemoryLayerError) as err:
            list_trait_lab_catalog_pin_binds_by_task(self.store, "missing")
        self.assertEqual(err.exception.code, "missing_task")

    def test_d04_d05_d06_count_bounds(self) -> None:
        self._import_seed(self.store, 3, "d04")
        self._pin_current(self.store, "d04-pin")
        self.assertEqual(catalog_pin_binds_by_count_floor(self.store, 1)["count"], 1)
        self.assertEqual(catalog_pin_binds_by_count_ceiling(self.store, 1)["count"], 1)
        self.assertEqual(catalog_pin_binds_by_count_band(self.store, 1, 1)["count"], 1)
        with self.assertRaises(MemoryLayerError) as err:
            catalog_pin_binds_by_count_floor(self.store, 9)
        self.assertEqual(err.exception.code, "missing_floor")

    def test_d07_d10_bound_only_and_has_bound(self) -> None:
        self.assertFalse(has_bound_trait_lab_catalog_pin(self.store))
        pack = self._import_seed(self.store, 4, "d07")
        pinned = self._pin_current(self.store, "d07-pin")
        bound = list_bound_only_trait_lab_catalog_pin_binds(self.store)
        self.assertEqual(bound["count"], 1)
        self.assertTrue(bound["binds"][0]["bound"])
        self.assertTrue(has_bound_trait_lab_catalog_pin(self.store))
        self.assertEqual(count_unbound_trait_lab_catalog_pins(self.store), 0)
        self.assertTrue(catalog_pin_bind_has_pack(self.store, pack["pack_sha256"]))
        self.assertEqual(
            list_trait_lab_catalog_pin_bind_ids_for_pack(self.store, pack["pack_sha256"]),
            [pinned["catalog_sha256"]],
        )
        self.assertEqual(count_trait_lab_catalog_pin_binds_for_pack(self.store, pack["pack_sha256"]), 1)
        with self.assertRaises(MemoryLayerError) as err:
            list_unbound_only_trait_lab_catalog_pin_binds(self.store)
        self.assertEqual(err.exception.code, "missing_pin")

    def test_d08_d09_d18_unbound_and_drop(self) -> None:
        self._import_seed(self.store, 5, "d08")
        pinned = self._pin_current(self.store, "d08-pin")
        dest = MemoryStore(Path(self.tmp.name) / "d08-unbound.db")
        try:
            import_trait_lab_catalog_pins(
                dest,
                export_trait_lab_catalog_pins(self.store),
                agent_id="unit",
                task_id="d08-import",
            )
            unbound = list_unbound_only_trait_lab_catalog_pin_binds(dest)
            self.assertEqual(unbound["count"], 1)
            self.assertEqual(count_unbound_trait_lab_catalog_pins(dest), 1)
            self.assertFalse(has_bound_trait_lab_catalog_pin(dest))
            dropped = drop_unbound_trait_lab_catalog_pins(dest)
            self.assertEqual(dropped["ids"], [pinned["catalog_sha256"]])
            self.assertFalse(has_trait_lab_catalog_pin(dest, pinned["catalog_sha256"]))
            with self.assertRaises(MemoryLayerError) as err:
                drop_unbound_trait_lab_catalog_pins(dest)
            self.assertEqual(err.exception.code, "missing_pin")
        finally:
            dest.close()

    def test_d11_d25_rematch_index_and_export_bound(self) -> None:
        self._import_seed(self.store, 6, "d11")
        self._pin_current(self.store, "d11-pin")
        exported = export_trait_lab_catalog_pin_binds(self.store)
        rematch = rematch_trait_lab_catalog_pin_bind_index(self.store, exported)
        self.assertTrue(rematch["rematched"])
        self.assertTrue(rematch["binds"][0]["bound"])
        rematch_ok = verify_trait_lab_catalog_pin_binds(rematch)
        self.assertTrue(rematch_ok["matched"])
        bound_export = export_bound_trait_lab_catalog_pin_binds(self.store)
        self.assertEqual(bound_export["count"], 1)
        self.assertTrue(bound_export["binds"][0]["bound"])
        empty = MemoryStore(Path(self.tmp.name) / "d11-empty.db")
        try:
            with self.assertRaises(MemoryLayerError) as err:
                export_bound_trait_lab_catalog_pin_binds(empty)
            self.assertEqual(err.exception.code, "missing_pin")
        finally:
            empty.close()

    def test_d12_d16_diff_and_compose(self) -> None:
        self._import_seed(self.store, 7, "d12a")
        first = self._pin_current(self.store, "d12-pin-a")
        left = export_trait_lab_catalog_pin_binds(self.store)
        other = MemoryStore(Path(self.tmp.name) / "d12-b.db")
        try:
            self._import_seed(other, 8, "d12b")
            second = self._pin_current(other, "d12-pin-b")
            right = export_trait_lab_catalog_pin_binds(other)
        finally:
            other.close()
        diff = diff_trait_lab_catalog_pin_bind_indexes(left, right)
        self.assertEqual(diff["only_a"], [first["catalog_sha256"]])
        self.assertEqual(diff["only_b"], [second["catalog_sha256"]])
        merged = merge_trait_lab_catalog_pin_bind_indexes(left, right)
        self.assertEqual(merged["mode"], "merge")
        self.assertEqual(merged["count"], 2)
        xor = symmetric_diff_trait_lab_catalog_pin_bind_indexes(left, right)
        self.assertEqual(xor["count"], 2)
        shared = intersect_trait_lab_catalog_pin_bind_indexes(merged, left)
        self.assertEqual(shared["count"], 1)
        subtracted = subtract_trait_lab_catalog_pin_bind_indexes(merged, left)
        self.assertEqual(subtracted["count"], 1)
        self.assertEqual(subtracted["binds"][0]["catalog_sha256"], second["catalog_sha256"])
        with self.assertRaises(MemoryLayerError) as err:
            merge_trait_lab_catalog_pin_bind_indexes(left, left)
        self.assertEqual(err.exception.code, "same_bind_index")

    def test_d17_retain_and_live(self) -> None:
        self._import_seed(self.store, 9, "d17a")
        self._pin_current(self.store, "d17-pin-a")
        self._import_seed(self.store, 10, "d17b")
        self._pin_current(self.store, "d17-pin-b")
        index = export_trait_lab_catalog_pin_binds(self.store)
        kept = retain_trait_lab_catalog_pin_binds(index, keep=1)
        self.assertEqual(kept["kept"], 1)
        self.assertEqual(kept["count"], 1)
        rematch = verify_trait_lab_catalog_pin_binds(kept)
        self.assertTrue(rematch["matched"])
        expected = sorted(index["binds"], key=lambda row: (-int(row["count"]), str(row["catalog_sha256"])))[0]
        self.assertEqual(kept["binds"][0]["catalog_sha256"], expected["catalog_sha256"])
        with self.assertRaises(MemoryLayerError) as err:
            retain_trait_lab_catalog_pin_binds(index, keep=0)
        self.assertEqual(err.exception.code, "invalid_keep")
        live = dict(index)
        live["live_verified"] = True
        with self.assertRaises(MemoryLayerError) as err2:
            retain_trait_lab_catalog_pin_binds(live)
        self.assertEqual(err2.exception.code, "live_claim")

    def test_d19_d22_catalogs_and_fact_id(self) -> None:
        self._import_seed(self.store, 11, "d19")
        pinned = self._pin_current(self.store, "d19-pin")
        catalogs = catalogs_from_bound_trait_lab_catalog_pins(self.store)
        self.assertEqual(catalogs["count"], 1)
        self.assertEqual(catalogs["catalogs"][0]["catalog_sha256"], pinned["catalog_sha256"])
        bind = get_trait_lab_catalog_pin_bind_by_fact_id(self.store, pinned["fact_id"])
        self.assertTrue(bind["bound"])
        self.assertEqual(bind["catalog_sha256"], pinned["catalog_sha256"])
        with self.assertRaises(MemoryLayerError) as err:
            get_trait_lab_catalog_pin_bind_by_fact_id(self.store, "trait-lab-catalog-0000000000000000")
        self.assertEqual(err.exception.code, "missing_pin")


if __name__ == "__main__":
    unittest.main()
