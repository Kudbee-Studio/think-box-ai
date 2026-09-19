# KILO Cloud Agent Governance Hooks — Integration Points

**Purpose:** Defines the governance integration points that all KILO Cloud Agents must implement. These hooks connect agents to the KUDBEE Control Fabric (Phase 12) and ensure every side effect passes through admission control.

---

## Governance Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      AGENT                                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 Governance Client                        │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │   │
│  │  │ Admission│ │  Audit   │ │  Policy  │ │  Token     │  │   │
│  │  │  Gate    │ │  Logger  │ │  Evaluator│ │  Manager   │  │   │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬──────┘  │   │
│  └───────┼────────────┼────────────┼────────────┼───────────┘   │
└──────────┼────────────┼────────────┼────────────┼────────────────┘
           │            │            │            │
           ▼            ▼            ▼            ▼
    ┌─────────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐
    │ Admission   │ │ Action  │ │ Policy  │ │ Governance│
    │ Service     │ │ Ledger  │ │ Engine  │ │ Token Svc │
    │ (Gate)      │           │ (OPA)   │             │
    └─────────────┘ └─────────┘ └─────────┘ └──────────┘
```

---

## Admission Gates

Every agent action that produces a side effect MUST pass through an **Admission Gate** before execution.

### Gate Protocol

```python
class AdmissionGate(Protocol):
    async def check(self, request: AdmissionRequest) -> AdmissionDecision: ...

class AdmissionRequest:
    agent_id: str
    task_id: str | None
    action_type: str              # From action taxonomy
    action_spec: dict             # Action-specific parameters
    governance_token: str | None  # Required for execution
    tenant_id: str
    timestamp: datetime

class AdmissionDecision:
    allowed: bool
    decision_id: str
    reason: str
    conditions: list[Condition]   # Must be met during execution
    expires_at: datetime | None
    governance_token: str | None  # Issued if allowed
```

### Action Taxonomy (Requires Admission)

| Action Type | Description | Example | Default Policy |
|-------------|-------------|---------|----------------|
| **SHELL_EXEC** | Execute shell command | `shell.exec` | RESTRICTED |
| **NETWORK_EGRESS** | Outbound network call | HTTP, database, API | GOVERNED |
| **FILE_WRITE** | Write to durable storage | Artifact, log, checkpoint | GOVERNED |
| **FILE_READ_SENSITIVE** | Read secrets/config | Vault, .env, certs | RESTRICTED |
| **PROCESS_SPAWN** | Spawn child process | Subprocess, container | RESTRICTED |
| **CLOUD_API** | Cloud provider API call | Provision, resize, snapshot | PRIVILEGED |
| **GPU_ALLOCATE** | Request GPU allocation | ML training, rendering | PRIVILEGED |
| **AGENT_SPAWN** | Spawn another agent | Supervisor scaling | PRIVILEGED |
| **LEDGER_WRITE** | Write to action ledger | Audit, compliance | GOVERNED |
| **MEMORY_WRITE_ORG** | Write to organizational memory | Learned knowledge | GOVERNED |
| **POLICY_CHANGE** | Modify policy rules | OPA rule update | PRIVILEGED |
| **TENANT_OPERATION** | Cross-tenant action | Data share, migration | PRIVILEGED |

### Action NOT Requiring Admission
| Action Type | Description |
|-------------|-------------|
| **COMPUTE_PURE** | Pure computation (no I/O) |
| **MEMORY_READ** | Read from session/task memory |
| **MEMORY_WRITE_SESSION** | Write to session/task memory |
| **METRICS_EMIT** | Emit telemetry metrics |
| **LOG_EMIT** | Emit structured logs |
| **CHECKPOINT_CREATE** | Create execution checkpoint |

---

## Governance Token Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   AGENT     │────▶│  ADMISSION  │────▶│  GOVERNANCE │────▶│  EXECUTION  │
│  REQUESTS   │     │   GATE      │     │  TOKEN SVC  │     │  (with     │
│  ACTION     │     │  CHECKS     │     │  ISSUES     │     │   token)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │                    │                    │
                           ▼                    ▼                    ▼
                    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
                    │  POLICY     │     │  TOKEN      │     │  ACTION     │
                    │  ENGINE     │     │  RECORDED   │     │  LEDGERED   │
                    │  EVALUATES  │     │  IN LEDGER  │     │  (append)   │
                    └─────────────┘     └─────────────┘     └─────────────┘
```

### Token Requirements
- **Format:** JWT (RS256) signed by Governance Token Service
- **Claims:** `agent_id`, `task_id`, `action_type`, `exp`, `nonce`, `conditions`
- **Lifetime:** Short (default 5 min, max 1 hour)
- **Single-use:** Nonce prevents replay
- **Revocation:** Immediate via token revocation list

### Token Absence = Draft Mode
- No token → action runs in **simulation/draft mode only**
- Side effects: logged but NOT executed
- Results: marked `DRAFT`, not persisted to ledger
- Use case: dry-run, planning, what-if analysis

---

## Audit Logging

### Mandatory Audit Events
Every agent MUST emit these audit events (append-only, tamper-evident):

