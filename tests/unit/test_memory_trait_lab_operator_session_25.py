"""Hermetic tests for Trait Lab operator session S01–S25."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.local_env_prep import (
    export_trait_lab_local_env_prep_report,
    list_trait_lab_local_env_prep_receipts,
    persist_trait_lab_local_env_prep_receipt,
)
from thinkbox.memory_layers import MemoryLayerError
from thinkbox.operator_session import (
    TRAIT_LAB_OPERATOR_SESSION_OPS,
    TRAIT_LAB_OPERATOR_SESSION_STEPS,
    count_trait_lab_operator_session_steps,
    dry_run_trait_lab_operator_session,
    get_trait_lab_operator_session_receipt,
    has_trait_lab_operator_session_receipt,
    list_trait_lab_operator_session_receipts,
    list_trait_lab_operator_session_receipts_by_agent,
    list_trait_lab_operator_session_steps,
    open_trait_lab_operator_session,
    page_trait_lab_operator_session_steps,
    persist_trait_lab_operator_session_receipt,
    plan_trait_lab_operator_session,
    public_trait_lab_operator_session_row,
    refuse_trait_lab_operator_session_live,
    require_trait_lab_operator_session_no_live_ack,
    require_trait_lab_operator_session_prep_ok,
    require_trait_lab_operator_session_prep_receipt,
    require_trait_lab_operator_session_provenance,
    session_from_prep_trait_lab_operator,
    sign_trait_lab_operator_session,
    trait_lab_operator_session_digest,
    trait_lab_operator_session_etag,
    trait_lab_operator_session_has_step,
    trait_lab_operator_session_status,
    validate_trait_lab_operator_session,
    verify_trait_lab_operator_session,
)


class TestMemoryTraitLabOperatorSession25(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "layers.db")

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def test_s00_ops_catalog_has_25(self) -> None:
        self.assertEqual(len(TRAIT_LAB_OPERATOR_SESSION_OPS), 25)
        self.assertEqual(len(set(TRAIT_LAB_OPERATOR_SESSION_OPS)), 25)
        self.assertEqual(len(TRAIT_LAB_OPERATOR_SESSION_STEPS), 3)

    def test_s01_s04_live_ack_provenance(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            refuse_trait_lab_operator_session_live({"live_verified": True})
        self.assertEqual(err.exception.code, "live_claim")
        self.assertTrue(require_trait_lab_operator_session_no_live_ack({})["ok"])
        with self.assertRaises(MemoryLayerError) as ack:
            require_trait_lab_operator_session_no_live_ack({"THINKBOX_SWARM_LIVE_ACK": "yes"})
        self.assertEqual(ack.exception.code, "live_claim")
        with self.assertRaises(MemoryLayerError) as prov:
            require_trait_lab_operator_session_provenance(agent_id="", task_id="s04")
        self.assertEqual(prov.exception.code, "missing_provenance")

    def test_s05_s08_plan_sign_verify(self) -> None:
        plan = plan_trait_lab_operator_session(["prep", "dry_run"])
        self.assertEqual(plan["count"], 2)
        self.assertTrue(validate_trait_lab_operator_session(plan)["valid"])
        signed = sign_trait_lab_operator_session(plan)
        rematch = verify_trait_lab_operator_session(signed)
        self.assertTrue(rematch["matched"])
        self.assertEqual(trait_lab_operator_session_digest(plan), signed["session_sha256"])
        self.assertEqual(trait_lab_operator_session_etag(plan), signed["session_sha256"][:16])
        with self.assertRaises(MemoryLayerError) as err:
            plan_trait_lab_operator_session(["pin_catalog"])
        self.assertEqual(err.exception.code, "invalid_step")

    def test_s09_s15_steps_public_row(self) -> None:
        plan = plan_trait_lab_operator_session(["prep", "require_prep", "dry_run"])
        self.assertEqual(count_trait_lab_operator_session_steps(plan), 3)
        self.assertEqual(list_trait_lab_operator_session_steps(plan), ["prep", "require_prep", "dry_run"])
        self.assertTrue(trait_lab_operator_session_has_step(plan, "prep"))
        page = page_trait_lab_operator_session_steps(plan, offset=1, limit=1)
        self.assertEqual(page["steps"], ["require_prep"])
        signed = sign_trait_lab_operator_session(plan)
        public = public_trait_lab_operator_session_row(signed)
        self.assertEqual(public["session_sha256"], signed["session_sha256"])
        self.assertNotIn("agent_id", public)

    def test_s02_s16_require_prep(self) -> None:
        report = export_trait_lab_local_env_prep_report(agent_id="unit", task_id="s02")
        self.assertTrue(require_trait_lab_operator_session_prep_ok(report)["required"])
        with self.assertRaises(MemoryLayerError) as missing:
            require_trait_lab_operator_session_prep_receipt(self.store)
        self.assertEqual(missing.exception.code, "missing_prep")
        persist_trait_lab_local_env_prep_receipt(
            self.store, report, agent_id="unit", task_id="s16"
        )
        got = require_trait_lab_operator_session_prep_receipt(self.store, report["prep_sha256"])
        self.assertTrue(got["required"])
        self.assertEqual(got["prep_sha256"], report["prep_sha256"])

    def test_s17_s18_dry_run_status(self) -> None:
        plan = session_from_prep_trait_lab_operator()
        ran = dry_run_trait_lab_operator_session(
            self.store, plan, agent_id="unit", task_id="s17", environ={}
        )
        self.assertEqual(ran["status"], "dry_run")
        self.assertFalse(ran["wrote"])
        self.assertTrue(ran["ok"])
        self.assertEqual(trait_lab_operator_session_status(ran), "dry_run")
        self.assertFalse(list_trait_lab_local_env_prep_receipts(self.store)["count"])

    def test_s17_require_prep_without_receipt_fails(self) -> None:
        plan = plan_trait_lab_operator_session(["require_prep", "dry_run"])
        with self.assertRaises(MemoryLayerError) as err:
            dry_run_trait_lab_operator_session(
                self.store, plan, agent_id="unit", task_id="s17b"
            )
        self.assertEqual(err.exception.code, "missing_prep")

    def test_s19_s23_persist_list_get(self) -> None:
        plan = session_from_prep_trait_lab_operator()
        ran = dry_run_trait_lab_operator_session(
            self.store, plan, agent_id="unit", task_id="s19", environ={}
        )
        receipt = persist_trait_lab_operator_session_receipt(
            self.store, ran, agent_id="unit", task_id="s19"
        )
        self.assertTrue(receipt["persisted"])
        self.assertTrue(has_trait_lab_operator_session_receipt(self.store, ran["session_sha256"]))
        got = get_trait_lab_operator_session_receipt(self.store, ran["session_sha256"])
        self.assertEqual(got["status"], "dry_run")
        listed = list_trait_lab_operator_session_receipts(self.store)
        self.assertEqual(listed["count"], 1)
        by_agent = list_trait_lab_operator_session_receipts_by_agent(self.store, "unit")
        self.assertEqual(by_agent["count"], 1)
        with self.assertRaises(MemoryLayerError) as err:
            list_trait_lab_operator_session_receipts_by_agent(self.store, "missing")
        self.assertEqual(err.exception.code, "missing_agent")

    def test_s24_s25_canned_and_open(self) -> None:
        canned = session_from_prep_trait_lab_operator()
        self.assertEqual(canned["steps"], ["prep", "dry_run"])
        opened = open_trait_lab_operator_session(agent_id="unit", task_id="s25", environ={})
        self.assertTrue(opened["opened"])
        self.assertTrue(opened["ok"])
        self.assertEqual(opened["status"], "ready")
        self.assertFalse(opened["live_verified"])
        self.assertTrue(opened["receipt"]["persisted"])
