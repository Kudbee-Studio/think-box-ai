"""Hermetic tests for Trait Lab catalog pin bind workflow W01–W25."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    TRAIT_LAB_CATALOG_PIN_BIND_WORKFLOW_OPS,
    bind_workflow_catalogs_from_bound,
    bind_workflow_drop_unbound,
    bind_workflow_from_store,
    bind_workflow_retain_and_pin,
    count_trait_lab_catalog_pin_bind_workflow_steps,
    dry_run_trait_lab_catalog_pin_bind_workflow,
    export_trait_lab_catalog_pins,
    export_trait_lab_seed_pack,
    export_trait_lab_seed_pack_catalog,
    get_trait_lab_catalog_pin_bind_workflow_receipt,
    has_trait_lab_catalog_pin_bind_workflow_receipt,
    import_trait_lab_catalog_pins,
    import_trait_lab_seed_pack,
    list_trait_lab_catalog_pin_bind_workflow_receipts,
    list_trait_lab_catalog_pin_bind_workflow_receipts_by_agent,
    list_trait_lab_catalog_pin_bind_workflow_steps,
    page_trait_lab_catalog_pin_bind_workflow_steps,
    persist_trait_lab_catalog_pin_bind_workflow_receipt,
    pin_trait_lab_seed_pack_catalog,
    plan_trait_lab_catalog_pin_bind_workflow,
    public_trait_lab_catalog_pin_bind_workflow_row,
    record_trait_lab_run,
    refuse_trait_lab_catalog_pin_bind_workflow_live,
    require_bound_trait_lab_catalog_pin_bind_workflow,
    run_trait_lab_catalog_pin_bind_workflow,
    sign_trait_lab_catalog_pin_bind_workflow,
    trait_lab_catalog_pin_bind_workflow_digest,
    trait_lab_catalog_pin_bind_workflow_etag,
    trait_lab_catalog_pin_bind_workflow_has_step,
    trait_lab_catalog_pin_bind_workflow_status,
    validate_trait_lab_catalog_pin_bind_workflow,
    verify_trait_lab_catalog_pin_bind_workflow,
)
from thinkbox.trait_game.engine import act, load_rules, new_run, proof_scorecard


class TestMemoryTraitLabCatalogPinBindWorkflow25(unittest.TestCase):
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

    def test_w00_ops_catalog_has_25(self) -> None:
        self.assertEqual(len(TRAIT_LAB_CATALOG_PIN_BIND_WORKFLOW_OPS), 25)
        self.assertEqual(len(set(TRAIT_LAB_CATALOG_PIN_BIND_WORKFLOW_OPS)), 25)

    def test_w01_w05_plan_sign_verify(self) -> None:
        plan = plan_trait_lab_catalog_pin_bind_workflow(["export_catalog", "rematch"])
        self.assertEqual(plan["count"], 2)
        self.assertTrue(validate_trait_lab_catalog_pin_bind_workflow(plan)["valid"])
        signed = sign_trait_lab_catalog_pin_bind_workflow(plan)
        rematch = verify_trait_lab_catalog_pin_bind_workflow(signed)
        self.assertTrue(rematch["matched"])
        self.assertEqual(trait_lab_catalog_pin_bind_workflow_digest(plan), signed["workflow_sha256"])
        self.assertEqual(trait_lab_catalog_pin_bind_workflow_etag(plan), signed["workflow_sha256"][:16])
        with self.assertRaises(MemoryLayerError) as err:
            plan_trait_lab_catalog_pin_bind_workflow(["not-a-step"])
        self.assertEqual(err.exception.code, "invalid_step")
        with self.assertRaises(MemoryLayerError) as err2:
            plan_trait_lab_catalog_pin_bind_workflow([])
        self.assertEqual(err2.exception.code, "missing_step")

    def test_w03_w08_w09_w12_live_status_page(self) -> None:
        plan = plan_trait_lab_catalog_pin_bind_workflow(["export_catalog", "pin_catalog", "require_bound"])
        self.assertEqual(list_trait_lab_catalog_pin_bind_workflow_steps(plan), plan["steps"])
        self.assertEqual(count_trait_lab_catalog_pin_bind_workflow_steps(plan), 3)
        self.assertTrue(trait_lab_catalog_pin_bind_workflow_has_step(plan, "pin_catalog"))
        self.assertFalse(trait_lab_catalog_pin_bind_workflow_has_step(plan, "drop_unbound"))
        page = page_trait_lab_catalog_pin_bind_workflow_steps(plan, offset=1, limit=1)
        self.assertEqual(page["steps"], ["pin_catalog"])
        self.assertEqual(trait_lab_catalog_pin_bind_workflow_status(validate_trait_lab_catalog_pin_bind_workflow(plan)), "planned")
        live = dict(plan)
        live["live_verified"] = True
        with self.assertRaises(MemoryLayerError) as err:
            refuse_trait_lab_catalog_pin_bind_workflow_live(live)
        self.assertEqual(err.exception.code, "live_claim")
        public = public_trait_lab_catalog_pin_bind_workflow_row(plan)
        self.assertNotIn("agent_id", public)

    def test_w06_dry_run_skips_pin_write(self) -> None:
        self._import_seed(self.store, 1, "w06")
        plan = plan_trait_lab_catalog_pin_bind_workflow(["export_catalog", "pin_catalog", "rematch"])
        dry = dry_run_trait_lab_catalog_pin_bind_workflow(self.store, plan)
        self.assertEqual(dry["status"], "dry_run")
        self.assertFalse(dry["wrote"])
        pin_step = dry["results"][1]
        self.assertTrue(pin_step["skipped"])
        self.assertFalse(pin_step["wrote"])
        self.assertEqual(trait_lab_catalog_pin_bind_workflow_status(dry), "dry_run")

    def test_w07_w16_w17_from_store_requires_bound(self) -> None:
        self._import_seed(self.store, 2, "w17")
        ran = bind_workflow_from_store(self.store, agent_id="unit", task_id="w17-run")
        self.assertEqual(ran["status"], "ran")
        self.assertTrue(ran["wrote"])
        require_bound_trait_lab_catalog_pin_bind_workflow(self.store)
        dest = MemoryStore(Path(self.tmp.name) / "w17-empty.db")
        try:
            with self.assertRaises(MemoryLayerError) as err:
                require_bound_trait_lab_catalog_pin_bind_workflow(dest)
            self.assertEqual(err.exception.code, "unbound_pin")
        finally:
            dest.close()

    def test_w07_run_requires_provenance(self) -> None:
        self._import_seed(self.store, 3, "w07")
        plan = plan_trait_lab_catalog_pin_bind_workflow(["export_catalog", "pin_catalog"])
        with self.assertRaises(MemoryLayerError) as err:
            run_trait_lab_catalog_pin_bind_workflow(self.store, plan, agent_id="", task_id="w07")
        self.assertEqual(err.exception.code, "missing_provenance")

    def test_w18_retain_and_pin(self) -> None:
        self._import_seed(self.store, 4, "w18a")
        self._import_seed(self.store, 5, "w18b")
        ran = bind_workflow_retain_and_pin(self.store, agent_id="unit", task_id="w18-run")
        self.assertEqual(ran["status"], "ran")
        pin_step = next(row for row in ran["results"] if row["step"] == "pin_catalog")
        self.assertEqual(pin_step["result"]["count"], 1)

    def test_w19_drop_unbound_workflow(self) -> None:
        self._import_seed(self.store, 6, "w19")
        catalog = export_trait_lab_seed_pack_catalog(self.store)
        pin_trait_lab_seed_pack_catalog(self.store, catalog, agent_id="unit", task_id="w19-pin")
        dest = MemoryStore(Path(self.tmp.name) / "w19-unbound.db")
        try:
            import_trait_lab_catalog_pins(
                dest,
                export_trait_lab_catalog_pins(self.store),
                agent_id="unit",
                task_id="w19-import",
            )
            ran = bind_workflow_drop_unbound(dest, agent_id="unit", task_id="w19-drop")
            self.assertTrue(ran["wrote"])
            drop_step = next(row for row in ran["results"] if row["step"] == "drop_unbound")
            self.assertEqual(drop_step["result"]["count"], 1)
        finally:
            dest.close()

    def test_w20_catalogs_from_bound_workflow(self) -> None:
        self._import_seed(self.store, 7, "w20")
        bind_workflow_from_store(self.store, agent_id="unit", task_id="w20-pin")
        ran = bind_workflow_catalogs_from_bound(self.store, agent_id="unit", task_id="w20-cat")
        self.assertEqual(ran["status"], "ran")
        self.assertFalse(ran["wrote"])
        cat_step = next(row for row in ran["results"] if row["step"] == "catalogs_from_bound")
        self.assertEqual(cat_step["result"]["count"], 1)

    def test_w21_w25_persist_and_list_receipts(self) -> None:
        self._import_seed(self.store, 8, "w21")
        ran = bind_workflow_from_store(self.store, agent_id="unit", task_id="w21-run")
        receipt = persist_trait_lab_catalog_pin_bind_workflow_receipt(
            self.store, ran, agent_id="unit", task_id="w21-receipt"
        )
        self.assertTrue(receipt["persisted"])
        self.assertTrue(has_trait_lab_catalog_pin_bind_workflow_receipt(self.store, ran["workflow_sha256"]))
        got = get_trait_lab_catalog_pin_bind_workflow_receipt(self.store, ran["workflow_sha256"])
        self.assertEqual(got["status"], "ran")
        listed = list_trait_lab_catalog_pin_bind_workflow_receipts(self.store)
        self.assertEqual(listed["count"], 1)
        by_agent = list_trait_lab_catalog_pin_bind_workflow_receipts_by_agent(self.store, "unit")
        self.assertEqual(by_agent["count"], 1)
        with self.assertRaises(MemoryLayerError) as err:
            list_trait_lab_catalog_pin_bind_workflow_receipts_by_agent(self.store, "other")
        self.assertEqual(err.exception.code, "missing_agent")
        live = dict(ran)
        live["live_verified"] = True
        with self.assertRaises(MemoryLayerError) as err2:
            persist_trait_lab_catalog_pin_bind_workflow_receipt(
                self.store, live, agent_id="unit", task_id="w21-live"
            )
        self.assertEqual(err2.exception.code, "live_claim")


if __name__ == "__main__":
    unittest.main()
