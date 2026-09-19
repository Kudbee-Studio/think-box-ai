# ADR 001: CNC Manufacturing Intelligence Platform

**Date:** 2026-09-18
**Status:** Accepted
**Supersedes:** None

## Context

Think Box AI needed to extend beyond agent reasoning and scheduling into
physical manufacturing intelligence. CNC (Computer Numerical Control) machines
require structured job definitions, safety gates before execution, multi-tenant
isolation for different customer jobs, and measurable ROI reporting.

The challenge: integrate manufacturing workflows into the existing governed
architecture (ThinkBoxEngine → GovernedEngine → VerifiedRetrySession → DAG →
dashboard) without introducing new runtime dependencies or violating layer
discipline.

## Options Considered

1. **External manufacturing service** — separate microservice for CNC jobs
2. **Embedded module with external SDK** — CNC module that calls vendor APIs
3. **Embedded self-contained module** — CNC logic entirely within Think Box,
   reusing existing infrastructure (adopted)

## Decision

Build CNC as an embedded module (`thinkbox/cnc/`) using only standard library
and existing Think Box components. No new external dependencies.

Key design decisions:
- **No autonomous execution** — human approval required via SafetyGate before
  any production job runs
- **Evidence labeling** — all data labeled as "simulated", "inferred",
  "verified", or "physically_measured"
- **Tenant isolation** — TenantBoundary and TenantStore ensure customer data
  remains isolated
- **Replayable** — every job persists and can be replayed via ReplayDriver
- **Proof packages** — every decision produces an auditable ProofPackage

## Consequences

- **Positive**: Zero new dependencies, full traceability, safety-first design
- **Positive**: Reuses dashboard, ledger, memory, and replay infrastructure
- **Negative**: Physical validation requires separate infrastructure (UpCloud
  agents, sensor feeds) — currently all evidence is "simulated"
- **Negative**: No real-time machine telemetry integration yet (Phase 2+)

## Modules

| Module | Purpose |
|--------|---------|
| `job.py` | CNCJob, Material, Tool, MachineProfile, Operation, ValidationResult, ApprovalRecord, ExecutionRecord, InspectionResult |
| `memory.py` | ManufacturingMemory, KnowledgeEntry (persistent knowledge across jobs) |
| `proof.py` | ProofPackage, ProofStore (evidence packages for every decision) |
| `adapter.py` | CADInterface, MachineControllerInterface, InspectionSystemInterface, SimulatorInterface, ShopDatabaseInterface, CNCAdapterRegistry |
| `safety.py` | ApprovalGate, SafetyGate, SafetyGateStore (human approval before execution) |
| `tenant.py` | Tenant, TenantPermission, TenantBoundary, TenantStore (multi-tenant isolation) |
| `dashboard.py` | ROIStats, ROIDashboard (measurable business value) |
| `demo.py` | DemoMode, DemoResult (deterministic end-to-end demonstration) |
| `engine.py` | CNCManufacturingEngine (wires all subsystems) |
| `__init__.py` | All exports |

## Testing

59 unit tests covering all modules (`tests/unit/test_cnc.py`), all passing.
Full suite integration verified (1435 tests, 6 skipped).
