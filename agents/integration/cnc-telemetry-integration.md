# KILO Cloud Agent CNC Telemetry Integration — Manufacturing Intelligence

**Purpose:** Defines how KILO Cloud Agents (specifically CNC_AGENT category) integrate with the CNC Manufacturing Intelligence Platform (PR86-87) for telemetry, job tracking, and evidence-based manufacturing.

---

## CNC Integration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CNC_AGENT                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  CNC Client                                             │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │   │
│  │  │  Job     │ │ Telemetry│ │  Proof   │ │  Safety    │  │   │
│  │  │  Submit  │ │  Stream  │ │  Package │ │  Gateway   │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              CNC MANUFACTURING INTELLIGENCE (PR86-87)           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────────┐  │
│  │  CNC Job │ │ Memory   │ │ Proof    │ │ Safety Gate        │  │
│  │  Manager │ │ Store    │ │ Store    │ │ (ApprovalGate)     │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────────┐  │
│  │ Adapter  │ │ Tenant   │ │ Dashboard│ │ Demo/Replay        │  │
│  │ Registry │ │ Store    │ │ (ROI)    │ │ Engine             │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## CNC Agent Capabilities

### Declared Capabilities (at registration)
```json
{
  "capabilities": [
    "cnc.job.planning",
    "cnc.toolpath.generation", 
    "cnc.simulation",
    "cnc.safety.validation",
    "cnc.inspection.planning",
    "cnc.material.optimization",
    "cnc.proof.generation",
    "cnc.replay.execution"
  ],
  "resource_profile": {
    "cpu_cores": 4,
    "memory_mb": 8192,
    "gpu_required": true,
    "gpu_type": "L4",
    "network_egress": true,
    "max_duration_seconds": 7200
  }
}
```

---

## Job Submission Flow

### 1. Job Creation (via CNC Client)
```python
class CNCClient(Protocol):
    async def submit_job(self, job: CNCJobSpec) -> JobSubmissionResult: ...
    async def get_job_status(self, job_id: str) -> CNCJobStatus: ...
    async def stream_telemetry(self, job_id: str) -> AsyncIterator[TelemetryEvent]: ...
    async def request_approval(self, request: SafetyApprovalRequest) -> ApprovalResult: ...
    async def submit_proof(self, proof: ProofPackage) -> ProofReceipt: ...
    async def replay_job(self, job_id: str, config: ReplayConfig) -> ReplayResult: ...

class CNCJobSpec:
    job_id: str
    tenant_id: str
    part_spec: PartSpecification
    material: MaterialSpec
    machine: MachineProfile
    operations: list[Operation]
    quality_requirements: QualitySpec
    safety_requirements: SafetySpec
    evidence_requirements: EvidenceSpec
```

### 2. Job Planning (Agent Execution)
- Agent receives `cnc.job.planning` task
- Generates toolpaths using `MachineAdapter` (SimMachineAdapter or real)
- Validates against `SafetyGate` (collision, limits, tooling)
- Produces `CNCJob` with `ValidationResult`

### 3. Approval Gate (Human-in-the-Loop)
```json
{
  "approval_request": {
    "request_id": "uuid",
    "job_id": "uuid",
    "gate_type": "SAFETY_GATE",
    "risk_level": "HIGH",
    "validation_result": {...},
    "simulation_artifact": "s3://bucket/sim/job_xyz.glb",
    "estimated_cost_usd": 1250.00,
    "estimated_duration_hours": 4.5,
    "expires_at": "2026-09-19T08:00:00Z"
  }
}
```
- Requires `APPROVAL_AGENT` routing to manufacturing engineer
- `SafetyGateStore` persists approval decision
- No execution without `APPROVED` status

