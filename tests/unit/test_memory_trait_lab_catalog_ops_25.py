"""Hermetic tests for Trait Lab catalog operator pack C01–C25."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.schema import MemoryEntry, MemoryEntryType, MemoryLayer
from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    TRAIT_LAB_CATALOG_OPS,
    apply_trait_lab_seed_pack,
    best_trait_lab_seed_pack_for_seed,
    catalog_has_seed,
    catalog_trait_lab_seed_pack_etag,
    catalog_trait_lab_seed_packs,
    catalog_trait_lab_seed_packs_by_agent,
    catalog_trait_lab_seed_packs_by_count_band,
    catalog_trait_lab_seed_packs_by_count_ceiling,
    catalog_trait_lab_seed_packs_by_count_floor,
    catalog_trait_lab_seed_packs_by_task,
    catalog_trait_lab_seed_packs_digest,
    catalog_trait_lab_seed_packs_for_seed,
    catalog_trait_lab_seed_packs_page,
    count_trait_lab_seed_packs,
    diff_trait_lab_seed_pack_catalogs,
    export_trait_lab_seed_pack,
    export_trait_lab_seed_pack_catalog,
    get_trait_lab_seed_pack,
    has_trait_lab_seed_pack,
    import_trait_lab_seed_pack,
    import_trait_lab_seed_pack_catalog,
    list_trait_lab_seed_pack_ids,
    list_trait_lab_seed_pack_ids_for_seed,
    list_trait_lab_seed_pack_seeds,
    public_trait_lab_seed_pack_row,
    purge_trait_lab_seed_pack,
    record_trait_lab_run,
    refuse_trait_lab_catalog_live,
    report_malformed_trait_lab_seed_packs,
    verify_trait_lab_seed_pack_catalog,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabCatalogOps25(unittest.TestCase):
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

    def _import_seed(self, seed: int, task_id: str) -> dict:
        self._record_finish(seed, task_id)
        pack = export_trait_lab_seed_pack(self.store, seed)
        import_trait_lab_seed_pack(self.store, pack, agent_id="unit", task_id=f"imp-{task_id}")
        return pack

    def test_c00_ops_catalog_has_25(self) -> None:
        self.assertEqual(len(TRAIT_LAB_CATALOG_OPS), 25)
        self.assertEqual(len(set(TRAIT_LAB_CATALOG_OPS)), 25)

    def test_c01_catalog_for_seed(self) -> None:
        pack = self._import_seed(5, "c01")
        catalog = catalog_trait_lab_seed_packs_for_seed(self.store, 5)
        self.assertEqual(catalog["seed"], 5)
        self.assertEqual(catalog["packs"][0]["pack_sha256"], pack["pack_sha256"])
        self.assertFalse(catalog["live_verified"])

    def test_c02_has_pack(self) -> None:
        pack = self._import_seed(4, "c02")
        self.assertTrue(has_trait_lab_seed_pack(self.store, pack["pack_sha256"]))
        self.assertFalse(has_trait_lab_seed_pack(self.store, "ab" * 32))

    def test_c03_list_ids(self) -> None:
        pack = self._import_seed(3, "c03")
        ids = list_trait_lab_seed_pack_ids(self.store)
        self.assertEqual(ids, [pack["pack_sha256"]])

    def test_c04_count_packs(self) -> None:
        self.assertEqual(count_trait_lab_seed_packs(self.store), 0)
        self._import_seed(2, "c04")
        self.assertEqual(count_trait_lab_seed_packs(self.store), 1)

    def test_c05_list_seeds(self) -> None:
        self._import_seed(2, "c05b")
        self._import_seed(1, "c05a")
        self.assertEqual(list_trait_lab_seed_pack_seeds(self.store), [1, 2])

    def test_c06_count_floor(self) -> None:
        self._import_seed(6, "c06")
        catalog = catalog_trait_lab_seed_packs_by_count_floor(self.store, 1)
        self.assertEqual(catalog["count"], 1)
        with self.assertRaises(MemoryLayerError) as err:
            catalog_trait_lab_seed_packs_by_count_floor(self.store, 9)
        self.assertEqual(err.exception.code, "missing_floor")

    def test_c07_count_ceiling(self) -> None:
        self._import_seed(7, "c07")
        catalog = catalog_trait_lab_seed_packs_by_count_ceiling(self.store, 1)
        self.assertEqual(catalog["count"], 1)

    def test_c08_count_band(self) -> None:
        self._import_seed(8, "c08")
        catalog = catalog_trait_lab_seed_packs_by_count_band(self.store, 1, 1)
        self.assertEqual(catalog["count"], 1)
        with self.assertRaises(MemoryLayerError) as err:
            catalog_trait_lab_seed_packs_by_count_band(self.store, 3, 1)
        self.assertEqual(err.exception.code, "invalid_band")

    def test_c09_page(self) -> None:
        self._import_seed(1, "c09a")
        self._import_seed(2, "c09b")
        page = catalog_trait_lab_seed_packs_page(self.store, offset=1, limit=1)
        self.assertEqual(len(page["packs"]), 1)
        self.assertEqual(page["count"], 2)
        self.assertEqual(page["offset"], 1)

    def test_c10_purge_keeps_runs(self) -> None:
        pack = self._import_seed(9, "c10")
        dest = MemoryStore(Path(self.tmp.name) / "dest.db")
        try:
            apply_trait_lab_seed_pack(dest, pack, agent_id="unit", task_id="c10-apply")
            purged = purge_trait_lab_seed_pack(dest, pack["pack_sha256"])
            self.assertTrue(purged["purged"])
            self.assertFalse(has_trait_lab_seed_pack(dest, pack["pack_sha256"]))
            from thinkbox.memory_layers import trait_lab_seed_history

            history = trait_lab_seed_history(dest, 9)
            self.assertGreaterEqual(history["count"], 1)
        finally:
            dest.close()

    def test_c11_c12_c13_export_verify_digest(self) -> None:
        self._import_seed(11, "c11")
        exported = export_trait_lab_seed_pack_catalog(self.store)
        self.assertEqual(len(exported["catalog_sha256"]), 64)
        self.assertEqual(catalog_trait_lab_seed_packs_digest(self.store), exported["catalog_sha256"])
        verified = verify_trait_lab_seed_pack_catalog(exported)
        self.assertTrue(verified["matched"])
        tampered = dict(exported)
        changed = dict(exported["packs"][0])
        changed["count"] = int(changed["count"]) + 1
        tampered["packs"] = [changed]
        with self.assertRaises(MemoryLayerError) as err:
            verify_trait_lab_seed_pack_catalog(tampered)
        self.assertEqual(err.exception.code, "catalog_mismatch")

    def test_c14_import_catalog_index(self) -> None:
        self._import_seed(12, "c14")
        exported = export_trait_lab_seed_pack_catalog(self.store)
        dest = MemoryStore(Path(self.tmp.name) / "idx.db")
        try:
            imported = import_trait_lab_seed_pack_catalog(
                dest, exported, agent_id="unit", task_id="c14-imp"
            )
            self.assertTrue(imported["imported"])
            self.assertEqual(count_trait_lab_seed_packs(dest), 1)
        finally:
            dest.close()

    def test_c15_by_agent(self) -> None:
        self._import_seed(13, "c15")
        catalog = catalog_trait_lab_seed_packs_by_agent(self.store, "unit")
        self.assertEqual(catalog["count"], 1)
        with self.assertRaises(MemoryLayerError) as err:
            catalog_trait_lab_seed_packs_by_agent(self.store, "other")
        self.assertEqual(err.exception.code, "missing_agent")

    def test_c16_by_task(self) -> None:
        self._import_seed(14, "c16")
        catalog = catalog_trait_lab_seed_packs_by_task(self.store, "imp-c16")
        self.assertEqual(catalog["count"], 1)

    def test_c17_malformed_report(self) -> None:
        self.store.put(
            MemoryEntry(
                key="verified:trait-lab-pack-deadbeefdeadbeef",
                layer=MemoryLayer.VERIFIED_KNOWLEDGE,
                entry_type=MemoryEntryType.FACT,
                value={"source": "abc", "seed": 1},
                agent_id="unit",
                task_id="c17",
            )
        )
        report = report_malformed_trait_lab_seed_packs(self.store)
        self.assertEqual(report["count"], 1)
        self.assertTrue(report["keys"][0].startswith("verified:trait-lab-pack-"))

    def test_c18_has_seed(self) -> None:
        self.assertFalse(catalog_has_seed(self.store, 15))
        self._import_seed(15, "c18")
        self.assertTrue(catalog_has_seed(self.store, 15))

    def test_c19_best_for_seed(self) -> None:
        pack = self._import_seed(16, "c19")
        best = best_trait_lab_seed_pack_for_seed(self.store, 16)
        self.assertEqual(best["pack_sha256"], pack["pack_sha256"])

    def test_c20_diff_catalogs(self) -> None:
        self._import_seed(1, "c20a")
        first = export_trait_lab_seed_pack_catalog(self.store)
        self._import_seed(2, "c20b")
        second = export_trait_lab_seed_pack_catalog(self.store)
        diff = diff_trait_lab_seed_pack_catalogs(first, second)
        self.assertEqual(len(diff["only_b"]), 1)
        self.assertFalse(diff["live_verified"])

    def test_c21_ids_for_seed(self) -> None:
        pack = self._import_seed(17, "c21")
        self.assertEqual(list_trait_lab_seed_pack_ids_for_seed(self.store, 17), [pack["pack_sha256"]])

    def test_c22_etag(self) -> None:
        self._import_seed(18, "c22")
        etag = catalog_trait_lab_seed_pack_etag(self.store)
        self.assertEqual(len(etag), 16)
        self.assertEqual(etag, catalog_trait_lab_seed_packs_digest(self.store)[:16])

    def test_c23_refuse_live(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            refuse_trait_lab_catalog_live({"live_verified": True})
        self.assertEqual(err.exception.code, "live_claim")
        live = export_trait_lab_seed_pack_catalog(self.store)
        live["live_verified"] = True
        with self.assertRaises(MemoryLayerError) as err2:
            verify_trait_lab_seed_pack_catalog(live)
        self.assertEqual(err2.exception.code, "live_claim")

    def test_c24_public_row(self) -> None:
        pack = self._import_seed(19, "c24")
        row = catalog_trait_lab_seed_packs(self.store)["packs"][0]
        public = public_trait_lab_seed_pack_row(row)
        self.assertEqual(public["pack_sha256"], pack["pack_sha256"])
        self.assertNotIn("agent_id", public)
        self.assertFalse(public["live_verified"])

    def test_c25_get_pack(self) -> None:
        pack = self._import_seed(20, "c25")
        got = get_trait_lab_seed_pack(self.store, pack["pack_sha256"])
        self.assertEqual(got["pack_sha256"], pack["pack_sha256"])
        self.assertEqual(got["fact_id"], f"trait-lab-pack-{pack['pack_sha256'][:16]}")
        with self.assertRaises(MemoryLayerError) as err:
            get_trait_lab_seed_pack(self.store, "ab" * 32)
        self.assertEqual(err.exception.code, "missing_pack")


if __name__ == "__main__":
    unittest.main()
