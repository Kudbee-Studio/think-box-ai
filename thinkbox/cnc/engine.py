"""CNC manufacturing engine."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from thinkbox.cnc.job import CNCJob, Material, MachineProfile, Operation, Tool, ValidationResult
from thinkbox.cnc.proof import ProofPackage, ProofStore
from thinkbox.cnc.safety import SafetyGate, SafetyGateStore


class CNCManufacturingEngine:
    """CNC manufacturing engine — validates, gates, executes, and proves jobs."""

    def __init__(self, safety_gate_store: SafetyGateStore | None = None,
                 proof_store: ProofStore | None = None) -> None:
        self._proof_store = proof_store or ProofStore()
        self._safety_store = safety_gate_store or SafetyGateStore()
        self._jobs: list[dict[str, Any]] = []

    def validate_job(self, job: CNCJob | dict[str, Any]) -> ValidationResult:
        """Validate a CNC job, returning errors and warnings."""
        if isinstance(job, dict):
            job = CNCJob(**job)
        errors = []
        warnings = []
        if not job.part_name:
            errors.append("Part name is required")
        if not job.operations:
            errors.append("At least one operation is required")
        if not job.material:
            errors.append("Material is required")
        if not job.machine:
            errors.append("Machine profile is required")
        for op in job.operations:
            if hasattr(op, 'depth_of_cut_mm') and op.depth_of_cut_mm > 10.0:
                warnings.append(f"Operation {op.operation_id}: depth of cut exceeds recommended limit")
            if hasattr(op, 'spindle_speed_rpm') and op.spindle_speed_rpm > 15000:
                errors.append(f"Operation {op.operation_id}: spindle speed exceeds maximum")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    def execute_job(self, job: CNCJob | dict[str, Any]) -> dict[str, Any]:
        """Execute a validated and approved CNC job."""
        if isinstance(job, dict):
            job = CNCJob(**job)
        validation = self.validate_job(job)
        if not validation.is_valid:
            return {"status": "failed", "errors": validation.errors}

        gate = self._safety_store.get_gate_by_job_id(job.job_id)
        if gate is None:
            return {"status": "blocked", "reason": "Safety gate not found"}
        if gate.status.value != "APPROVED":
            return {"status": "blocked", "reason": "Safety gate not approved"}

        records = []
        for op in job.operations:
            records.append({"operation_id": op.operation_id, "status": "completed", "start_time": datetime.now(timezone.utc).isoformat()})

        self._jobs.append(job.model_dump())

        return {"status": "completed", "execution_records": records}

    def get_stats(self) -> dict[str, Any]:
        """Return engine status statistics."""
        return {"engines": 1, "active_jobs": 0, "status": "running"}

    def create_proof(self, job: CNCJob | dict[str, Any], evidence_label: str = "simulated") -> ProofPackage:
        """Create a proof package for a job."""
        if isinstance(job, dict):
            job = CNCJob(**job)
        proof = self._proof_store.create_proof(job.job_id, evidence_label)
        return proof

    def list_jobs_by_tenant(self, tenant_id: str) -> list[dict[str, Any]]:
        """List jobs for a tenant (matched by customer_id)."""
        return [j for j in self._jobs if j.get("customer_id") == tenant_id]

    def query_jobs(self, status: str | None = None, customer_id: str | None = None) -> list[dict[str, Any]]:
        """Query jobs by optional status and/or customer_id filters."""
        results = list(self._jobs)
        if status is not None:
            results = [j for j in results if j.get("status") == status]
        if customer_id is not None:
            results = [j for j in results if j.get("customer_id") == customer_id]
        return results
