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


class JobTemplate:
    """Preset templates for common CNC jobs."""

    @staticmethod
    def aluminum_bracket() -> dict[str, Any]:
        return {
            "part_name": "Aluminum Bracket",
            "part_number": "BRKT-AL-001",
            "material": Material(name="6061-T6 Aluminum", grade="6061-T6", stock_size="100x50x10", stock_units="mm"),
            "machine": MachineProfile(name="HAAS VF-2SS", control_system="Fanuc", spindle_speed_rpm=8000),
            "operations": [
                Operation(operation_id="op-1", operation_type="milling", tool=Tool(name="End Mill 10mm", tool_type="end_mill", diameter_mm=10.0), spindle_speed_rpm=8000, feed_rate_mm_min=200, depth_of_cut_mm=2.0, description="Roughing pass"),
                Operation(operation_id="op-2", operation_type="milling", tool=Tool(name="End Mill 6mm", tool_type="end_mill", diameter_mm=6.0), spindle_speed_rpm=10000, feed_rate_mm_min=150, depth_of_cut_mm=0.5, description="Finishing pass"),
                Operation(operation_id="op-3", operation_type="drilling", tool=Tool(name="Drill 8mm", tool_type="drill", diameter_mm=8.0), spindle_speed_rpm=3000, feed_rate_mm_min=100, depth_of_cut_mm=10.0, description="Mounting holes"),
            ],
            "customer_id": "default",
            "priority": "normal",
        }

    @staticmethod
    def steel_shaft() -> dict[str, Any]:
        return {
            "part_name": "Steel Shaft",
            "part_number": "SHFT-ST-001",
            "material": Material(name="1045 Steel", grade="1045", stock_size="50x50x200", stock_units="mm"),
            "machine": MachineProfile(name="Mazak QT-250", control_system="Mazatrol", spindle_speed_rpm=3000),
            "operations": [
                Operation(operation_id="op-1", operation_type="turning", tool=Tool(name="Turning Insert CNMG", tool_type="insert", diameter_mm=12.0), spindle_speed_rpm=1500, feed_rate_mm_min=300, depth_of_cut_mm=3.0, description="Rough turning"),
                Operation(operation_id="op-2", operation_type="turning", tool=Tool(name="Finishing Insert CCMT", tool_type="insert", diameter_mm=9.5), spindle_speed_rpm=2000, feed_rate_mm_min=200, depth_of_cut_mm=0.5, description="Finish turning"),
            ],
            "customer_id": "default",
            "priority": "high",
        }

    @staticmethod
    def titanium_implant() -> dict[str, Any]:
        return {
            "part_name": "Titanium Implant",
            "part_number": "IMPL-TI-001",
            "material": Material(name="Ti-6Al-4V", grade="Grade 5", stock_size="30x30x30", stock_units="mm"),
            "machine": MachineProfile(name="DMG MORI DMU 50", control_system="Heidenhain", spindle_speed_rpm=12000),
            "operations": [
                Operation(operation_id="op-1", operation_type="milling", tool=Tool(name="Ball Nose 4mm", tool_type="ball_nose", diameter_mm=4.0), spindle_speed_rpm=12000, feed_rate_mm_min=500, depth_of_cut_mm=0.2, description="5-axis roughing"),
                Operation(operation_id="op-2", operation_type="milling", tool=Tool(name="Ball Nose 2mm", tool_type="ball_nose", diameter_mm=2.0), spindle_speed_rpm=15000, feed_rate_mm_min=300, depth_of_cut_mm=0.1, description="5-axis finishing"),
            ],
            "customer_id": "medical-corp",
            "priority": "critical",
        }

    @staticmethod
    def list_templates() -> list[str]:
        return ["aluminum_bracket", "steel_shaft", "titanium_implant"]

    @classmethod
    def from_template(cls, name: str) -> CNCJob:
        template_map = {
            "aluminum_bracket": cls.aluminum_bracket(),
            "steel_shaft": cls.steel_shaft(),
            "titanium_implant": cls.titanium_implant(),
        }
        if name not in template_map:
            raise ValueError(f"Unknown template: {name}. Available: {list(template_map.keys())}")
        data = template_map[name]
        return CNCJob(
            part_name=data["part_name"],
            part_number=data["part_number"],
            material=data["material"],
            machine=data["machine"],
            operations=data["operations"],
            customer_id=data["customer_id"],
            priority=data["priority"],
        )
