"""CNC manufacturing engine."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from thinkbox.cnc.job import CNCJob, Material, MachineProfile, Operation, Tool, ValidationResult
from thinkbox.cnc.proof import ProofPackage, ProofStore
from thinkbox.cnc.safety import SafetyGate, SafetyGateStore


@dataclass
class CNCManufacturingEngine:
    def __init__(self):
        self._proof_store = ProofStore()
        self._safety_store = SafetyGateStore()

    def validate_job(self, job: CNCJob | dict[str, Any]) -> ValidationResult:
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
        if isinstance(job, dict):
            job = CNCJob(**job)
        validation = self.validate_job(job)
        if not validation.is_valid:
            return {"status": "failed", "errors": validation.errors}

        gate = self._safety_store.get_gate(job.job_id)
        if gate and gate.status.value != "APPROVED":
            return {"status": "blocked", "reason": "Safety gate not approved"}

        records = []
        for op in job.operations:
            records.append({"operation_id": op.operation_id, "status": "completed", "start_time": datetime.now(timezone.utc).isoformat()})

        return {"status": "completed", "execution_records": records}

    def get_stats(self) -> dict[str, Any]:
        return {"engines": 1, "active_jobs": 0, "status": "running"}

    def create_proof(self, job: CNCJob | dict[str, Any], evidence_label: str = "simulated") -> ProofPackage:
        if isinstance(job, dict):
            job = CNCJob(**job)
        proof = self._proof_store.create_proof(job.job_id, evidence_label)
        return proof
