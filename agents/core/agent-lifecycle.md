# KILO Cloud Agent Lifecycle — State Machine & Transitions

**Purpose:** Defines the complete lifecycle of a KILO Cloud Agent from spawn to termination, including all valid state transitions, governance checkpoints, and telemetry requirements.

---

## Lifecycle States

```
                    ┌─────────────┐
                    │   SPAWNED   │
                    └──────┬──────┘
                           │ initialize()
                           ▼
                    ┌─────────────┐
                    │ INITIALIZED │
                    └──────┬──────┘
                           │ accept_task()
                           ▼
              ┌────────────┴────────────┐
              ▼                         ▼
       ┌─────────────┐            ┌─────────────┐
       │  EXECUTING  │            │   IDLE      │
       └──────┬──────┘            └──────┬──────┘
              │                          │
              │ checkpoint()             │ accept_task()
              ▼                          ▼
       ┌─────────────┐            ┌─────────────┐
       │ CHECKPOINTED│            │  EXECUTING  │
       └──────┬──────┘            └──────┬──────┘
              │                          │
              │ restore()                │ complete()/fail()
              ▼                          ▼
       ┌─────────────┐            ┌─────────────┐
       │  EXECUTING  │            │  COMPLETED  │
       └──────┬──────┘            └──────┬──────┘
              │                          │
              │ cancel()                 │ shutdown()
              ▼                          ▼
       ┌─────────────┐            ┌─────────────┐
       │  CANCELLED  │            │  TERMINATED │
       └─────────────┘            └─────────────┘
```

---

## State Definitions

| State | Description | Valid Transitions | Governance Required |
|-------|-------------|-------------------|---------------------|
| **SPAWNED** | Process/container created, not yet initialized | → INITIALIZED | Pre-spawn admission gate |
| **INITIALIZED** | Config loaded, dependencies connected, registered | → IDLE, → EXECUTING | Capability verification |
| **IDLE** | Ready, awaiting task assignment | → EXECUTING, → TERMINATED | None |
| **EXECUTING** | Actively processing a task | → CHECKPOINTED, → COMPLETED, → CANCELLED, → FAILED | Per-action approval gates |
| **CHECKPOINTED** | Intermediate state persisted | → EXECUTING (restore), → TERMINATED | State integrity check |
| **COMPLETED** | Task finished successfully | → IDLE, → TERMINATED | Result validation |
| **FAILED** | Task failed with error | → IDLE (retry), → TERMINATED | Error classification |
| **CANCELLED** | Task cancelled by request | → IDLE, → TERMINATED | Cancellation audit |
| **TERMINATED** | Agent shut down, resources released | (terminal) | Resource release verification |

---

## Transition Details

### SPAWNED → INITIALIZED
- **Trigger:** `initialize(config)` called
- **Actions:** Load configuration, establish connections, register with orchestration, verify capabilities
- **Governance:** Pre-spawn admission gate must approve (resource quota, policy compliance)
- **Telemetry:** `agent.initialized` event with config hash, capability list
- **Timeout:** 30 seconds default
- **Failure:** → TERMINATED with `INITIALIZATION_FAILED`

### INITIALIZED → IDLE
- **Trigger:** Initialization complete, no immediate task
- **Actions:** Enter wait loop, advertise availability
- **Governance:** None
- **Telemetry:** `agent.idle` event

### INITIALIZED → EXECUTING
- **Trigger:** Task assigned during initialization (batch mode)
- **Actions:** Begin task execution immediately
- **Governance:** Task admission gate
- **Telemetry:** `agent.executing` event with task_id

### IDLE → EXECUTING
- **Trigger:** `accept_task(task_spec)` called
- **Actions:** Validate task, allocate resources, begin execution
- **Governance:** Task admission gate (resource quota, policy, priority)
- **Telemetry:** `agent.task_accepted`, `agent.executing` events

### EXECUTING → CHECKPOINTED
- **Trigger:** `checkpoint(task_id)` called (periodic or on signal)
- **Actions:** Persist execution state, context, intermediate results
- **Governance:** State integrity verification (hash, schema)
- **Telemetry:** `agent.checkpoint` event with checkpoint_id, size
- **Frequency:** Configurable (default: every 60s or on state change)

### EXECUTING → COMPLETED
- **Trigger:** Task completes successfully
- **Actions:** Emit results, release task resources, update metrics
- **Governance:** Result validation gate (schema, policy, quality)
- **Telemetry:** `agent.completed` event with result_ref, duration, resource_usage

### EXECUTING → FAILED
- **Trigger:** Task encounters unrecoverable error
- **Actions:** Capture error context, emit failure event, preserve state for debugging
- **Governance:** Error classification gate (retryable vs terminal)
- **Telemetry:** `agent.failed` event with error_type, context, stack_trace_ref

### EXECUTING → CANCELLED
- **Trigger:** `cancel_task(task_id, reason)` called
- **Actions:** Interrupt execution, preserve partial state, release resources
- **Governance:** Cancellation audit (who, why, impact)
- **Telemetry:** `agent.cancelled` event with reason, partial_progress

### CHECKPOINTED → EXECUTING
- **Trigger:** `restore(checkpoint_id)` called
- **Actions:** Load state, verify integrity, resume execution
- **Governance:** State integrity verification
- **Telemetry:** `agent.restored` event with checkpoint_id

