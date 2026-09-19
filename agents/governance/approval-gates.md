# KILO Cloud Agent Approval Gates — Specifications

**Purpose:** Defines the approval gate system for KILO Cloud Agents. Approval gates enforce human-in-the-loop and policy-based authorization for sensitive operations.

---

## Approval Gate Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     AGENT                                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Governance Client → Admission Gate → Approval Service  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    APPROVAL SERVICE                              │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────────┐  │
│  │  Policy      │ │  Notification│ │  Approval State        │  │
│  │  Engine      │ │  Dispatcher  │ │  Machine               │  │
│  │  (OPA)       │ │  (Slack/     │ │  (Pending/Approved/    │  │
│  │              │ │   Email/     │ │   Denied/Expired/      │  │
│  │              │ │   PagerDuty) │ │   Auto-approved)       │  │
│  └──────────────┘ └──────────────┘ └────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Approval Gate Types

### 1. Human Approval Gate
**Trigger:** Actions requiring human judgment
**Flow:** Request → Notify → Wait → Decision → Execute/Deny

| Parameter | Value |
|-----------|-------|
| **Timeout** | Configurable (default: 1 hour, max: 24 hours) |
| **Escalation** | Auto-escalate after 50% timeout |
| **Quorum** | Single approver (default) or multi-party |
| **Delegation** | Approver can delegate to alternate |

**Notification Channels:**
- Slack (primary) — Interactive buttons (Approve/Deny/View)
- Email (fallback) — Link to approval dashboard
- PagerDuty (urgent) — High-priority alert

### 2. Policy Auto-Approval Gate
**Trigger:** Actions matching pre-approved policy patterns
**Flow:** Request → Policy Evaluation → Auto-Approve/Deny → Execute/Deny

| Parameter | Value |
|-----------|-------|
| **Evaluation** | OPA policy (same as admission) |
| **Cache TTL** | 60 seconds |
| **Audit** | Full audit trail (same as human) |
| **Override** | Human can override auto-decision |

### 3. Time-Based Gate
**Trigger:** Actions allowed only in maintenance windows
**Flow:** Request → Window Check → Queue/Execute → Execute/Deny

| Parameter | Value |
|-----------|-------|
| **Windows** | Cron-defined (e.g., "0 2 * * 0" for Sunday 2AM) |
| **Queue** | Requests queued until window opens |
| **Max Queue Time** | 7 days (then expire) |

### 4. Resource Quota Gate
**Trigger:** Actions consuming billable/limited resources
**Flow:** Request → Quota Check → Reserve → Execute/Release/Deny

| Parameter | Value |
|-----------|-------|
| **Reservation** | Atomic reserve at approval |
| **Release** | On completion, cancellation, or timeout |
| **Timeout** | 4 hours (configurable) |
| **Overdraft** | Not allowed (hard limit) |

---

## Gate Definitions by Action

| Action Type | Gate Type | Approvers | Timeout | Escalation | Conditions |
|-------------|-----------|-----------|---------|------------|------------|
| **SHELL_EXEC** | Human | Platform admin | 30 min | 15 min | Command allowlist, working dir restrict |
| **CLOUD_API (provision)** | Human + Quota | Platform admin + FinOps | 1 hour | 30 min | Budget check, tagging required |
| **CLOUD_API (terminate)** | Human (2-party) | Platform admin + Owner | 2 hours | 1 hour | Confirmation, backup verified |
| **GPU_ALLOCATE** | Policy + Quota | Auto (policy) | 4 hours | N/A | GPU type, duration, project code |
| **AGENT_SPAWN (PRIVILEGED)** | Human (2-party) | Platform admin + Security | 2 hours | 1 hour | Category, resource profile, tenant |
| **POLICY_CHANGE** | Human (3-party) | Platform admin + Security + Compliance | 24 hours | 12 hours | Canary plan, rollback tested |
| **TENANT_OPERATION** | Human (cross-tenant) | Both tenant admins | 4 hours | 2 hours | Data sharing agreement |
| **MEMORY_WRITE_ORG (verified)** | Policy | Auto (policy) | N/A | N/A | Verification score > threshold |
| **LEDGER_WRITE (audit)** | Policy | Auto (policy) | N/A | N/A | Schema valid, tamper-evident |

---

## Approval State Machine

```
                    ┌─────────────┐
                    │  PENDING    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       ┌────────────┐ ┌──────────┐ ┌──────────┐
       │  APPROVED  │ │  DENIED  │ │  EXPIRED │
       └─────┬──────┘ └────┬─────┘ └────┬─────┘
             │             │             │
             ▼             ▼             ▼
       ┌────────────┐ ┌──────────┐ ┌──────────┐
       │  EXECUTING │ │  CLOSED  │ │  CLOSED  │
       └─────┬──────┘ └──────────┘ └──────────┘
             │
             ▼
       ┌────────────┐
       │  COMPLETED │
       └────────────┘
```

### State Transitions

