# ADR 025: Trait Lab Autonomous Worker Executor — Governance Layer

**Date:** 2026-09-25
**Status:** Proposed (not Accepted)
**Supersedes:** None

## Context

The Trait Lab autonomous chain (PRs #203–#229) has built a complete CI/CD pipeline for autonomous applications:

- **A01–A25** — Autonomous workflow (plan/sign/verify + receipt gates)
- **R01–R25** — Autonomous receipt chain (triple index: prep/session/autonomous)
- **F01–F25** — Workflow chain bind (run_chained + bind persist)
- **O01–O25** — Flow workflow major (orchestration + flow receipt)
- **P01–P25** — Flow workflow compose (merge/intersect/subtract/xor flow-receipt indexes)
- **U01–U25** — Stack harness (dry/run/full smoke entry for app integration)
- **V01–V25** — Stack suite (dry+run+full CI suite + suite artifact)
- **G01–G25** — App gate (stack_suite gate for application CI)
- **J01–J25** — App regression (baseline vs candidate gate compare)
- **K01–K25** — Integration major (gate + regression CI manifest) — **merged at `2a2fa3e`**

**What exists:** A complete quality-gate pipeline (`IntegrationMajor`) that validates applications.

**What is missing:** An autonomous worker executor that:
- Pulls work from a queue
- Runs the K01–K25 Integration Major as its quality gate
- Executes via existing substrate
- Produces verified execution receipts
- Reports outcomes to scheduler/orchestrator

**Existing execution primitives (already built, tested, hermetic):**
- `ExecutionJobQueue` — durable SQLite queue (PR #198)
- `CloudExecutionWorker` — process-local worker loop with state machine, heartbeat, runtime persistence (PR #199)
- `CloudExecutionEngine` — Intent → Admission → Provider → Receipt (PR #197)
- `DurableCloudExecutionEngine` — with recovery
- `ConcurrentGoalsRunner` — concurrent goal execution with budgets
- `GovernedEngine.execute_verified_goal` / `execute_verified_task`
- `VerifiedRetrySession`, `VerifiedRetryConfig`, `BudgetExhausted`
- `ExperimentManager`, `ExperimentDB` — experiment tracking

## Options Considered

1. **Build new worker from scratch** — duplicate `CloudExecutionWorker` logic
2. **Compose around `CloudExecutionWorker`** — wrap the existing worker with Trait Lab governance
3. **Orchestrate via `CloudExecutionEngine` directly** — bypass `CloudExecutionWorker`, use engine directly with Integration Major gate
4. **New Layer 5 Agent Runtime** — implement as Layer 5 "Agent Implementations" per architecture-v1.md

## Decision (Proposed — Pending Founder Approval)

**Architecture:** Compose a **governance/orchestration layer** ("Trait Lab Worker Executor") on top of existing execution primitives, using K01–K25 Integration Major as the quality gate.

```
Queue (ExecutionJobQueue)
    ↓
CloudExecutionWorker (existing substrate, PR #199)
    ↓
Trait Lab Worker Executor (NEW — PR230 governance layer)
    ↓
K01–K25 Integration Major (quality gate)
    ↓
Execution via existing provider (HermeticCloudExecutionProvider or live)
    ↓
Verified Execution Receipt
    ↓
Scheduler/Orchestrator Outcome (ExperimentManager / ConcurrentGoalsRunner / dashboard)
```

**Key Principles:**
- **NO DUPLICATE WORKER SUBSTRATE** — `CloudExecutionWorker` already exists and is tested
- **Composition over inheritance** — governance layer wraps/orchestrates, doesn't reimplement
- **Hermetic boundary** — `live_verified: false`; four-state ceiling = CODE COMPLETE / TEST VERIFIED
- **No live APIs** — all tests use `HermeticCloudExecutionProvider` and in-memory SQLite
- **Memory contract** — uses existing `write_verified` / `record_task_step` from `memory_layers`
- **Receipt chain** — execution receipts link to Integration Major report SHA-256

## Decisions Remaining (Explicitly Not Resolved)

| # | Decision | Status | Notes |
|---|----------|--------|-------|
| 1 | Composition pattern | **PENDING** | Wrap `CloudExecutionWorker` vs orchestrate via `CloudExecutionEngine` directly |
| 2 | Architecture layer | **PENDING** | Layer 4 (orchestration) vs Layer 5 (Agent Runtime per architecture-v1.md §3) |
| 3 | Feature namespace | **PENDING** | L01–L25 proposed alphabetically after K; founder to select final namespace |
| 4 | Module name | **PENDING** | `autonomous_worker_executor.py` vs `autonomous_worker.py` vs other |

These decisions are **intentionally left open** for explicit founder resolution before Accepting this ADR and beginning implementation.

## Proposed Module Structure (Subject to Decisions Above)

| Module | Purpose |
|--------|---------|
| `thinkbox/autonomous_worker_executor.py` | Governance layer: queue consumer → Integration Major gate → execution → receipt → outcome |
| `scripts/verify_trait_lab_autonomous_worker_executor.py` | Hermetic verification (25 ops, `hermetic_operator_ok`, `live_verified: false`) |
| `tests/unit/test_memory_trait_lab_autonomous_worker_executor_25.py` | 4+ test methods covering all 25 features |

## Proposed 25 Operations (L01–L25, Pending Namespace Decision)

| Op | Name | Purpose |
|----|------|---------|
| L01 | `refuse_live` | Worker payloads may not claim LIVE VERIFIED |
| L02 | `require_provenance` | Fail-closed without `agent_id` + `task_id` |
| L03 | `require_no_live_ack` | Fail-closed when swarm live ack present |
| L04 | `plan_worker` | Unsigned worker plan (queue, gate_mode, max_claims, budget) |
| L05 | `validate_worker_plan` | Fail-closed validation |
| L06 | `sign_worker_plan` | Sign plan with SHA-256 |
| L07 | `verify_worker_plan` | Rematch plan hash |
| L08 | `list_gate_modes` | Available Integration Major modes from plan |
| L09 | `gate_mode_ok` | Check named gate mode result |
| L10 | `run_worker_cycle` | Single claim → gate → execute → receipt loop |
| L11 | `run_worker_continuous` | Run cycles until budget/claims exhausted or shutdown |
| L12 | `export_worker_report` | Signed worker execution report |
| L13 | `verify_worker_report` | Rematch report hash |
| L14 | `assert_worker_ok` | Fail-closed unless all cycles ok |
| L15 | `worker_status` | ready/blocked/draining/stopped |
| L16 | `worker_digest` | Worker report SHA-256 |
| L17 | `worker_etag` | Short worker identity |
| L18 | `public_worker_row` | Stable summary for dashboards |
| L19 | `manifest_worker_config` | SDK-friendly config manifest |
| L20 | `bundle_worker_for_ci` | JSON-friendly CI bundle |
| L21 | `compare_worker_reports` | Compare two worker reports |
| L22 | `worker_row` | One-line worker metadata |
| L23 | `persist_worker_artifact` | Persist worker report on workspace store |
| L24 | `worker_contract_summary` | Hermetic catalog for verify scripts |
| L25 | `open_worker_executor` | Run worker with queue + Integration Major gate |

## Consequences

**Positive:**
- Reuses all existing execution infrastructure (queue, worker, engine, provider, retry, budget, experiment tracking)
- Turns the complete Trait Lab chain (#203–#229) into a governed autonomous execution layer
- Zero new dependencies; hermetic by construction
- Integrates with dashboard pipeline (`/api/pipeline`) and ExperimentManager

**Negative/Risk:**
- Requires explicit founder decisions on composition pattern, layer, namespace before implementation
- If Layer 5, may need agent framework integration (protocol, registry, telemetry per agents/ docs)
- If wrapping `CloudExecutionWorker`, must handle its state machine correctly
- Risk of scope creep if not bounded to "governance layer only"

## Testing

- Hermetic only: `HermeticCloudExecutionProvider`, in-memory SQLite
- 25-operation contract verification via `*_contract_summary()`
- `ops_count == 25`, `hermetic_operator_ok == true`, `live_verified == false`
- No live API calls in test suite

## References

- PR #229: `thinkbox/autonomous_integration_major.py` (K01–K25, merged `2a2fa3e`)
- PR #199: `thinkbox/cloud_execution/worker_orchestrator.py` (`CloudExecutionWorker`)
- PR #198: `thinkbox/cloud_execution/queue.py` (`ExecutionJobQueue`)
- PR #197: `thinkbox/cloud_execution/engine.py` (`CloudExecutionEngine`)
- Architecture: `docs/architecture-v1.md` §3 (Layer 4 vs Layer 5)
- Roadmap: `docs/roadmaps/kilo-post-170-pr-roadmap.md` (Slot 14+)
- Chronicle: `docs/CONTINUITY.md` (2026-09-25 PR230 entry)