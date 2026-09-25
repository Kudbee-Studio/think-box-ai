"""Hermetic tests for Trait Lab local environment prep E01–E25."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.store import MemoryStore
from thinkbox.local_env_prep import (
    TRAIT_LAB_LOCAL_ENV_PREP_OPS,
    count_trait_lab_local_env_prep_checks,
    dry_run_trait_lab_local_env_workflow,
    export_trait_lab_local_env_prep_report,
    get_trait_lab_local_env_prep_receipt,
    has_trait_lab_local_env_prep_receipt,
    list_trait_lab_local_env_prep_checks,
    list_trait_lab_local_env_prep_receipts,
    list_trait_lab_local_env_prep_receipts_by_agent,
    page_trait_lab_local_env_prep_checks,
    persist_trait_lab_local_env_prep_receipt,
    prepare_and_dry_run_trait_lab_local_env,
    prepare_trait_lab_local_env_workspace,
    probe_trait_lab_local_env_store,
    public_trait_lab_local_env_prep_row,
    redact_trait_lab_local_env_environ,
    refuse_trait_lab_local_env_prep_live,
    require_trait_lab_local_env_no_live_ack,
    require_trait_lab_local_env_provenance,
    require_trait_lab_local_env_python,
    run_trait_lab_local_env_prep_checks,
    trait_lab_local_env_prep_digest,
    trait_lab_local_env_prep_etag,
    trait_lab_local_env_prep_has_check,
    trait_lab_local_env_prep_status,
    verify_trait_lab_local_env_prep_report,
)
from thinkbox.memory_layers import MemoryLayerError


class TestMemoryTraitLabLocalEnvPrep25(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "layers.db")

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def test_e00_ops_catalog_has_25(self) -> None:
        self.assertEqual(len(TRAIT_LAB_LOCAL_ENV_PREP_OPS), 25)
        self.assertEqual(len(set(TRAIT_LAB_LOCAL_ENV_PREP_OPS)), 25)

    def test_e01_e05_python_redact_store_ack(self) -> None:
        py = require_trait_lab_local_env_python()
        self.assertTrue(py["ok"])
        redacted = redact_trait_lab_local_env_environ(
            {"THINKBOX_TOKEN": "secret-value", "PATH": "/usr/bin"}
        )
        self.assertEqual(redacted["THINKBOX_TOKEN"], "[REDACTED]")
        self.assertEqual(redacted["PATH"], "/usr/bin")
        probe = probe_trait_lab_local_env_store(Path(self.tmp.name) / "probe.db")
        self.assertTrue(probe["ok"])
        self.assertTrue(require_trait_lab_local_env_no_live_ack({})["ok"])
        with self.assertRaises(MemoryLayerError) as err:
            require_trait_lab_local_env_no_live_ack({"THINKBOX_SWARM_LIVE_ACK": "yes"})
        self.assertEqual(err.exception.code, "live_claim")

    def test_e02_e25_live_and_provenance(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            refuse_trait_lab_local_env_prep_live({"live_verified": True})
        self.assertEqual(err.exception.code, "live_claim")
        with self.assertRaises(MemoryLayerError) as err2:
            require_trait_lab_local_env_provenance(agent_id="", task_id="e02")
        self.assertEqual(err2.exception.code, "missing_provenance")

    def test_e06_e10_checks_and_run(self) -> None:
        self.assertEqual(count_trait_lab_local_env_prep_checks(), 5)
        self.assertEqual(len(list_trait_lab_local_env_prep_checks()), 5)
        self.assertTrue(trait_lab_local_env_prep_has_check("python"))
        self.assertFalse(trait_lab_local_env_prep_has_check("mercury"))
        page = page_trait_lab_local_env_prep_checks(offset=1, limit=2)
        self.assertEqual(len(page["checks"]), 2)
        ran = run_trait_lab_local_env_prep_checks(
            agent_id="unit", task_id="e10", environ={}
        )
        self.assertTrue(ran["ok"])
        self.assertEqual(ran["count"], 5)

    def test_e11_e15_export_verify_digest(self) -> None:
        report = export_trait_lab_local_env_prep_report(
            agent_id="unit", task_id="e11", environ={}
        )
        rematch = verify_trait_lab_local_env_prep_report(report)
        self.assertTrue(rematch["matched"])
        self.assertEqual(
            trait_lab_local_env_prep_digest(agent_id="unit", task_id="e11", environ={}),
            report["prep_sha256"],
        )
        self.assertEqual(
            trait_lab_local_env_prep_etag(agent_id="unit", task_id="e11", environ={}),
            report["prep_sha256"][:16],
        )
        public = public_trait_lab_local_env_prep_row(report)
        self.assertNotIn("agent_id", public)
        tampered = dict(report)
        checks = dict(report["checks"])
        checks["python"] = {**checks["python"], "python": "0.0"}
        tampered["checks"] = checks
        with self.assertRaises(MemoryLayerError) as err:
            verify_trait_lab_local_env_prep_report(tampered)
        self.assertEqual(err.exception.code, "prep_mismatch")

    def test_e16_e18_workspace_dry_run_status(self) -> None:
        workspace = prepare_trait_lab_local_env_workspace(Path(self.tmp.name) / "ws")
        self.assertTrue(workspace["prepared"])
        dry = dry_run_trait_lab_local_env_workflow(self.store, agent_id="unit", task_id="e17")
        self.assertEqual(dry["status"], "dry_run")
        self.assertFalse(dry["wrote"])
        self.assertEqual(trait_lab_local_env_prep_status(workspace), "ready")
        self.assertEqual(trait_lab_local_env_prep_status(dry), "dry_run")

    def test_e19_e23_persist_and_list_receipts(self) -> None:
        report = export_trait_lab_local_env_prep_report(
            agent_id="unit", task_id="e19", environ={}
        )
        receipt = persist_trait_lab_local_env_prep_receipt(
            self.store, report, agent_id="unit", task_id="e19-receipt"
        )
        self.assertTrue(receipt["persisted"])
        self.assertTrue(has_trait_lab_local_env_prep_receipt(self.store, report["prep_sha256"]))
        got = get_trait_lab_local_env_prep_receipt(self.store, report["prep_sha256"])
        self.assertTrue(got["ok"])
        listed = list_trait_lab_local_env_prep_receipts(self.store)
        self.assertEqual(listed["count"], 1)
        by_agent = list_trait_lab_local_env_prep_receipts_by_agent(self.store, "unit")
        self.assertEqual(by_agent["count"], 1)
        with self.assertRaises(MemoryLayerError) as err:
            list_trait_lab_local_env_prep_receipts_by_agent(self.store, "other")
        self.assertEqual(err.exception.code, "missing_agent")

    def test_e24_prepare_and_dry_run(self) -> None:
        bundled = prepare_and_dry_run_trait_lab_local_env(
            agent_id="unit", task_id="e24", environ={}
        )
        self.assertEqual(bundled["status"], "ready")
        self.assertTrue(bundled["ok"])
        self.assertFalse(bundled["dry_run"]["wrote"])
        self.assertTrue(bundled["receipt"]["persisted"])
        self.assertFalse(bundled["live_verified"])


if __name__ == "__main__":
    unittest.main()
