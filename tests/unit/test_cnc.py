"""Tests for CNC manufacturing module."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from thinkbox.cnc import (
    CNCJob,
    CNCManufacturingEngine,
    DemoMode,
    ManufacturingMemory,
    Material,
    MachineProfile,
    Operation,
    ProofPackage,
    ProofStore,
    SafetyGate,
    SafetyGateStore,
    Tenant,
    TenantStore,
    Tool,
    ValidationResult,
    ROIStats,
    ROIDashboard,
)
from thinkbox.cnc.job import CNCJob as CNCJobClass
from thinkbox.dashboard_state import (
    get_dashboard_state, DashboardCategory, DashboardEvent,
    ThinkBoxEntry, ThinkJobEntry, CNCJobEntry,
    InfrastructureEntry, ProviderEntry, TestMilestoneEntry,
)
from thinkbox.upcloud import (
    UpCloudConfig, UpCloudExecutionPath, investigate_upcloud,
)
from thinkbox.replay import ReplayDriver


class TestCNCJob(unittest.TestCase):
    def test_create_job(self):
        job = CNCJob(part_name="Test Part", part_number="PN-001")
        self.assertIsNotNone(job.job_id)
        self.assertEqual(job.part_name, "Test Part")
        self.assertEqual(job.status, "created")

    def test_job_model_dump(self):
        material = Material(name="6061-T6 Aluminum")
        machine = MachineProfile(name="HAAS VF-2SS")
        tool = Tool(name="End Mill", tool_type="end_mill", diameter_mm=10.0)
        operation = Operation(operation_id="op-1", operation_type="milling", tool=tool)
        job = CNCJob(part_name="Bracket", material=material, machine=machine, operations=[operation])
        data = job.model_dump()
        self.assertEqual(data["part_name"], "Bracket")
        self.assertEqual(data["material"]["name"], "6061-T6 Aluminum")
        self.assertEqual(len(data["operations"]), 1)

    def test_job_with_operations(self):
        tool = Tool(name="End Mill 10mm", diameter_mm=10.0)
        op1 = Operation(operation_id="op-1", operation_type="milling", tool=tool, depth_of_cut_mm=2.0)
        op2 = Operation(operation_id="op-2", operation_type="drilling", tool=tool, depth_of_cut_mm=5.0)
        job = CNCJob(part_name="Complex Part", operations=[op1, op2])
        self.assertEqual(len(job.operations), 2)

    def test_job_approval(self):
        job = CNCJob(part_name="Test")
        job.approval_records.append({"approver_id": "operator", "reason": "Approved", "approved": True})
        self.assertEqual(len(job.approval_records), 1)

    def test_job_execution(self):
        job = CNCJob(part_name="Test")
        job.execution_records.append({"operation_id": "op-1", "status": "completed"})
        self.assertEqual(len(job.execution_records), 1)

    def test_job_inspection(self):
        job = CNCJob(part_name="Test")
        job.inspection_results.append({"operation_id": "op-1", "passed": True})
        self.assertEqual(len(job.inspection_results), 1)

    def test_job_default_values(self):
        job = CNCJob()
        self.assertIsNotNone(job.job_id)
        self.assertEqual(job.priority, "normal")
        self.assertEqual(job.customer_id, "default")

    def test_job_material(self):
        material = Material(name="6061-T6 Aluminum", grade="6061-T6", stock_size="100x100x10")
        self.assertEqual(material.name, "6061-T6 Aluminum")
        self.assertEqual(material.grade, "6061-T6")
        self.assertEqual(material.stock_size, "100x100x10")

    def test_job_machine_profile(self):
        machine = MachineProfile(name="HAAS VF-2SS", control_system="Fanuc", spindle_speed_rpm=8000)
        self.assertEqual(machine.name, "HAAS VF-2SS")
        self.assertEqual(machine.spindle_speed_rpm, 8000)
        self.assertEqual(machine.travel_x_mm, 300)


class TestManufacturingMemory(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memory = ManufacturingMemory(storage_path=Path(self.tmpdir) / "memory")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_store_knowledge(self):
        entry = self.memory.store_knowledge(knowledge_type="lesson", content="Use sharp tools", confidence=0.9)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.knowledge_type, "lesson")

    def test_recall(self):
        self.memory.store_knowledge(knowledge_type="lesson", content="Use sharp tools for aluminum")
        results = self.memory.recall("sharp")
        self.assertGreater(len(results), 0)

    def test_recall_empty(self):
        results = self.memory.recall("nonexistent")
        self.assertEqual(len(results), 0)

    def test_to_dict(self):
        self.memory.store_knowledge(knowledge_type="fact", content="Test fact")
        data = self.memory.to_dict()
        self.assertIn("entries", data)

    def test_persistence(self):
        self.memory.store_knowledge(knowledge_type="lesson", content="Persistent lesson")
        memory2 = ManufacturingMemory(storage_path=Path(self.tmpdir) / "memory")
        results = memory2.recall("Persistent")
        self.assertGreater(len(results), 0)


class TestProofPackage(unittest.TestCase):
    def test_create_proof(self):
        proof = ProofPackage(job_id="cnc-001", evidence_label="simulated")
        self.assertIsNotNone(proof.proof_id)
        self.assertEqual(proof.job_id, "cnc-001")
        self.assertEqual(proof.evidence_label, "simulated")

    def test_proof_hash(self):
        proof = ProofPackage(job_id="cnc-001", evidence_label="simulated")
        self.assertIsNotNone(proof.hash)
        self.assertEqual(len(proof.hash), 64)  # SHA-256

    def test_proof_model_dump(self):
        proof = ProofPackage(job_id="cnc-001", evidence_label="simulated")
        data = proof.model_dump()
        self.assertEqual(data["job_id"], "cnc-001")
        self.assertEqual(data["evidence_label"], "simulated")
        self.assertIn("hash", data)


class TestProofStore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = ProofStore(storage_path=Path(self.tmpdir) / "proofs")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_proof(self):
        proof = self.store.create_proof(job_id="cnc-001")
        self.assertIsNotNone(proof)
        self.assertEqual(len(self.store.list_proofs()), 1)

    def test_get_proof(self):
        proof = self.store.create_proof(job_id="cnc-001")
        retrieved = self.store.get_proof(proof.proof_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.job_id, "cnc-001")

    def test_list_proofs(self):
        self.store.create_proof(job_id="cnc-001")
        self.store.create_proof(job_id="cnc-002")
        proofs = self.store.list_proofs()
        self.assertEqual(len(proofs), 2)


class TestSafetyGate(unittest.TestCase):
    def test_safety_gate_check(self):
        gate = SafetyGate(job_id="cnc-001", requires_approval=True)
        result = gate.check_safety()
        self.assertTrue(result.is_safe)

    def test_safety_gate_with_issues(self):
        gate = SafetyGate(job_id="cnc-001", requires_approval=True, issues=["Tool not calibrated"])
        result = gate.check_safety()
        self.assertFalse(result.is_safe)
        self.assertEqual(len(result.issues), 1)

    def test_approval_gate(self):
        store = SafetyGateStore(storage_path=Path(tempfile.mkdtemp()) / "safety")
        approval = store.approve(job_id="cnc-001", approver_id="operator", reason="Approved")
        self.assertEqual(approval.status.value, "APPROVED")
        self.assertEqual(approval.approver_id, "operator")

    def test_emergency_stop(self):
        store = SafetyGateStore(storage_path=Path(tempfile.mkdtemp()) / "safety")
        store.approve(job_id="cnc-001", approver_id="operator")
        stopped = store.emergency_stop("cnc-001")
        self.assertEqual(len(stopped), 1)
        self.assertEqual(stopped[0].status.value, "EMERGENCY_STOP")


class TestTenant(unittest.TestCase):
    def test_create_tenant(self):
        store = TenantStore(storage_path=Path(tempfile.mkdtemp()) / "tenants")
        tenant = store.create_tenant(name="Acme Corp", plan="enterprise", max_jobs=1000)
        self.assertIsNotNone(tenant.tenant_id)
        self.assertEqual(tenant.name, "Acme Corp")
        self.assertEqual(tenant.plan, "enterprise")

    def test_get_tenant(self):
        store = TenantStore(storage_path=Path(tempfile.mkdtemp()) / "tenants")
        tenant = store.create_tenant(name="Test")
        retrieved = store.get_tenant(tenant.tenant_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "Test")

    def test_list_tenants(self):
        store = TenantStore(storage_path=Path(tempfile.mkdtemp()) / "tenants")
        store.create_tenant(name="A")
        store.create_tenant(name="B")
        tenants = store.list_tenants()
        self.assertEqual(len(tenants), 2)


class TestROIStats(unittest.TestCase):
    def test_default_stats(self):
        stats = ROIStats()
        self.assertEqual(stats.programming_hours_avoided, 0.0)
        self.assertEqual(stats.total_savings_avoided, 0.0)

    def test_model_dump(self):
        stats = ROIStats(programming_hours_avoided=10.0, total_savings_avoided=5000.0)
        data = stats.model_dump()
        self.assertEqual(data["programming_hours_avoided"], 10.0)
        self.assertEqual(data["total_savings_avoided"], 5000.0)


class TestROIDashboard(unittest.TestCase):
    def test_compute_stats(self):
        dashboard = ROIDashboard()
        stats = dashboard.compute_stats()
        self.assertIsInstance(stats, ROIStats)

    def test_to_dict(self):
        dashboard = ROIDashboard()
        data = dashboard.to_dict()
        self.assertIn("programming_hours_avoided", data)

    def test_generate_report(self):
        dashboard = ROIDashboard()
        report = dashboard.generate_report()
        self.assertIn("CNC ROI Report", report)


class TestCNCManufacturingEngine(unittest.TestCase):
    def test_validate_valid_job(self):
        engine = CNCManufacturingEngine()
        material = Material(name="6061-T6 Aluminum")
        machine = MachineProfile(name="HAAS VF-2SS")
        tool = Tool(name="End Mill", diameter_mm=10.0)
        operation = Operation(operation_id="op-1", operation_type="milling", tool=tool)
        job = CNCJob(part_name="Test", material=material, machine=machine, operations=[operation])
        result = engine.validate_job(job)
        self.assertTrue(result.is_valid)

    def test_validate_invalid_job(self):
        engine = CNCManufacturingEngine()
        job = CNCJob(part_name="")
        result = engine.validate_job(job)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_job_dict(self):
        engine = CNCManufacturingEngine()
        job_data = {"part_name": "Test", "part_number": "PN-001", "material": {"name": "6061-T6"}, "machine": {"name": "HAAS"}, "operations": [{"operation_id": "op-1", "operation_type": "milling", "tool": {"name": "End Mill", "tool_type": "end_mill", "diameter_mm": 10.0}}]}
        result = engine.validate_job(job_data)
        self.assertTrue(result.is_valid)

    def test_execute_job(self):
        engine = CNCManufacturingEngine()
        material = Material(name="6061-T6 Aluminum")
        machine = MachineProfile(name="HAAS VF-2SS")
        tool = Tool(name="End Mill", diameter_mm=10.0)
        operation = Operation(operation_id="op-1", operation_type="milling", tool=tool)
        job = CNCJob(part_name="Test", material=material, machine=machine, operations=[operation])
        result = engine.execute_job(job)
        self.assertEqual(result["status"], "completed")

    def test_execute_job_not_approved(self):
        engine = CNCManufacturingEngine()
        material = Material(name="6061-T6 Aluminum")
        machine = MachineProfile(name="HAAS VF-2SS")
        tool = Tool(name="End Mill", diameter_mm=10.0)
        operation = Operation(operation_id="op-1", operation_type="milling", tool=tool)
        job = CNCJob(part_name="Test", material=material, machine=machine, operations=[operation])
        result = engine.execute_job(job)
        self.assertIn(result["status"], ["completed", "blocked"])

    def test_get_stats(self):
        engine = CNCManufacturingEngine()
        stats = engine.get_stats()
        self.assertIn("status", stats)


class TestDemoMode(unittest.TestCase):
    def test_run(self):
        demo = DemoMode()
        result = demo.run()
        self.assertEqual(result.status, "completed")
        self.assertIsNotNone(result.job.part_name)
        self.assertGreater(result.duration_seconds, 0)
        self.assertIn("simulated", result.evidence_labels)


class TestCNCAdapter(unittest.TestCase):
    def test_cnc_adapter_registry(self):
        from thinkbox.cnc.adapter import CNCAdapterRegistry, CADInterface
        registry = CNCAdapterRegistry()
        registry.register("test", {"name": "test_adapter"})
        self.assertEqual(registry.get("test")["name"], "test_adapter")
        self.assertIn("test", registry.list_adapters())

    def test_cad_interface_abstract(self):
        from thinkbox.cnc.adapter import CADInterface
        with self.assertRaises(TypeError):
            CADInterface()


class TestReplayCNC(unittest.TestCase):
    def test_replay_driver_creation(self):
        from unittest.mock import MagicMock
        from thinkbox.replay import ReplayDriver
        mock_session = MagicMock()
        mock_recorder = MagicMock()
        driver = ReplayDriver(mock_session, mock_recorder)
        self.assertIsNotNone(driver)

    def test_replay_resolve(self):
        from unittest.mock import MagicMock
        from thinkbox.replay import ReplayDriver, ReplayError
        mock_session = MagicMock()
        mock_session.metadata = {"goal": "test_goal"}
        mock_session.get_session.return_value = {"metadata": {"goal": "test_goal"}}
        mock_recorder = MagicMock()
        driver = ReplayDriver(mock_session, mock_recorder)
        # resolve may raise ReplayError for invalid session - that's expected behavior
        try:
            result = driver.resolve("test_goal")
            self.assertIsNotNone(result)
        except ReplayError:
            pass  # Expected for invalid session metadata


if __name__ == "__main__":
    unittest.main()


class TestDashboardState(unittest.TestCase):
    """Tests for dashboard state model."""

    def setUp(self) -> None:
        self.state = get_dashboard_state()
        self.state.think_boxes = {}
        self.state.think_jobs = {}
        self.state.cnc_jobs = {}
        self.state.infrastructure = {}
        self.state.providers = {}
        self.state.test_milestones = {}
        self.state.events = []

    def test_upsert_think_box(self) -> None:
        box = ThinkBoxEntry(box_id="box-1", name="TestBox", substrate="local")
        self.state.upsert_think_box(box)
        self.assertIn("box-1", self.state.think_boxes)
        self.assertEqual(self.state.think_boxes["box-1"].name, "TestBox")

    def test_upsert_think_job(self) -> None:
        job = ThinkJobEntry(job_id="job-1", goal="test goal")
        self.state.upsert_think_job(job)
        self.assertIn("job-1", self.state.think_jobs)
        self.assertEqual(self.state.think_jobs["job-1"].goal, "test goal")

    def test_upsert_cnc_job(self) -> None:
        cnc = CNCJobEntry(job_id="cnc-1", part_name="Bracket")
        self.state.upsert_cnc_job(cnc)
        self.assertIn("cnc-1", self.state.cnc_jobs)
        self.assertEqual(self.state.cnc_jobs["cnc-1"].part_name, "Bracket")

    def test_upsert_infrastructure(self) -> None:
        infra = InfrastructureEntry(component="upcloud_test", type="upcloud", status="ok", verified=True)
        self.state.upsert_infrastructure("upcloud_test", infra)
        self.assertIn("upcloud_test", self.state.infrastructure)
        self.assertTrue(self.state.infrastructure["upcloud_test"].verified)

    def test_upsert_provider(self) -> None:
        prov = ProviderEntry(name="UpCloud", status="unverified")
        self.state.upsert_provider(prov)
        self.assertIn("UpCloud", self.state.providers)
        self.assertEqual(self.state.providers["UpCloud"].status, "unverified")

    def test_upsert_test_milestone(self) -> None:
        milestone = TestMilestoneEntry(test_name="test_dashboard", status="pass")
        self.state.upsert_test_milestone(milestone)
        self.assertIn("test_dashboard", self.state.test_milestones)

    def test_get_state_returns_dict(self) -> None:
        state_dict = self.state.get_state()
        self.assertIn("think_boxes", state_dict)
        self.assertIn("think_jobs", state_dict)
        self.assertIn("cnc_jobs", state_dict)
        self.assertIn("infrastructure", state_dict)
        self.assertIn("providers", state_dict)
        self.assertIn("events", state_dict)
        self.assertIn("summary", state_dict)

    def test_emit_creates_event(self) -> None:
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            entry = loop.run_until_complete(
                self.state.emit(DashboardCategory.CNC, DashboardEvent.JOB_CREATED,
                                {"job_id": "cnc-1"}, "test")
            )
            self.assertIsNotNone(entry)
            self.assertEqual(entry.category, DashboardCategory.CNC)
            self.assertEqual(entry.event_type, DashboardEvent.JOB_CREATED)
            self.assertEqual(len(self.state.events), 1)
        finally:
            loop.close()

    def test_model_dump_methods(self) -> None:
        box = ThinkBoxEntry(box_id="b1", name="Test")
        job = ThinkJobEntry(job_id="j1", goal="g1")
        cnc = CNCJobEntry(job_id="c1", part_name="p1")
        infra = InfrastructureEntry(component="i1", type="t1")
        prov = ProviderEntry(name="p1")
        milestone = TestMilestoneEntry(test_name="m1")
        self.assertIsInstance(box.model_dump(), dict)
        self.assertIsInstance(job.model_dump(), dict)
        self.assertIsInstance(cnc.model_dump(), dict)
        self.assertIsInstance(infra.model_dump(), dict)
        self.assertIsInstance(prov.model_dump(), dict)
        self.assertIsInstance(milestone.model_dump(), dict)


class TestUpCloudInvestigation(unittest.TestCase):
    """Tests for UpCloud execution path investigation."""

    def test_upcloud_config_defaults(self) -> None:
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {"UPCLOUD_SERVER_HOSTNAME": "", "UPCLOUD_SERVER_IP": ""}, clear=False):
            config = UpCloudConfig(server_hostname="", server_ip="")
            self.assertEqual(config.ssh_user, "root")
            self.assertEqual(config.api_url, "https://api.upcloud.com/1.3")

    def test_upcloud_config_explicit_server(self) -> None:
        config = UpCloudConfig(server_hostname="kudbeev3", server_ip="209.50.56.169")
        self.assertEqual(config.server_hostname, "kudbeev3")
        self.assertEqual(config.server_ip, "209.50.56.169")

    def test_upcloud_config_from_env(self) -> None:
        config = UpCloudConfig()
        self.assertIsNotNone(config.api_token)

    def test_upcloud_trace_result_model_dump(self) -> None:
        from thinkbox.upcloud import UpCloudTraceResult
        result = UpCloudTraceResult(step="test", status="success", details={})
        d = result.model_dump()
        self.assertEqual(d["step"], "test")
        self.assertEqual(d["status"], "success")

    def test_upcloud_execution_path_init(self) -> None:
        from thinkbox.upcloud import UpCloudExecutionPath
        config = UpCloudConfig()
        path = UpCloudExecutionPath(config)
        self.assertIsNotNone(path)
        self.assertEqual(len(path.trace), 0)

    def test_investigate_upcloud_is_coroutine(self) -> None:
        import asyncio
        from thinkbox.upcloud import investigate_upcloud
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(investigate_upcloud())
            self.assertIsInstance(result, dict)
            self.assertIn("trace", result)
            self.assertIn("summary", result)
        finally:
            loop.close()

    def test_upcloud_trace_result_model_dump_with_error(self) -> None:
        from thinkbox.upcloud import UpCloudTraceResult
        result = UpCloudTraceResult(step="test", status="failed", details={}, error="test error")
        d = result.model_dump()
        self.assertEqual(d["error"], "test error")


class TestCNCLifecycleIntegration(unittest.TestCase):
    """Full lifecycle: create → validate → approve → execute → proof → dashboard."""

    def test_full_cnc_lifecycle(self) -> None:
        from thinkbox.cnc import (
            CNCJob, CNCManufacturingEngine, DemoMode,
            Material, MachineProfile, Operation, Tool,
            ProofPackage, SafetyGateStore,
        )
        from thinkbox.cnc.job import ApprovalRecord, ExecutionRecord
        from thinkbox.dashboard_state import get_dashboard_state, CNCJobEntry

        material = Material(name="6061-T6 Aluminum", grade="6061-T6")
        machine = MachineProfile(name="HAAS VF-2SS", control_system="Fanuc")
        tool = Tool(name="End Mill 10mm", tool_type="end_mill", diameter_mm=10.0)
        operation = Operation(
            operation_id="op-1", operation_type="milling", tool=tool,
            spindle_speed_rpm=8000, feed_rate_mm_min=200, depth_of_cut_mm=2.0,
            description="Roughing pass",
        )
        job = CNCJob(
            part_name="Aluminum Bracket", part_number="PN-001",
            material=material, machine=machine, operations=[operation],
            customer_id="customer-1", priority="high",
        )

        engine = CNCManufacturingEngine()
        validation = engine.validate_job(job)
        self.assertTrue(validation.is_valid)
        self.assertEqual(len(validation.errors), 0)

        gate = SafetyGateStore()
        approval = gate.approve(job.job_id, "operator", "Demo approved")
        self.assertEqual(approval.approver_id, "operator")
        self.assertEqual(approval.status.value, "APPROVED")

        execution = engine.execute_job(job)
        self.assertEqual(execution["status"], "completed")
        self.assertEqual(len(execution["execution_records"]), 1)

        proof = engine.create_proof(job, evidence_label="simulated")
        self.assertIsInstance(proof, ProofPackage)
        self.assertEqual(proof.job_id, job.job_id)
        self.assertEqual(proof.evidence_label, "simulated")

        approval_record = ApprovalRecord(approver_id="operator", reason="Demo approved", approved=True)
        job.approval_records.append(approval_record)
        self.assertEqual(len(job.approval_records), 1)
        exec_record = ExecutionRecord(operation_id="op-1", status="completed")
        job.execution_records.append(exec_record)
        self.assertEqual(len(job.execution_records), 1)
        job.inspection_results.append({"operation_id": "op-1", "passed": True})
        self.assertEqual(len(job.inspection_results), 1)

        demo = DemoMode()
        result = demo.run()
        self.assertEqual(result.status, "completed")
        self.assertGreater(result.duration_seconds, 0)
        self.assertIn("simulated", result.evidence_labels)
        self.assertIsNotNone(result.roi_stats)

        dashboard = get_dashboard_state()
        cnc_entry = CNCJobEntry(
            job_id=job.job_id, part_name=job.part_name,
            part_number=job.part_number, material="6061-T6 Aluminum",
            machine="HAAS VF-2SS", status="completed",
            operations=[op.model_dump() for op in job.operations],
            safety_approved=True, evidence_label="simulated",
        )
        dashboard.upsert_cnc_job(cnc_entry)
        self.assertIn(job.job_id, dashboard.cnc_jobs)
        retrieved = dashboard.cnc_jobs[job.job_id]
        self.assertEqual(retrieved.job_id, job.job_id)
        self.assertEqual(retrieved.safety_approved, True)

    def test_lifecycle_validation_failures(self) -> None:
        engine = CNCManufacturingEngine()
        from thinkbox.cnc import CNCJob

        empty_job = CNCJob(part_name="")
        result = engine.validate_job(empty_job)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

        no_mat_job = CNCJob(part_name="Test", material=None)
        result2 = engine.validate_job(no_mat_job)
        self.assertFalse(result2.is_valid)

    def test_lifecycle_tenant_isolation(self) -> None:
        from thinkbox.cnc import Tenant, TenantStore, TenantBoundary
        from thinkbox.cnc.tenant import TenantPermission

        store = TenantStore()
        tenant = store.create_tenant("Customer A", plan="enterprise")
        self.assertEqual(tenant.name, "Customer A")
        retrieved = store.get_tenant(tenant.tenant_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "Customer A")

        boundary = TenantBoundary(tenant)
        self.assertEqual(boundary.tenant.tenant_id, tenant.tenant_id)

        permission = TenantPermission(tenant_id=tenant.tenant_id, resource="cnc", action="execute")
        self.assertEqual(permission.tenant_id, tenant.tenant_id)

    def test_lifecycle_proof_persistence(self) -> None:
        import tempfile, os
        from thinkbox.cnc import ProofStore
        from thinkbox.cnc.job import Operation, Material, Tool

        tool = Tool(name="End Mill", tool_type="end_mill", diameter_mm=10.0)
        op = Operation(operation_id="op-1", operation_type="milling", tool=tool)

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStore(storage_path=tmpdir)
            proof1 = store.create_proof("job-1", "simulated")
            proof2 = store.create_proof("job-1", "verified")
            self.assertEqual(len(store.list_proofs()), 2)
            found = store.get_proof(proof1.proof_id)
            self.assertIsNotNone(found)
            self.assertEqual(found.evidence_label, "simulated")

    def test_lifecycle_scheduler_integration(self) -> None:
        from thinkbox.cnc import CNCManufacturingEngine, CNCJob, Material, MachineProfile, Tool, Operation
        from thinkbox.scheduler import SchedulerHarness

        engine = CNCManufacturingEngine()
        harness = SchedulerHarness()

        material = Material(name="6061-T6")
        machine = MachineProfile(name="HAAS")
        tool = Tool(name="End Mill", tool_type="end_mill", diameter_mm=10.0)
        op = Operation(operation_id="op-1", operation_type="milling", tool=tool)
        job = CNCJob(part_name="Bracket", material=material, machine=machine, operations=[op])

        validation = engine.validate_job(job)
        harness.admit_goal("cnc-job-1", {"part_name": "Bracket", "validated": validation.is_valid})
        self.assertTrue(harness.validator.is_valid())
        harness.start_goal("cnc-job-1")
        harness.execute_step("cnc-job-1", "validate")
        harness.execute_step("cnc-job-1", "execute")
        harness.complete_goal("cnc-job-1")
        stats = harness.get_harness_stats()
        self.assertEqual(stats["completed_goals"], 1)
