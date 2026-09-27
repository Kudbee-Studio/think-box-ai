"""Hermetic tests for Trait Lab autonomous workflow A16–A25."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.autonomous_workflow import (
    TRAIT_LAB_AUTONOMOUS_WORKFLOW_OPS,
    dry_run_trait_lab_autonomous_workflow,
    get_trait_lab_autonomous_workflow_receipt,
    has_trait_lab_autonomous_workflow_receipt,
    list_trait_lab_autonomous_workflow_receipts,
    list_trait_lab_autonomous_workflow_receipts_by_agent,
    persist_trait_lab_autonomous_workflow_receipt,
    public_trait_lab_autonomous_workflow_row,
    require_trait_lab_autonomous_workflow_green_session,
    run_trait_lab_autonomous,
    sign_trait_lab_autonomous_workflow,
    trait_lab_autonomous_workflow_status,
    workflow_from_session_trait_lab_autonomous,
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


class TestMemoryTraitLabAutonomousWorkflow25(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "layers.db")

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def _seed_prep_and_session(self) -> tuple[str, str]:
        report = export_trait_lab_local_env_prep_report(agent_id="unit", task_id="a25")
        persist_trait_lab_local_env_prep_receipt(
            self.store, report, agent_id="unit", task_id="a25"
        )
        session_plan = session_from_prep_trait_lab_operator()
        session_dry = dry_run_trait_lab_operator_session(
            self.store, session_plan, agent_id="unit", task_id="a25", environ={}
        )
        persist_trait_lab_operator_session_receipt(
            self.store, session_dry, agent_id="unit", task_id="a25"
        )
        return report["prep_sha256"], session_dry["session_sha256"]

    def test_a00_ops_catalog_has_25(self) -> None:
        self.assertEqual(len(TRAIT_LAB_AUTONOMOUS_WORKFLOW_OPS), 25)
        self.assertEqual(len(set(TRAIT_LAB_AUTONOMOUS_WORKFLOW_OPS)), 25)

    def test_a16_public_row(self) -> None:
        signed = sign_trait_lab_autonomous_workflow(
            {"steps": ["prep", "session", "workflow_dry_run"]}
        )
        public = public_trait_lab_autonomous_workflow_row(signed)
        self.assertEqual(public["autonomous_sha256"], signed["autonomous_sha256"])
        self.assertFalse(public["live_verified"])

    def test_a17_a18_dry_run_full_chain(self) -> None:
        prep_sha, session_sha = self._seed_prep_and_session()
        green = require_trait_lab_autonomous_workflow_green_session(self.store, session_sha)
        self.assertTrue(green["green"])
        plan = workflow_from_session_trait_lab_autonomous({"session_sha256": session_sha})
        ran = dry_run_trait_lab_autonomous_workflow(
            self.store,
            plan,
            agent_id="unit",
            task_id="a18",
            environ={},
            prep_sha256=prep_sha,
        )
        self.assertEqual(trait_lab_autonomous_workflow_status(ran), "dry_run")
        self.assertTrue(ran["ok"])
        self.assertFalse(ran["wrote"])

    def test_a20_a24_receipt_index(self) -> None:
        prep_sha, session_sha = self._seed_prep_and_session()
        plan = workflow_from_session_trait_lab_autonomous({"session_sha256": session_sha})
        ran = dry_run_trait_lab_autonomous_workflow(
            self.store,
            plan,
            agent_id="unit",
            task_id="a20",
            environ={},
            prep_sha256=prep_sha,
            session_sha256=session_sha,
        )
        persisted = persist_trait_lab_autonomous_workflow_receipt(
            self.store, ran, agent_id="unit", task_id="a20"
        )
        self.assertTrue(persisted["persisted"])
        sha = ran["autonomous_sha256"]
        self.assertTrue(has_trait_lab_autonomous_workflow_receipt(self.store, sha))
        row = get_trait_lab_autonomous_workflow_receipt(self.store, sha)
        self.assertEqual(row["status"], "dry_run")
        listed = list_trait_lab_autonomous_workflow_receipts(self.store)
        self.assertGreaterEqual(listed["count"], 1)
        by_agent = list_trait_lab_autonomous_workflow_receipts_by_agent(self.store, "unit")
        self.assertEqual(by_agent["agent_id"], "unit")

    def test_a25_run_autonomous(self) -> None:
        out = run_trait_lab_autonomous(agent_id="unit", task_id="a25-run", environ={})
        self.assertTrue(out["ran"])
        self.assertTrue(out["ok"])
        self.assertEqual(out["status"], "ready")
        sha = out["autonomous"]["autonomous_sha256"]
        ws_store = MemoryStore(Path(out["workspace"]["store_path"]))
        try:
            self.assertTrue(has_trait_lab_autonomous_workflow_receipt(ws_store, sha))
        finally:
            ws_store.close()

    def test_a17_blocks_bad_session(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            require_trait_lab_autonomous_workflow_green_session(self.store, "a" * 64)
        self.assertIn(err.exception.code, {"missing_session", "missing_autonomous"})
