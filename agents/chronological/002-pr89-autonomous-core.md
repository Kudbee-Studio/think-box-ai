# PR89: Autonomous Agent Core — Implementation Plan

**Date:** Planned (Post-PR88)  
**Status:** PLANNED  
**Branch:** `feat/kilo-agent-core-pr89` (to be created)  
**PR:** #89 (to be created)  

---

## Objective

Implement the autonomous agent core: kernel, lifecycle, protocol, governance client, telemetry emitter, and orchestration client. This is the first code PR for the agent framework.

---

## Scope

### Implementation Deliverables

| Component | File/Module | Description |
|-----------|-------------|-------------|
| **Agent Kernel** | `thinkbox/agent/kernel.py` | Base `AgentKernel` class, identity, lifecycle state machine |
| **Lifecycle Manager** | `thinkbox/agent/lifecycle.py` | State transitions, governance checkpoints, transition validation |
| **Protocol Layer** | `thinkbox/agent/protocol/` | gRPC/HTTP servers, Protobuf definitions, client stubs |
| **Scheduler Client** | `thinkbox/agent/scheduler_client.py` | Work pull, heartbeat, capacity reporting, outcome reporting |
| **Governance Client** | `thinkbox/agent/governance_client.py` | Admission checks, approval requests, audit logging, token management |
| **Telemetry Emitter** | `thinkbox/agent/telemetry.py` | Metrics (Prometheus), traces (OTEL), logs (structured), health endpoints |
| **Orchestration Client** | `thinkbox/agent/orchestration_client.py` | Capacity requests, service discovery, config watch, secret injection |
| **Agent Registry** | `thinkbox/agent/registry.py` | Agent registration, discovery, health tracking |
| **Base Agent Classes** | `thinkbox/agent/base/` | `TaskAgent`, `WorkflowAgent`, `BatchAgent`, `StreamAgent` |

### Protocol Implementation

| Protocol | Transport | Schema | Status |
|----------|-----------|--------|--------|
| Agent ↔ Scheduler | gRPC + HTTP | `protocol/scheduler.proto` | To implement |
| Agent ↔ Admission Gate | gRPC | `protocol/governance.proto` | To implement |
| Agent ↔ Orchestration | gRPC | `protocol/orchestration.proto` | To implement |
| Agent ↔ CNC Platform | gRPC | `protocol/cnc.proto` | To implement |
| Telemetry | OTLP/HTTP | Prometheus + OTLP | To implement |
| Health | HTTP + gRPC | `protocol/health.proto` | To implement |

---

## Implementation Order

### Phase 1: Foundation (Week 1)
1. Protobuf schema definitions (`protocol/*.proto`)
2. `AgentKernel` base class with identity & lifecycle
3. `LifecycleManager` with 10-state machine
4. Configuration system (Pydantic settings)

### Phase 2: Protocol Layer (Week 1-2)
5. gRPC server implementation (async, interceptors for auth/tracing)
6. HTTP server for health/metrics (FastAPI)
7. Client stubs for all services
8. Protocol version negotiation

### Phase 3: Scheduler Integration (Week 2)
9. `SchedulerClient` with work pull (long-polling)
10. Heartbeat with command handling (preempt, pause, etc.)
11. Capacity reporting (periodic + on-change)
12. Outcome reporting (immediate on completion)

### Phase 4: Governance Integration (Week 2-3)
13. `GovernanceClient` with admission check (sync, fail-closed)
14. Approval request/response handling
15. Audit event emission (local buffer + async flush)
16. Governance token management (request, cache, renew, revoke)

### Phase 5: Telemetry (Week 3)
17. `TelemetryEmitter` with OpenTelemetry SDK
18. Prometheus metrics exposition (`/metrics`)
19. OTLP trace export (batch processor)
20. Structured JSON logging (with trace correlation)
21. Health endpoints (`/health/live`, `/health/ready`, `/health`)

### Phase 6: Orchestration (Week 3-4)
22. `OrchestrationClient` for capacity requests
23. Service discovery (TTL cache + background refresh)
24. Config watch (long-polling + resume)
25. Secret injection (at startup + rotation callbacks)

### Phase 7: Base Agent Types (Week 4)
26. `TaskAgent` — single task execution
27. `WorkflowAgent` — DAG execution with checkpointing
28. `BatchAgent` — high-throughput batch processing
29. `StreamAgent` — continuous stream processing

### Phase 8: Testing & Integration (Week 4-5)
30. Unit tests for all components (target: 80% coverage)
31. Contract tests for all protocols
32. Integration tests with Governed Scheduler
33. Integration tests with CNC Platform
34. Integration tests with KUDBEE Control Fabric
35. End-to-end test: spawn → register → pull → execute → report

---

## Technical Specifications

### Agent Kernel Class
```python
class AgentKernel:
    def __init__(self, config: AgentConfig):
        self.agent_id = generate_ulid()
        self.config = config
        self.lifecycle = LifecycleManager(self)
        self.scheduler = SchedulerClient(self)
        self.governance = GovernanceClient(self)
        self.telemetry = TelemetryEmitter(self)
        self.orchestration = OrchestrationClient(self)
        self._state = AgentState.SPAWNED
    
    async def initialize(self) -> InitResult:
        # 1. Validate config
        # 2. Connect to platform services
        # 3. Register with scheduler
        # 4. Request governance token
        # 5. Start telemetry emission
        # 6. Start heartbeat
        # 7. Transition to INITIALIZED
    
    async def shutdown(self, reason: ShutdownReason) -> ShutdownResult:
        # 1. Stop accepting work
        # 2. Complete/drain in-flight tasks
        # 3. Release capacity
        # 4. Flush telemetry/audit
        # 5. Deregister from scheduler
        # 6. Transition to TERMINATED
```

