# KILO Cloud Agent Kernel — Core Definition

**Purpose:** Defines the agent kernel — the foundational abstraction that all KILO Cloud Agents implement. This is the single source of truth for agent identity, responsibilities, and operational model.

---

## Agent Kernel Definition

A **KILO Cloud Agent** is an autonomous, governed execution unit that:

1. **Operates within a defined execution boundary** (sandbox, resource limits, permission scope)
2. **Exposes a standardized protocol interface** for task ingestion, status reporting, and result emission
3. **Integrates with governance infrastructure** (approval gates, audit logging, compliance checks)
4. **Emits structured telemetry** (metrics, traces, health signals) continuously
5. **Persists state durably** via the KILO persistence layer (SQLite/Vector/Object store)
6. **Participates in the agent lifecycle** (spawn → initialize → execute → checkpoint → terminate)

---

## Kernel Responsibilities

| Responsibility | Description | Mandatory |
|----------------|-------------|-----------|
| **Task Ingestion** | Accept work via standardized protocol (JSON-RPC / gRPC / HTTP) | ✅ |
| **Execution Control** | Start, pause, resume, cancel execution within boundaries | ✅ |
| **State Management** | Maintain durable execution state (checkpoints, context, artifacts) | ✅ |
| **Governance Compliance** | Request approvals, emit audit events, respect policy decisions | ✅ |
| **Telemetry Emission** | Emit metrics, traces, logs, health signals per contract | ✅ |
| **Resource Accounting** | Report CPU, memory, network, GPU, API call consumption | ✅ |
| **Error Handling** | Structured error propagation with context (agent_id, task_id, etc.) | ✅ |
| **Protocol Adherence** | Implement required protocol methods & message formats | ✅ |

---

## Agent Identity

Every agent carries an immutable identity document:

```json
{
  "agent_id": "uuid-v4",
  "agent_type": "string",           // From agent-categories.md taxonomy
  "agent_version": "semver",        // Agent code version
  "protocol_version": "semver",     // Protocol interface version
  "capabilities": ["string"],       // Declared capability identifiers
  "resource_profile": {             // Declared resource requirements
    "cpu_cores": "number",
    "memory_mb": "number",
    "gpu_required": "boolean",
    "network_egress": "boolean",
    "max_duration_seconds": "number"
  },
  "governance_tier": "string",      // GOVERNED / RESTRICTED / PRIVILEGED
  "created_at": "ISO8601",
  "created_by": "string"            // Human / system / agent identifier
}
```

---

## Execution Model

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENT KERNEL                              │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Protocol   │  │  Execution  │  │    Governance       │  │
│  │  Adapter    │──▶│  Controller │──▶│    Interface        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│         ▲               │                    ▲               │
│         │               ▼                    │               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   State     │  │  Telemetry  │  │    Resource         │  │
│  │  Manager    │  │  Emitter    │  │    Accountant       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Execution Phases

| Phase | Description | Governance Check | Telemetry |
|-------|-------------|------------------|-----------|
| **SPAWN** | Agent process/container created | Pre-spawn admission | `agent.spawned` |
| **INITIALIZE** | Load config, connect deps, register | Capability verification | `agent.initialized` |
| **AWAIT_TASK** | Idle, waiting for work assignment | None | `agent.idle` |
| **EXECUTE** | Active task processing | Per-action approval gates | `agent.executing` |
| **CHECKPOINT** | Persist intermediate state | State integrity verification | `agent.checkpoint` |
| **COMPLETE** | Task finished, results emitted | Result validation | `agent.completed` |
| **TERMINATE** | Graceful shutdown, cleanup | Resource release verification | `agent.terminated` |

---

## Protocol Interface (Abstract)

All agents MUST implement this interface:

```python
class AgentKernel(Protocol):
    # Lifecycle
    async def initialize(self, config: AgentConfig) -> InitResult: ...
    async def shutdown(self, reason: ShutdownReason) -> ShutdownResult: ...
    
    # Task handling
    async def accept_task(self, task: TaskSpec) -> TaskAcceptance: ...
    async def cancel_task(self, task_id: str, reason: str) -> CancelResult: ...
    async def get_task_status(self, task_id: str) -> TaskStatus: ...
    
    # State
    async def checkpoint(self, task_id: str) -> CheckpointResult: ...
    async def restore(self, checkpoint_id: str) -> RestoreResult: ...
    
    # Governance
    async def request_approval(self, action: ActionRequest) -> ApprovalResult: ...
    async def report_audit(self, event: AuditEvent) -> None: ...
    
    # Telemetry
    async def emit_metrics(self, metrics: MetricsBatch) -> None: ...
    async def emit_trace(self, span: TraceSpan) -> None: ...
    async def report_health(self) -> HealthReport: ...
    
    # Resources
    async def get_resource_usage(self) -> ResourceUsage: ...
    async def set_resource_limits(self, limits: ResourceLimits) -> None: ...
```

---

## Non-Goals (PR88)

- ❌ No specific agent implementations
- ❌ No protocol wire format (JSON-RPC vs gRPC vs HTTP)
- ❌ No scheduler integration logic
- ❌ No multi-agent coordination primitives
- ❌ No agent marketplace or discovery

These are addressed in PR89+.

---

## References

- `agent-lifecycle.md` — Detailed lifecycle state machine
- `agent-categories.md` — Agent taxonomy & type definitions
- `execution-boundaries.md` — Sandbox & resource isolation
- `governance/governance-hooks.md` — Governance integration points
- `telemetry/telemetry-expectations.md` — Required telemetry signals
- `integration/protocol-responsibilities.md` — Protocol duties & formats