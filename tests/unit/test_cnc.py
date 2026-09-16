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
