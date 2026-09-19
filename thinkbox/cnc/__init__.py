"""CNC module exports."""

from __future__ import annotations

from thinkbox.cnc.adapter import (
    CADInterface,
    MachineControllerInterface,
    InspectionSystemInterface,
    SimulatorInterface,
    ShopDatabaseInterface,
    CNCAdapterRegistry,
    MachineAdapter,
    SimMachineAdapter,
)
from thinkbox.cnc.dashboard import ROIStats, ROIDashboard
from thinkbox.cnc.demo import DemoMode, DemoResult
from thinkbox.cnc.engine import CNCManufacturingEngine
from thinkbox.cnc.job import (
    CNCJob,
    ApprovalRecord,
    ExecutionRecord,
    InspectionResult,
    Material,
    MachineProfile,
    Operation,
    Tool,
    ValidationResult,
    JobTemplate,
)
from thinkbox.cnc.memory import KnowledgeEntry, ManufacturingMemory
from thinkbox.cnc.proof import ProofPackage
from thinkbox.cnc.proof_store import ProofStore
from thinkbox.cnc.safety import ApprovalGate, SafetyGate
from thinkbox.cnc.safety_gate_store import SafetyGateStore
from thinkbox.cnc.tenant import Tenant, TenantPermission, TenantBoundary
from thinkbox.cnc.tenant_store import TenantStore
from thinkbox.cnc.telemetry import TelemetryIngest, TelemetrySeries, TelemetryPoint

__all__ = [
    "CADInterface", "MachineControllerInterface", "InspectionSystemInterface",
    "SimulatorInterface", "ShopDatabaseInterface", "CNCAdapterRegistry",
    "ApprovalGate", "SafetyGate", "SafetyGateStore",
    "Tenant", "TenantPermission", "TenantBoundary", "TenantStore",
    "CNCJob", "ValidationResult", "ApprovalRecord", "ExecutionRecord",
    "InspectionResult", "Material", "MachineProfile", "Operation", "Tool",
    "ROIStats", "ROIDashboard", "DemoMode", "DemoResult",
    "CNCManufacturingEngine", "KnowledgeEntry", "ManufacturingMemory",
    "ProofPackage", "ProofStore", "JobTemplate",
    "TelemetryIngest", "TelemetrySeries", "TelemetryPoint",
]