### 4. Execution & Telemetry Streaming
```json
{
  "telemetry_event": {
    "job_id": "uuid",
    "timestamp": "2026-09-19T04:00:00Z",
    "event_type": "OPERATION_START",
    "operation_id": "op_001",
    "machine_state": {
      "position": {"x": 0, "y": 0, "z": 0},
      "spindle_rpm": 12000,
      "feed_rate": 500,
      "tool_id": "T01"
    },
    "sensor_data": {
      "vibration": 0.02,
      "temperature": 45,
      "power_draw": 2.3
    }
  }
}
```
- Streamed via `TelemetryEvent` to CNC Memory Store
- Real-time dashboard updates
- Anomaly detection (vibration, temp, power)

### 5. Proof Package Generation
```json
{
  "proof_package": {
    "job_id": "uuid",
    "package_id": "uuid",
    "evidence": [
      {"type": "SIMULATION", "artifact_ref": "s3://...", "hash": "sha256:..."},
      {"type": "TOOLPATH", "artifact_ref": "s3://...", "hash": "sha256:..."},
      {"type": "VALIDATION", "artifact_ref": "s3://...", "hash": "sha256:..."},
      {"type": "APPROVAL", "artifact_ref": "s3://...", "hash": "sha256:..."},
      {"type": "TELEMETRY", "artifact_ref": "s3://...", "hash": "sha256:..."},
      {"type": "INSPECTION", "artifact_ref": "s3://...", "hash": "sha256:..."}
    ],
    "merkle_root": "sha256:...",
    "timestamp": "2026-09-19T08:30:00Z",
    "classification": "VERIFIED"
  }
}
```
- Submitted to `ProofStore` (immutable, tamper-evident)
- Linked to `ActionLedger` for audit trail
- Enables `ReplayDriver` for exact reproduction

---

## Telemetry Schema (CNC-Specific)

### Machine Telemetry
| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `kilo_cnc_machine_position` | Gauge | `job_id`, `machine_id`, `axis` | Current position (mm) |
| `kilo_cnc_spindle_rpm` | Gauge | `job_id`, `machine_id` | Spindle speed |
| `kilo_cnc_feed_rate` | Gauge | `job_id`, `machine_id` | Feed rate (mm/min) |
| `kilo_cnc_tool_wear` | Gauge | `job_id`, `tool_id` | Wear (mm) |
| `kilo_cnc_vibration` | Gauge | `job_id`, `machine_id`, `axis` | Vibration (g) |
| `kilo_cnc_temperature` | Gauge | `job_id`, `machine_id`, `sensor` | Temperature (°C) |
| `kilo_cnc_power_draw` | Gauge | `job_id`, `machine_id` | Power (kW) |
| `kilo_cnc_coolant_flow` | Gauge | `job_id`, `machine_id` | Flow rate (L/min) |

### Job Progress
| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `kilo_cnc_job_progress_percent` | Gauge | `job_id` | Overall progress |
| `kilo_cnc_operation_duration_seconds` | Histogram | `job_id`, `operation_id` | Operation time |
| `kilo_cnc_material_removed_kg` | Counter | `job_id`, `material` | Material removed |
| `kilo_cnc_tool_changes_total` | Counter | `job_id` | Tool changes |
| `kilo_cnc_quality_checks_total` | Counter | `job_id`, `check_type`, `result` | Quality checks |

### Safety & Compliance
| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `kilo_cnc_safety_violations_total` | Counter | `job_id`, `violation_type` | Safety violations |
| `kilo_cnc_approval_requests_total` | Counter | `job_id`, `gate_type`, `decision` | Approval outcomes |
| `kilo_cnc_approval_latency_seconds` | Histogram | `job_id`, `gate_type` | Approval wait time |

---

## Evidence Classification (PR86-87)

All CNC data carries evidence classification:

| Classification | Description | Examples |
|----------------|-------------|----------|
| **SIMULATED** | Generated by simulation | Toolpath sim, physics sim |
| **INFERRED** | Derived from models | Tool wear prediction, thermal model |
| **VERIFIED** | Measured/confirmed | Probe measurement, inspection |
| **PHYSICALLY_MEASURED** | Direct physical measurement | CMM inspection, weigh scale |