| Event | Trigger | Required Fields |
|-------|---------|-----------------|
| `agent.spawned` | Agent process starts | agent_id, agent_type, tenant_id, resource_profile |
| `agent.initialized` | Agent ready | agent_id, capabilities, config_hash |
| `admission.requested` | Before any gated action | agent_id, task_id, action_type, action_spec |
| `admission.decided` | Gate returns decision | agent_id, task_id, decision_id, allowed, reason |
| `action.executed` | Side effect executed | agent_id, task_id, action_type, result_ref, duration_ms |
| `action.failed` | Side effect failed | agent_id, task_id, action_type, error_code, error_context |
| `checkpoint.created` | State checkpointed | agent_id, task_id, checkpoint_id, size_bytes, hash |
| `checkpoint.restored` | State restored | agent_id, task_id, checkpoint_id, verified |
| `agent.terminated` | Agent shuts down | agent_id, reason, uptime_ms, final_metrics, resource_leaks |

### Audit Log Format (JSON Lines)
```json
{
  "event_id": "uuid",
  "event_type": "admission.decided",
  "timestamp": "2026-09-19T04:00:00Z",
  "agent_id": "uuid",
  "task_id": "uuid",
  "tenant_id": "uuid",
  "decision_id": "uuid",
  "allowed": true,
  "reason": "Policy allow: task_execution within quota",
  "governance_token_hash": "sha256:...",
  "policy_version": "v3.2.1",
  "evaluation_ms": 12
}
```

### Tamper Evidence
- Each entry: `hash = SHA256(prev_hash + current_entry)`
- Periodic anchoring to external timestamping service
- Verification: `ledger.verify()` → full chain integrity

---

## Policy Evaluation

### Policy Engine: OPA (Open Policy Agent)
- **Language:** Rego
- **Data Input:** Agent identity, task context, resource state, tenant config
- **Decision:** Allow / Deny / Conditional
- **Caching:** Decisions cached with TTL (default 60s)

### Policy Structure
```rego
package kilo.admission

default allow = false

# Allow task execution within quota
allow {
  input.action_type == "TASK_EXECUTE"
  input.agent.governance_tier == "GOVERNED"
  quota_available(input.tenant_id, input.action_spec.estimated_cost)
}

# Require approval for shell execution
allow {
  input.action_type == "SHELL_EXEC"
  input.governance_token != ""
  token_valid(input.governance_token)
  approval_exists(input.task_id, "shell_exec")
}

# Deny by default with reason
deny[reason] {
  not allow
  reason := sprintf("No policy allows %s for agent %s", [input.action_type, input.agent_id])
}
```

### Policy Versioning
- Policies versioned in Git (OPA bundle)
- Version embedded in every admission decision
- Rollback via Git revert + bundle rebuild
- Canary deployment for policy changes

---

## Governance Tiers

| Tier | Description | Admission Required | Token Required | Approval Required |
|------|-------------|-------------------|----------------|-------------------|
| **GOVERNED** | Standard agent operations | Yes (most actions) | Yes (for side effects) | Per-action (configurable) |
| **RESTRICTED** | Sensitive operations | Yes (all actions) | Yes (always) | Always (human or policy) |
| **PRIVILEGED** | Platform-level operations | Yes (all actions) | Yes (always) | Always (multi-party) |

### Tier Assignment
- Declared at agent registration (immutable)
- Verified by Admission Gate at spawn
- Escalation requires new agent spawn with higher tier

---

## Integration with KUDBEE Control Fabric (Phase 12)

| Control Fabric Component | Agent Hook | Purpose |
|-------------------------|------------|---------|
| **AdmissionGate** | `governance_client.admission.check()` | Pre-execution authorization |
| **ActionLedger** | `governance_client.audit.append()` | Immutable audit trail |
| **GovernanceToken** | `governance_client.token.request()` | Execution authorization |
| **ThinkBox** | `task.experiment_id` + `task.think_box_id` | Portable work unit |
| **Mesh** | `agent.mesh_cell_id` | Compromise containment |

---

## Failure Modes

| Failure | Detection | Response |
|---------|-----------|----------|
| **Admission Gate Unavailable** | Timeout / connection error | Fail closed (deny), queue request, alert |
| **Policy Engine Error** | OPA evaluation error | Fail closed, use cached decision if fresh |
| **Token Service Down** | Token request fails | Fail closed, no new tokens issued |
| **Ledger Write Fails** | Append error | Buffer locally, retry with backoff, alert |
| **Token Revoked Mid-Action** | Token check during execution | Immediate termination, audit event |

---

## Implementation Requirements (PR89+)

- Governance client as shared library (not per-agent duplication)
- All gated actions: explicit `await admission.check()` before execution
- Audit events: fire-and-forget to local buffer, async flush to ledger
- Token management: automatic renewal, secure storage (memory only)
- Policy evaluation: local OPA instance or gRPC to policy service
- Testing: contract tests for every action type + governance tier

---

## References

- `agent-kernel.md` — Governance compliance as kernel responsibility
- `agent-lifecycle.md` — Governance checkpoints at each transition
- `execution-boundaries.md` — Boundary violations → governance events
- `governance/approval-gates.md` — Approval gate specifications
- `governance/compliance-model.md` — Compliance expectations
- `governance/audit-logging.md` — Audit log format & verification
- `integration/scheduler-integration.md` — Scheduler admission integration