### Lifecycle State Machine
```python
class LifecycleManager:
    VALID_TRANSITIONS = {
        AgentState.SPAWNED: [AgentState.INITIALIZED, AgentState.TERMINATED],
        AgentState.INITIALIZED: [AgentState.IDLE, AgentState.EXECUTING, AgentState.TERMINATED],
        AgentState.IDLE: [AgentState.EXECUTING, AgentState.TERMINATED],
        AgentState.EXECUTING: [AgentState.CHECKPOINTED, AgentState.COMPLETED, 
                               AgentState.FAILED, AgentState.CANCELLED, AgentState.TERMINATED],
        AgentState.CHECKPOINTED: [AgentState.EXECUTING, AgentState.TERMINATED],
        AgentState.COMPLETED: [AgentState.IDLE, AgentState.TERMINATED],
        AgentState.FAILED: [AgentState.IDLE, AgentState.TERMINATED],
        AgentState.CANCELLED: [AgentState.IDLE, AgentState.TERMINATED],
        AgentState.TERMINATED: [],  # Terminal
    }
    
    async def transition(self, new_state: AgentState) -> TransitionResult:
        # 1. Validate transition
        # 2. Execute pre-transition hooks (governance checkpoints)
        # 3. Emit telemetry event
        # 4. Update state
        # 5. Execute post-transition hooks
```

### Governance Client (Fail-Closed)
```python
class GovernanceClient:
    async def check_admission(self, action: ActionRequest) -> AdmissionDecision:
        # 1. Build request with agent/task context
        # 2. Call AdmissionGate gRPC (timeout: 5s)
        # 3. On timeout/error: DENY (fail-closed)
        # 4. If allowed: cache token, return decision
        # 5. Emit audit event (async)
    
    async def request_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        # 1. Submit to ApprovalService
        # 2. Wait for decision (with timeout)
        # 3. Return decision + token
```

---

## Testing Requirements

### Unit Tests (Minimum)
| Module | Min Tests | Focus |
|--------|-----------|-------|
| `kernel.py` | 15 | Identity, config, init/shutdown |
| `lifecycle.py` | 20 | All transitions, invalid transitions, checkpoints |
| `scheduler_client.py` | 15 | Pull, heartbeat, capacity, outcome |
| `governance_client.py` | 20 | Admission (allow/deny/timeout), approval, tokens |
| `telemetry.py` | 15 | Metrics, traces, logs, health |
| `orchestration_client.py` | 15 | Capacity, discovery, config, secrets |
| `base/*.py` | 10 each | Agent type behaviors |

### Contract Tests
- Protobuf serialization/deserialization
- gRPC service contract compliance
- HTTP API contract compliance
- Protocol version negotiation

### Integration Tests
- With Governed Scheduler (work pull, preemption, capacity)
- With Admission Gate (allow, deny, timeout, revocation)
- With Action Ledger (audit event persistence, verification)
- With CNC Platform (job submit, telemetry, proof)
- With Orchestration (capacity grant, service discovery, config)

---

## FourState Target

| Phase | Target |
|-------|--------|
| **CODE_COMPLETE** | ✅ All modules implemented |
| **TEST_VERIFIED** | ✅ Unit + contract + integration tests passing |
| **LIVE_VERIFIED** | ✅ Running on Upstash Box, registered with scheduler |
| **PRODUCTION_READY** | ⏳ After PR90 (multi-agent) |

---

## Dependencies

### New Dependencies (to add to pyproject.toml)
```toml
dependencies = [
    # ... existing ...
    "grpcio>=1.60",
    "grpcio-tools>=1.60",
    "protobuf>=4.24",
    "opentelemetry-api>=1.20",
    "opentelemetry-sdk>=1.20",
    "opentelemetry-exporter-otlp>=1.20",
    "opentelemetry-instrumentation-fastapi>=0.42",
    "prometheus-client>=0.17",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
]
```

### Existing Dependencies (reused)
- `thinkbox.scheduler` — SchedulerHarness, admission
- `thinkbox.cnc` — CNC job types, safety gates
- `core.providers` — Model providers
- `core.memory` — Memory store
- `core.ledger` — Action ledger

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| gRPC complexity | Medium | High | Start with HTTP fallback, migrate to gRPC |
| Governance latency | High | High | Local policy cache, async audit |
| Telemetry overhead | Medium | Medium | Sampling, batching, budget enforcement |
| State machine bugs | Medium | High | Formal verification (TLA+), property tests |
| Protocol versioning | Low | High | Strict semver, compatibility tests |

---

## References

- `agents/core/agent-kernel.md` — Kernel specification
- `agents/core/agent-lifecycle.md` — Lifecycle specification
- `agents/core/agent-categories.md` — Agent types
- `agents/core/execution-boundaries.md` — Resource limits
- `agents/core/cloud-interaction-model.md` — PAL interfaces
- `agents/governance/governance-hooks.md` — Governance integration
- `agents/telemetry/telemetry-expectations.md` — Telemetry requirements
- `agents/integration/scheduler-integration.md` — Scheduler protocol
- `agents/integration/cloud-orchestration.md` — Orchestration protocol
- `agents/integration/protocol-responsibilities.md` — All protobuf schemas