### Evidence in Telemetry
```json
{
  "measurement": "diameter",
  "value": 25.001,
  "unit": "mm",
  "classification": "PHYSICALLY_MEASURED",
  "source": "CMM_ZEISS_CONTURA",
  "confidence": 0.999,
  "timestamp": "2026-09-19T08:15:00Z",
  "traceability": {
    "standard": "ISO_10360",
    "certificate": "CAL_2026_001",
    "expiry": "2027-01-15"
  }
}
```

---

## Tenant Isolation (PR86-87)

- Each tenant has isolated `TenantBoundary`
- `TenantStore` enforces data isolation
- CNC_AGENT declares `tenant_id` at registration
- All job data, proofs, telemetry scoped to tenant
- Cross-tenant access requires `TENANT_OPERATION` approval

---

## ROI Dashboard Integration

CNC_AGENT emits metrics for `ROIDashboard`:
```json
{
  "roi_metrics": {
    "job_id": "uuid",
    "material_cost_usd": 150.00,
    "tooling_cost_usd": 85.00,
    "machine_time_cost_usd": 420.00,
    "labor_cost_usd": 200.00,
    "total_cost_usd": 855.00,
    "estimated_sale_price_usd": 2500.00,
    "roi_percent": 192.4,
    "cycle_time_hours": 4.5,
    "quality_score": 0.98,
    "first_pass_yield": true
  }
}
```

---

## Replay & Self-Improvement

### Replay Driver
```python
class ReplayDriver(Protocol):
    async def replay(self, job_id: str, config: ReplayConfig) -> ReplayResult: ...
    async def compare(self, original_id: str, replay_id: str) -> ComparisonReport: ...

class ReplayConfig:
    mode: "EXACT" | "MODIFIED_PARAMS" | "DIFFERENT_MACHINE"
    parameter_overrides: dict
    machine_profile: MachineProfile | None
```

### Self-Improvement Loop
- `SelfImprovementLoop` compares outcomes across jobs
- Identifies parameter optimizations
- Feeds back to `CNCJob` planning for future jobs
- `CNC_AGENT` receives improved parameters via `MemoryStore`

---

## Metrics for CNC Integration

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `kilo_cnc_jobs_total` | Counter | `agent_id`, `tenant_id`, `outcome` | Jobs completed |
| `kilo_cnc_job_duration_seconds` | Histogram | `agent_id`, `part_type` | Job cycle time |
| `kilo_cnc_simulation_accuracy` | Gauge | `agent_id`, `simulation_type` | Sim vs actual |
| `kilo_cnc_first_pass_yield` | Gauge | `agent_id`, `tenant_id` | FPY rate |
| `kilo_cnc_rework_rate` | Gauge | `agent_id`, `tenant_id` | Rework % |
| `kilo_cnc_proof_packages_total` | Counter | `agent_id`, `classification` | Proofs generated |
| `kilo_cnc_replay_comparisons_total` | Counter | `agent_id`, `result` | Replay comparisons |

---

## Implementation Requirements (PR89+)

- CNC Client: Shared library (Python/Go)
- Telemetry: High-frequency (100Hz) streaming via WebSocket/gRPC
- Proof generation: Async, non-blocking execution path
- Safety gate: Integrated with `APPROVAL_AGENT` (human + policy)
- Tenant isolation: Enforced at CNC Client layer
- Replay: Deterministic (same inputs → same outputs)
- Evidence: Classification mandatory on all measurements

---

## References

- `core/agent-categories.md` — CNC_AGENT definition
- `core/cloud-interaction-model.md` — Machine adapter cloud integration
- `governance/governance-hooks.md` — Safety gate as admission gate
- `governance/approval-gates.md` — Human approval for execution
- `governance/audit-logging.md` — Proof packages in audit trail
- `telemetry/telemetry-expectations.md` — CNC telemetry profile
- `telemetry/metrics-contract.md` — CNC metrics schema