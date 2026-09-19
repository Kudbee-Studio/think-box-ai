# KILO Cloud Agent Framework — Documentation Index

**Purpose:** This directory contains the complete documentation suite for the KILO Cloud Agent Framework, introduced in PR88 as the foundational layer of the Agent Era inside the KILO platform.

---

## Documentation Structure

```
agents/
├── README.md                           # This file — documentation index
├── core/                               # Core agent architecture & runtime
│   ├── agent-kernel.md                 # Agent kernel definition & responsibilities
│   ├── agent-lifecycle.md              # Agent lifecycle: spawn, execute, terminate
│   ├── agent-categories.md             # Agent taxonomy & classification
│   ├── execution-boundaries.md         # Execution boundaries & sandboxing
│   └── cloud-interaction-model.md      # Cloud environment interaction patterns
├── governance/                         # Governance & compliance
│   ├── governance-hooks.md             # Governance integration points
│   ├── compliance-model.md             # Compliance expectations & audit
│   ├── approval-gates.md               # Approval gate definitions
│   └── audit-logging.md                # Audit trail requirements
├── telemetry/                          # Observability & telemetry
│   ├── telemetry-expectations.md       # Required telemetry signals
│   ├── metrics-contract.md             # Metrics schema & emission
│   ├── tracing-model.md                # Distributed tracing integration
│   └── health-reporting.md             # Health & readiness reporting
├── integration/                        # Subsystem integration
│   ├── scheduler-integration.md        # Governed scheduler integration
│   ├── cnc-telemetry-integration.md    # CNC Manufacturing Intelligence integration
│   ├── cloud-orchestration.md          # Cloud orchestration layer hooks
│   └── protocol-responsibilities.md    # Protocol duties & message formats
└── chronological/                      # Historical evolution track
    ├── 000-pre-agent-architecture.md   # Pre-agent architecture baseline
    ├── 001-pr88-initialization.md      # PR88: framework initialization
    ├── 002-pr89-autonomous-core.md     # PR89: autonomous agent core (planned)
    ├── 003-pr90-multi-agent-clustering.md  # PR90: multi-agent clustering (planned)
    ├── 004-pr91-distributed-governance.md  # PR91: distributed governance (planned)
    └── 005-pr92-agent-marketplace.md   # PR92: agent marketplace (planned)
```

---

## Quick Navigation

| Domain | Purpose | Entry Point |
|--------|---------|-------------|
| **Core Architecture** | Agent kernel, lifecycle, categories, boundaries | `core/agent-kernel.md` |
| **Governance** | Compliance, approval gates, audit logging | `governance/governance-hooks.md` |
| **Telemetry** | Metrics, tracing, health reporting | `telemetry/telemetry-expectations.md` |
| **Integration** | Scheduler, CNC, cloud orchestration | `integration/scheduler-integration.md` |
| **History** | Evolution from pre-agent to future phases | `chronological/000-pre-agent-architecture.md` |

---

## PR88 Scope

**Delivers:** Complete documentation suite for KILO Cloud Agent Framework conceptual foundation

**Does NOT deliver:**
- No runtime code or implementations
- No protocol implementations
- No agent runtime modules
- No autonomous execution capabilities

**Enables:** Structured development in subsequent PRs (PR89+)

---

## Integration Points (Existing Systems)

| Subsystem | Integration Document | Status |
|-----------|---------------------|--------|
| Governed Scheduler (PR80–85) | `integration/scheduler-integration.md` | Documented |
| CNC Manufacturing Intelligence (PR86–87) | `integration/cnc-telemetry-integration.md` | Documented |
| Cloud Orchestration Layer | `integration/cloud-orchestration.md` | Documented |
| KUDBEE Control Fabric (Phase 12) | `governance/governance-hooks.md` | Documented |

---

## Version & Status

| Field | Value |
|-------|-------|
| **Framework Version** | 0.1.0 (PR88 initialization) |
| **Documentation Status** | Complete for PR88 scope |
| **Implementation Status** | Not started (PR89+) |
| **Last Updated** | 2026-09-19 |
| **PR Reference** | #88 |

---

## Contributing

All agent framework documentation follows the same standards as the main repository:
- ADR process for architectural decisions (`docs/decisions/`)
- FourState classification for implementation tracking
- Evidence-over-assumptions principle
- No secrets in documentation