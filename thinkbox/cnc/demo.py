"""Demo mode for CNC manufacturing."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from thinkbox.cnc.job import CNCJob, Material, MachineProfile, Operation, Tool
from thinkbox.cnc.engine import CNCManufacturingEngine
from thinkbox.cnc.proof import ProofStore
from thinkbox.cnc.safety import SafetyGateStore
from thinkbox.cnc.dashboard import ROIStats


@dataclass
class DemoResult:
    job: CNCJob = field(default_factory=CNCJob)
    status: str = "completed"
    duration_seconds: float = 1.5
    evidence_labels: list[str] = field(default_factory=list)
    roi_stats: ROIStats = field(default_factory=ROIStats)
    validation_results: list[Any] = field(default_factory=list)
    approval_records: list[Any] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return {"job": self.job.model_dump(), "status": self.status, "duration_seconds": self.duration_seconds, "evidence_labels": self.evidence_labels, "roi_stats": self.roi_stats.model_dump(), "validation_results": [r.model_dump() if hasattr(r, 'model_dump') else r for r in self.validation_results], "approval_records": [a.model_dump() if hasattr(a, 'model_dump') else a for a in self.approval_records]}


class DemoMode:
    def run(self) -> DemoResult:
        material = Material(name="6061-T6 Aluminum", grade="6061-T6")
        machine = MachineProfile(name="HAAS VF-2SS", control_system="Fanuc")
        tool = Tool(name="End Mill 10mm", tool_type="end_mill", diameter_mm=10.0)
        operation = Operation(operation_id="op-1", operation_type="milling", tool=tool, spindle_speed_rpm=8000, feed_rate_mm_min=200, depth_of_cut_mm=2.0, description="Roughing pass")
        job = CNCJob(part_name="Aluminum Bracket", part_number="PN-001", material=material, machine=machine, operations=[operation])

        engine = CNCManufacturingEngine()
        validation = engine.validate_job(job)

        gate = SafetyGateStore()
        approval = gate.approve(job.job_id, "operator", "Demo approved")

        result = DemoResult(
            job=job,
            status="completed",
            duration_seconds=1.5,
            evidence_labels=["simulated", "inferred"],
            roi_stats=ROIStats(programming_hours_avoided=2.5, total_savings_avoided=1250.0, jobs_completed=1),
            validation_results=[validation],
            approval_records=[approval],
        )
        return result
