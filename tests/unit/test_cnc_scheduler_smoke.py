"""Smoke test: SchedulerHarness orchestrating CNC lifecycle."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from thinkbox.cnc import (
    CNCJob,
    CNCManufacturingEngine,
    Material,
    MachineProfile,
    Operation,
    SafetyGateStore,
    Tool,
)
from thinkbox.cnc.proof_store import ProofStore
from thinkbox.scheduler import (
    AdmissionRateLimiter,
    ConfigValidator,
    DeadLetterQueue,
    DataIntegrityChecker,
    GracefulShutdownCoordinator,
    MemoryPressureMonitor,
    RetryStormGuard,
    SchemaVersionTracker,
    SchedulerHarness,
    SchedulerSentinel,
    AnomalyDetector,
)


class TestSchedulerHarnessCNCSmoke(unittest.TestCase):
    """Verify SchedulerHarness can orchestrate a CNC admit-validate-approve-execute-proof flow."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.safety_store = SafetyGateStore(storage_path=Path(self.tmpdir) / "safety")
        self.proof_store = ProofStore(storage_path=Path(self.tmpdir) / "proofs")
        self.engine = CNCManufacturingEngine(
            safety_gate_store=self.safety_store,
            proof_store=self.proof_store,
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_job(self) -> CNCJob:
        return CNCJob(
            part_name="Test Bracket",
            part_number="PN-TEST-001",
            material=Material(name="6061-T6 Aluminum"),
            machine=MachineProfile(name="HAAS VF-2SS"),
            operations=[
                Operation(
                    operation_id="op-1",
                    operation_type="milling",
                    tool=Tool(name="End Mill", tool_type="end_mill", diameter_mm=10.0),
                    spindle_speed_rpm=8000,
                    feed_rate_mm_min=200,
                    depth_of_cut_mm=2.0,
                    description="Roughing pass",
                )
            ],
            customer_id="tenant-1",
        )

    def _make_harness(self) -> SchedulerHarness:
        return SchedulerHarness()

    def test_admit_goal(self):
        harness = self._make_harness()
        receipt = harness.admit_goal("cnc-job-1")
        self.assertTrue(receipt["admitted"] or receipt["rate_limited"])
        self.assertIn("goal_id", receipt)

    def test_validate_cnc_job(self):
        harness = self._make_harness()
        job = self._make_job()
        result = self.engine.validate_job(job)
        self.assertTrue(result.is_valid)
        harness.start_goal("cnc-job-1", task_count=1)
        receipt = harness.execute_step("cnc-job-1", "validate", retry_count=0)
        self.assertTrue(receipt["executed"])

    def test_admit_and_start_goal(self):
        harness = self._make_harness()
        admit = harness.admit_goal("cnc-job-2")
        self.assertIn("goal_id", admit)
        start = harness.start_goal("cnc-job-2", task_count=1)
        self.assertTrue(start["started"])

    def test_approve_safety_gate(self):
        job = self._make_job()
        self.safety_store.approve(job_id=job.job_id, approver_id="operator", reason="Approved for production")
        gate = self.safety_store.get_gate_by_job_id(job.job_id)
        self.assertIsNotNone(gate)
        self.assertEqual(gate.status.value, "APPROVED")

    def test_execute_cnc_job(self):
        job = self._make_job()
        self.safety_store.approve(job_id=job.job_id, approver_id="operator", reason="Approved")
        result = self.engine.execute_job(job)
        self.assertEqual(result["status"], "completed")
        self.assertIn("execution_records", result)

    def test_create_proof_after_execution(self):
        job = self._make_job()
        self.safety_store.approve(job.job_id, approver_id="operator", reason="Approved")
        self.engine.execute_job(job)
        proof = self.engine.create_proof(job)
        self.assertIsNotNone(proof)
        self.assertEqual(proof.job_id, job.job_id)
        self.assertEqual(proof.evidence_label, "simulated")

    def test_tenant_scoped_job_list(self):
        job = self._make_job()
        self.safety_store.approve(job_id=job.job_id, approver_id="operator", reason="Approved")
        self.engine.execute_job(job)
        jobs = self.engine.list_jobs_by_tenant("tenant-1")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["customer_id"], "tenant-1")
        other = self.engine.list_jobs_by_tenant("tenant-2")
        self.assertEqual(len(other), 0)

    def test_proof_query_helpers(self):
        job = self._make_job()
        proof1 = self.proof_store.create_proof(job_id=job.job_id, evidence_label="simulated")
        proof2 = self.proof_store.create_proof(job_id="other-job", evidence_label="simulated")
        by_job = self.proof_store.query_proofs(job_id=job.job_id)
        self.assertEqual(len(by_job), 1)
        self.assertEqual(by_job[0].proof_id, proof1.proof_id)
        by_label = self.proof_store.query_proofs(evidence_label="simulated")
        self.assertEqual(len(by_label), 2)
        by_both = self.proof_store.query_proofs(job_id=job.job_id, evidence_label="simulated")
        self.assertEqual(len(by_both), 1)

    def test_full_cnc_lifecycle_under_harness(self):
        harness = self._make_harness()
        job = self._make_job()

        admit = harness.admit_goal(job.job_id)
        self.assertIn("goal_id", admit)

        harness.start_goal(job.job_id, task_count=1)

        validation = self.engine.validate_job(job)
        self.assertTrue(validation.is_valid)

        self.safety_store.approve(job.job_id, approver_id="operator", reason="Approved")

        execute_receipt = harness.execute_step(job.job_id, "execute", retry_count=0)
        self.assertTrue(execute_receipt["executed"])

        result = self.engine.execute_job(job)
        self.assertEqual(result["status"], "completed")

        proof = self.engine.create_proof(job)
        self.assertEqual(proof.evidence_label, "simulated")

    def test_scheduler_schema_versioned(self):
        harness = self._make_harness()
        versions = harness.schema.get_versions()
        self.assertIsInstance(versions, list)
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0]["component"], "scheduler_harness")
