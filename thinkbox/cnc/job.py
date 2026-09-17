"""CNC manufacturing domain model."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Material:
    def __init__(self, name: str = "6061-T6 Aluminum", grade: str = "6061-T6",
                 stock_size: str = "100x100x10", stock_units: str = "mm"):
        self.name = name
        self.grade = grade
        self.stock_size = stock_size
        self.stock_units = stock_units

    def model_dump(self) -> dict[str, Any]:
        return {"name": self.name, "grade": self.grade, "stock_size": self.stock_size, "stock_units": self.stock_units}


class Tool:
    def __init__(self, name: str = "End Mill 10mm", tool_type: str = "end_mill",
                 diameter_mm: float = 10.0, flute_count: int = 2, material: str = "Carbide"):
        self.name = name
        self.tool_type = tool_type
        self.diameter_mm = diameter_mm
        self.flute_count = flute_count
        self.material = material

    def model_dump(self) -> dict[str, Any]:
        return {"name": self.name, "tool_type": self.tool_type, "diameter_mm": self.diameter_mm, "flute_count": self.flute_count, "material": self.material}


class MachineProfile:
    def __init__(self, name: str = "HAAS VF-2SS", control_system: str = "Fanuc",
                 spindle_speed_rpm: int = 8000, travel_x_mm: int = 300,
                 travel_y_mm: int = 250, travel_z_mm: int = 200):
        self.name = name
        self.control_system = control_system
        self.spindle_speed_rpm = spindle_speed_rpm
        self.travel_x_mm = travel_x_mm
        self.travel_y_mm = travel_y_mm
        self.travel_z_mm = travel_z_mm

    def model_dump(self) -> dict[str, Any]:
        return {"name": self.name, "control_system": self.control_system, "spindle_speed_rpm": self.spindle_speed_rpm, "travel_x_mm": self.travel_x_mm, "travel_y_mm": self.travel_y_mm, "travel_z_mm": self.travel_z_mm}


class Operation:
    def __init__(self, operation_id: str = "op-1", operation_type: str = "milling",
                 tool: Tool | None = None, spindle_speed_rpm: int = 8000,
                 feed_rate_mm_min: int = 200, depth_of_cut_mm: float = 2.0,
                 passes: int = 1, description: str = "Roughing pass"):
        self.operation_id = operation_id
        self.operation_type = operation_type
        self.tool = tool or Tool()
        self.spindle_speed_rpm = spindle_speed_rpm
        self.feed_rate_mm_min = feed_rate_mm_min
        self.depth_of_cut_mm = depth_of_cut_mm
        self.passes = passes
        self.description = description

    def model_dump(self) -> dict[str, Any]:
        return {"operation_id": self.operation_id, "operation_type": self.operation_type, "tool": self.tool.model_dump(), "spindle_speed_rpm": self.spindle_speed_rpm, "feed_rate_mm_min": self.feed_rate_mm_min, "depth_of_cut_mm": self.depth_of_cut_mm, "passes": self.passes, "description": self.description}


class ValidationResult:
    def __init__(self, is_valid: bool = True, errors: list[str] | None = None, warnings: list[str] | None = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []

    def model_dump(self) -> dict[str, Any]:
        return {"is_valid": self.is_valid, "errors": self.errors, "warnings": self.warnings}


class ApprovalRecord:
    def __init__(self, approver_id: str = "", reason: str = "", timestamp: str = "", approved: bool = False):
        self.approver_id = approver_id
        self.reason = reason
        self.timestamp = timestamp
        self.approved = approved

    def model_dump(self) -> dict[str, Any]:
        return {"approver_id": self.approver_id, "reason": self.reason, "timestamp": self.timestamp, "approved": self.approved}


class ExecutionRecord:
    def __init__(self, operation_id: str = "", status: str = "pending", start_time: str = "", end_time: str = "", notes: str = ""):
        self.operation_id = operation_id
        self.status = status
        self.start_time = start_time
        self.end_time = end_time
        self.notes = notes

    def model_dump(self) -> dict[str, Any]:
        return {"operation_id": self.operation_id, "status": self.status, "start_time": self.start_time, "end_time": self.end_time, "notes": self.notes}


class InspectionResult:
    def __init__(self, operation_id: str = "", passed: bool = True, measurements: dict[str, Any] | None = None, notes: str = ""):
        self.operation_id = operation_id
        self.passed = passed
        self.measurements = measurements or {}
        self.notes = notes

    def model_dump(self) -> dict[str, Any]:
        return {"operation_id": self.operation_id, "passed": self.passed, "measurements": self.measurements, "notes": self.notes}


class CNCJob:
    def __init__(self, job_id: str = "", part_name: str = "", part_number: str = "PN-001",
                 material: Material | None = None, machine: MachineProfile | None = None,
                 operations: list[Operation] | None = None, customer_id: str = "default",
                 priority: str = "normal", status: str = "created"):
        self.job_id = job_id or f"cnc-{uuid.uuid4().hex[:8]}"
        self.part_name = part_name
        self.part_number = part_number
        self.material = material or Material()
        self.machine = machine or MachineProfile()
        self.operations = operations or []
        self.customer_id = customer_id
        self.priority = priority
        self.status = status
        self.approval_records: list[ApprovalRecord] = []
        self.execution_records: list[ExecutionRecord] = []
        self.inspection_results: list[InspectionResult] = []
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at

    def model_dump(self) -> dict[str, Any]:
        return {"job_id": self.job_id, "part_name": self.part_name, "part_number": self.part_number, "material": self.material.model_dump(), "machine": self.machine.model_dump(), "operations": [op.model_dump() for op in self.operations], "customer_id": self.customer_id, "priority": self.priority, "status": self.status, "approval_records": [a.model_dump() for a in self.approval_records], "execution_records": [e.model_dump() for e in self.execution_records], "inspection_results": [i.model_dump() for i in self.inspection_results], "created_at": self.created_at, "updated_at": self.updated_at}
