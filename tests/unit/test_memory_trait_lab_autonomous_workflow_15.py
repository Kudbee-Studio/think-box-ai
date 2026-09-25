"""Hermetic tests for Trait Lab autonomous workflow A01–A15."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.autonomous_workflow import (
    TRAIT_LAB_AUTONOMOUS_WORKFLOW_OPS,
    TRAIT_LAB_AUTONOMOUS_WORKFLOW_STEPS,
    count_trait_lab_autonomous_workflow_steps,
    list_trait_lab_autonomous_workflow_steps,
    page_trait_lab_autonomous_workflow_steps,
    plan_trait_lab_autonomous_workflow,
    refuse_trait_lab_autonomous_workflow_live,
    require_trait_lab_autonomous_workflow_no_live_ack,
    require_trait_lab_autonomous_workflow_prep_receipt,
    require_trait_lab_autonomous_workflow_provenance,
    require_trait_lab_autonomous_workflow_session_receipt,
    sign_trait_lab_autonomous_workflow,
    trait_lab_autonomous_workflow_digest,
    trait_lab_autonomous_workflow_etag,
    trait_lab_autonomous_workflow_has_step,
    validate_trait_lab_autonomous_workflow,
    verify_trait_lab_autonomous_workflow,
)
from thinkbox.local_env_prep import (
    export_trait_lab_local_env_prep_report,
    persist_trait_lab_local_env_prep_receipt,
)
from thinkbox.memory_layers import MemoryLayerError
from thinkbox.operator_session import (
    dry_run_trait_lab_operator_session,
    persist_trait_lab_operator_session_receipt,
    session_from_prep_trait_lab_operator,
)


class TestMemoryTraitLabAutonomousWorkflow15(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "layers.db")

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def test_a00_ops_catalog_has_25(self) -> None:
        self.assertEqual(len(TRAIT_LAB_AUTONOMOUS_WORKFLOW_OPS), 25)
        self.assertEqual(len(set(TRAIT_LAB_AUTONOMOUS_WORKFLOW_OPS)), 25)
        self.assertEqual(len(TRAIT_LAB_AUTONOMOUS_WORKFLOW_STEPS), 3)

    def test_a01_a05_live_ack_provenance(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            refuse_trait_lab_autonomous_workflow_live({"live_verified": True})
        self.assertEqual(err.exception.code, "live_claim")
        self.assertTrue(require_trait_lab_autonomous_workflow_no_live_ack({})["ok"])
        with self.assertRaises(MemoryLayerError) as prov:
            require_trait_lab_autonomous_workflow_provenance(agent_id="", task_id="a05")
        self.assertEqual(prov.exception.code, "missing_provenance")

    def test_a06_a09_plan_sign_verify(self) -> None:
        plan = plan_trait_lab_autonomous_workflow(["prep", "session", "workflow_dry_run"])
        self.assertEqual(plan["count"], 3)
        self.assertTrue(validate_trait_lab_autonomous_workflow(plan)["valid"])
        signed = sign_trait_lab_autonomous_workflow(plan)
        rematch = verify_trait_lab_autonomous_workflow(signed)
        self.assertTrue(rematch["matched"])
        self.assertEqual(trait_lab_autonomous_workflow_digest(plan), signed["autonomous_sha256"])
        self.assertEqual(trait_lab_autonomous_workflow_etag(plan), signed["autonomous_sha256"][:16])
        with self.assertRaises(MemoryLayerError) as bad:
            plan_trait_lab_autonomous_workflow(["pin_catalog"])
        self.assertEqual(bad.exception.code, "invalid_step")

    def test_a10_a13_steps_and_page(self) -> None:
        plan = plan_trait_lab_autonomous_workflow(["prep", "workflow_dry_run"])
        self.assertEqual(count_trait_lab_autonomous_workflow_steps(plan), 2)
        self.assertEqual(list_trait_lab_autonomous_workflow_steps(plan), ["prep", "workflow_dry_run"])
        self.assertTrue(trait_lab_autonomous_workflow_has_step(plan, "prep"))
        page = page_trait_lab_autonomous_workflow_steps(plan, offset=1, limit=1)
        self.assertEqual(page["steps"], ["workflow_dry_run"])

    def test_a02_a03_require_receipts(self) -> None:
        with self.assertRaises(MemoryLayerError) as missing_prep:
            require_trait_lab_autonomous_workflow_prep_receipt(self.store)
        self.assertEqual(missing_prep.exception.code, "missing_prep")
        report = export_trait_lab_local_env_prep_report(agent_id="unit", task_id="a02")
        persist_trait_lab_local_env_prep_receipt(
            self.store, report, agent_id="unit", task_id="a02"
        )
        prep = require_trait_lab_autonomous_workflow_prep_receipt(self.store, report["prep_sha256"])
        self.assertTrue(prep["required"])
        with self.assertRaises(MemoryLayerError) as missing_sess:
            require_trait_lab_autonomous_workflow_session_receipt(self.store)
        self.assertEqual(missing_sess.exception.code, "missing_session")
        session_plan = session_from_prep_trait_lab_operator()
        session_ran = dry_run_trait_lab_operator_session(
            self.store, session_plan, agent_id="unit", task_id="a03", environ={}
        )
        persist_trait_lab_operator_session_receipt(
            self.store, session_ran, agent_id="unit", task_id="a03"
        )
        sess = require_trait_lab_autonomous_workflow_session_receipt(
            self.store, session_ran["session_sha256"]
        )
        self.assertTrue(sess["required"])
        self.assertEqual(sess["status"], "dry_run")