### COMPLETED/FAILED/CANCELLED → IDLE
- **Trigger:** Agent ready for next task (pooled mode)
- **Actions:** Clean task-specific resources, reset execution context
- **Governance:** None
- **Telemetry:** `agent.idle` event

### ANY → TERMINATED
- **Trigger:** `shutdown(reason)` called or forced termination
- **Actions:** Flush telemetry, release all resources, persist final state, deregister
- **Governance:** Resource release verification (no leaks)
- **Telemetry:** `agent.terminated` event with reason, final_metrics, uptime
- **Timeout:** 60 seconds graceful, then forced

---

## Governance Checkpoints

| Checkpoint | Phase | Policy Evaluated | Failure Action |
|------------|-------|------------------|----------------|
| **Pre-spawn Admission** | SPAWNED→INITIALIZED | Resource quota, agent policy, tenant limits | Block spawn |
| **Capability Verification** | INITIALIZED | Declared vs actual capabilities, version compatibility | Block initialization |
| **Task Admission** | IDLE→EXECUTING | Resource availability, priority, policy, dependencies | Queue or reject task |
| **Action Approval** | EXECUTING (per action) | Action-specific policy (shell, network, data access) | Block action, emit audit |
| **Result Validation** | EXECUTING→COMPLETED | Output schema, quality thresholds, policy compliance | Quarantine result |
| **Error Classification** | EXECUTING→FAILED | Retryable vs terminal, blast radius, escalation | Determine retry/terminate |
| **State Integrity** | CHECKPOINTED, RESTORE | Hash verification, schema compliance, tamper evidence | Block restore, alert |
| **Resource Release** | ANY→TERMINATED | No orphaned resources, quota returned, cleanup complete | Alert, manual intervention |

---

## Telemetry Requirements Per Transition

| Transition | Required Events | Required Metrics |
|------------|-----------------|------------------|
| SPAWNED→INITIALIZED | `agent.spawned`, `agent.initialized` | `agent_init_duration_ms`, `agent_capability_count` |
| INITIALIZED→IDLE | `agent.idle` | `agent_idle_duration_ms` |
| IDLE→EXECUTING | `agent.task_accepted`, `agent.executing` | `task_queue_wait_ms`, `agent_active` |
| EXECUTING→CHECKPOINTED | `agent.checkpoint` | `checkpoint_size_bytes`, `checkpoint_duration_ms` |
| EXECUTING→COMPLETED | `agent.completed` | `task_duration_ms`, `task_resource_usage`, `task_result_size` |
| EXECUTING→FAILED | `agent.failed` | `task_duration_ms`, `error_count`, `error_type_distribution` |
| EXECUTING→CANCELLED | `agent.cancelled` | `task_duration_ms`, `cancellation_reason` |
| ANY→TERMINATED | `agent.terminated` | `agent_uptime_ms`, `total_tasks`, `total_errors`, `resource_leaks` |

---

## Error Handling

### Structured Error Format
All errors MUST include:
```json
{
  "error_id": "uuid",
  "agent_id": "uuid",
  "task_id": "uuid|null",
  "timestamp": "ISO8601",
  "error_type": "string",        // From error taxonomy
  "error_code": "string",        // Machine-readable code
  "message": "string",           // Human-readable
  "context": {},                 // Relevant execution context
  "retryable": "boolean",
  "blast_radius": "string",      // TASK / AGENT / TENANT / PLATFORM
  "remediation": "string|null"   // Suggested action
}
```

### Error Taxonomy
| Category | Codes | Retryable | Blast Radius |
|----------|-------|-----------|--------------|
| **RESOURCE** | `OOM`, `CPU_THROTTLE`, `DISK_FULL`, `QUOTA_EXCEEDED` | Yes (after backoff) | AGENT |
| **NETWORK** | `CONNECTION_TIMEOUT`, `DNS_FAILURE`, `TLS_ERROR` | Yes (exponential backoff) | TASK |
| **DEPENDENCY** | `SERVICE_UNAVAILABLE`, `VERSION_MISMATCH`, `AUTH_FAILED` | Conditional | TASK/AGENT |
| **VALIDATION** | `SCHEMA_VIOLATION`, `POLICY_DENIED`, `QUALITY_THRESHOLD` | No | TASK |
| **INTERNAL** | `BUG`, `PANIC`, `CORRUPTION` | No | AGENT/PLATFORM |
| **GOVERNANCE** | `APPROVAL_DENIED`, `AUDIT_FAILURE`, `COMPLIANCE_VIOLATION` | No | TENANT/PLATFORM |

---

## Implementation Notes (PR89+)

- State machine MUST be implemented as a formal verifiable model (TLA+ / statecharts)
- All transitions MUST emit telemetry before completing
- Governance checkpoints MUST be synchronous (block until decision)
- Checkpoint/restore MUST be tested for every agent type
- Termination MUST be idempotent and handle partial failures

---

## References

- `agent-kernel.md` — Kernel responsibilities & identity
- `execution-boundaries.md` — Resource limits & sandboxing
- `governance/governance-hooks.md` — Governance integration details
- `governance/approval-gates.md` — Approval gate specifications
- `telemetry/telemetry-expectations.md` — Telemetry signal contracts