| From | To | Trigger | Action |
|------|-----|---------|--------|
| PENDING | APPROVED | Human clicks Approve / Policy allows | Issue governance token, notify agent |
| PENDING | DENIED | Human clicks Deny / Policy denies | Record reason, notify agent |
| PENDING | EXPIRED | Timeout reached | Auto-deny, record timeout, notify agent |
| APPROVED | EXECUTING | Agent begins execution | Record start time, token validated |
| EXECUTING | COMPLETED | Action finishes | Record result, release reservation |
| EXECUTING | DENIED | Token revoked mid-execution | Terminate action, record revocation |

---

## Approval Request Format

```json
{
  "request_id": "uuid",
  "agent_id": "uuid",
  "task_id": "uuid|null",
  "tenant_id": "uuid",
  "action_type": "SHELL_EXEC",
  "action_spec": {
    "command": "docker build -t myapp .",
    "working_dir": "/workspace",
    "timeout_seconds": 300,
    "allowlist_match": "docker build"
  },
  "gate_type": "HUMAN",
  "requested_by": "agent",
  "requested_at": "2026-09-19T04:00:00Z",
  "expires_at": "2026-09-19T05:00:00Z",
  "priority": "normal",
  "context": {
    "task_name": "build_container",
    "estimated_cost_usd": 0.05,
    "risk_score": 0.3
  }
}
```

## Approval Decision Format

```json
{
  "decision_id": "uuid",
  "request_id": "uuid",
  "decided_by": "user:admin@company.com",
  "decided_at": "2026-09-19T04:05:00Z",
  "decision": "APPROVED",
  "reason": "Standard build, within policy",
  "conditions": [
    "working_dir must be /workspace",
    "no network access during build"
  ],
  "governance_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_expires_at": "2026-09-19T04:10:00Z"
}
```

---

## Notification Templates

### Slack (Interactive)
```json
{
  "blocks": [
    {"type": "header", "text": {"type": "plain_text", "text": "⏳ Approval Required"}},
    {"type": "section", "fields": [
      {"type": "mrkdwn", "text": "*Agent:* `task-agent-abc123`"},
      {"type": "mrkdwn", "text": "*Action:* `SHELL_EXEC`"},
      {"type": "mrkdwn", "text": "*Command:* `docker build -t myapp .`"},
      {"type": "mrkdwn", "text": "*Expires:* <!date^1695123600^{date_short} {time}|in 1 hour>"},
      {"type": "mrkdwn", "text": "*Cost Est:* $0.05"},
      {"type": "mrkdwn", "text": "*Risk:* Low (0.3)"}
    ]},
    {"type": "actions", "elements": [
      {"type": "button", "text": {"type": "plain_text", "text": "✅ Approve"}, "style": "primary", "action_id": "approve", "value": "req_uuid"},
      {"type": "button", "text": {"type": "plain_text", "text": "❌ Deny"}, "style": "danger", "action_id": "deny", "value": "req_uuid"},
      {"type": "button", "text": {"type": "plain_text", "text": "🔍 View Details"}, "action_id": "view", "url": "https://kilo.company.com/approvals/req_uuid"}
    ]}
  ]
}
```

### Email (Fallback)
```
Subject: [KILO] Approval Required: SHELL_EXEC for task-agent-abc123

An agent requires your approval to execute a shell command.

Agent: task-agent-abc123 (TASK_AGENT)
Action: SHELL_EXEC
Command: docker build -t myapp .
Working Directory: /workspace
Expires: 2026-09-19 05:00 UTC (1 hour)
Estimated Cost: $0.05
Risk Score: 0.3 (Low)

[✅ Approve] [❌ Deny] [🔍 View Details]

If you do not respond within 1 hour, this request will expire and be auto-denied.
```

---

## Approval Service API

```python
class ApprovalService(Protocol):
    # Submit approval request
    async def request_approval(self, request: ApprovalRequest) -> ApprovalRequestId: ...
    
    # Get approval status
    async def get_status(self, request_id: str) -> ApprovalStatus: ...
    
    # Submit decision (human or policy)
    async def decide(self, request_id: str, decision: ApprovalDecision) -> None: ...
    
    # Cancel pending request
    async def cancel(self, request_id: str, reason: str) -> None: ...
    
    # List pending for user/role
    async def list_pending(self, user_id: str, role: str) -> list[ApprovalRequest]: ...
    
    # Webhook for notification callbacks
    async def handle_callback(self, payload: CallbackPayload) -> None: ...
```

---

## Implementation Requirements (PR89+)

- Approval service: highly available, multi-region
- State machine: persisted in PostgreSQL (ACID)
- Notifications: async, at-least-once delivery, idempotent
- Token issuance: integrated with Governance Token Service
- Audit: every state transition logged to ActionLedger
- Testing: contract tests for each gate type + state transition
- Metrics: approval latency, approval rate, expiration rate, escalation rate

---

## References

- `governance/governance-hooks.md` — Admission gate integration
- `governance/compliance-model.md` — Compliance requirements for approvals
- `governance/audit-logging.md` — Audit trail for approvals
- `governance/governance-hooks.md` — Governance token flow
- `core/agent-lifecycle.md` — Lifecycle transitions requiring approval
- `core/execution-boundaries.md` — Actions requiring approval