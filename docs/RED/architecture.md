# RED: Core Architecture

## RESOURCES

| Name | Type | Location | Description |
|------|------|----------|-------------|
| `ThinkBoxEngine` | Class | `thinkbox/engine.py:48` | Unified engine wiring decomposer, pruner, autoscaler, model client, swarm, git engine |
| `EngineConfig` | Dataclass | `thinkbox/engine.py:39` | Engine configuration (model, scaler, git, repo path, speculative, retries) |
| `TaskState` | Enum | `thinkbox/engine.py:21` | PENDING, RUNNING, SPECULATING, SUCCESS, FAILED |
| `TaskEvent` | Dataclass | `thinkbox/engine.py:30` | Task state transition event with timestamp, message, metadata |
| `set_verified_task_runner()` | Method | `thinkbox/engine.py:64` | Dependency injection point for GovernedEngine verified execution |
| `GovernedEngine` | Class | `thinkbox/governed.py:39` | Admission-gated facade around ThinkBoxEngine |
| `GovernedEngineConfig` | Dataclass | `thinkbox/governed.py:32` | Config: base engine, token service, identity ledger, ledger path |
| `GovernedEngine.execute_goal()` | Method | `thinkbox/governed.py:67` | Authorizes via AdmissionGate, then delegates to base engine |
| `GovernedEngine.execute_verified_goal()` | Method | `thinkbox/governed.py:81` | Builds graph, assigns stable IDs, delegates to verified runner |
| `VerifiedRetrySession` | Class | `thinkbox/pop_arena.py:711` | Bounded retry with per-call traces, session budget, BudgetExhausted |
| `VerifiedRetryConfig` | Dataclass | `thinkbox/pop_arena.py:672` | Retry configuration: max attempts, budget, timeout |
| `VerifiedCallResult` | Dataclass | `thinkbox/pop_arena.py:686` | Single verified call result with taxonomy, trace, latency |
| `BudgetExhausted` | Exception | `thinkbox/pop_arena.py:707` | Raised when retry budget is depleted (honest terminal failure) |
| `ConcurrentGoalsRunner` | Class | `thinkbox/concurrent_goals.py:523` | Runs multiple goals concurrently with independent/shared budgets |
| `ConcurrentGoalsConfig` | Dataclass | `thinkbox/concurrent_goals.py:75` | max_calls_global, max_retries_global, independent_goals, contention_policy |
| `BudgetContentionPolicy` | Enum | `thinkbox/concurrent_goals.py:58` | FAIR_SHARE, PRIORITY, FIFO |
| `ConcurrentGoalSpec` | Dataclass | `thinkbox/concurrent_goals.py:66` | Goal + subtasks + budget config + priority |
| `ConcurrentGoalsResult` | Dataclass | `thinkbox/concurrent_goals.py:84` | Per-goal results, cross-goal summary, layer telemetry, proof paths |
| `aggregate_layer_telemetry()` | Function | `thinkbox/concurrent_goals.py:101` | Pure function merging per-layer telemetry across goals |
| `TaskDecomposer` | Class | `thinkbox/decomposer.py` | Decomposes goals into TaskGraph of TaskNodes |
| `TaskGraph` | Class | `thinkbox/decomposer.py` | DAG of task nodes with `get_execution_order()` for layers |
| `AdmissionGate` | Class | `thinkbox/admission.py` | Fail-closed admission checking governance tokens |
| `ActionLedger` | Class | `thinkbox/ledger.py` | Append-only tamper-evitable action log |
| `GovernanceTokenService` | Class | `thinkbox/governance_token.py` | Token issuance, verification, revocation |
| `IdentityLedger` | Class | `thinkbox/identity.py` | Agent identity and capability registration |
| Layer 0 — Foundation | Layer | `thinkbox/` base modules | Config, schemas, logging, error handling |
| Layer 1 — Provider Abstraction | Layer | `core/providers/` | OpenAI-compatible, Anthropic, local models |
| Layer 2 — Memory Subsystem | Layer | `thinkbox/memory.py` | Session, task, organizational, verified knowledge |
| Layer 3 — Governance/Tools | Layer | `thinkbox/admission.py`, `thinkbox/ledger.py` | Permission checks, audit log, approval gates |
| Layer 4 — Runtime | Layer | `thinkbox/engine.py`, `thinkbox/governed.py` | Execution loop, Think Box, Planner, Actor, Observer |
| Phase 9 Modules | Module Group | `thinkbox/{coalition,consensus,economy,intelligence,benchmark,session}.py` | 55 innovations across 13 categories |

## EVENTS

| Date | Event | Details |
|------|-------|---------|
| 2026-08-20 | Architecture v1 drafted | `docs/architecture-v1.md` — 5-layer model defined, layer discipline rule established |
| 2026-09-15 | KUDBEE Control Fabric completed | Phase 12: admission gate, ledger, identity, workspace, handoff, occupancy, capacity modules |
| 2026-09-17 | Verified execution chain spans full DAG | `ThinkBoxEngine.set_verified_task_runner()` + `execute_goal(goal, graph=None)` route nodes through GovernedEngine |
| 2026-09-17 | Multi-goal concurrent budgets shipped | `thinkbox/concurrent_goals.py` with FAIR_SHARE/PRIORITY/FIFO policies |
| 2026-09-17 | Architecture audit: concurrency model decided | Each concurrent goal gets OWN GovernedEngine to avoid shared `_verified_task_runner` race |
| 2026-09-17 | Budget contention policies completed | Early budget check for limit ≤ 0 goals; defense-in-depth in `_counted_complete` |
| 2026-09-17 | DAG-level verified execution completed | 5 live calls via Mercury-2; 3 FIRST_TRY_SUCCESS + 1 RECOVERED_SUCCESS |
| 2026-09-18 | PR #84 merged | AdaptiveConcurrency, Preemption, TaskCoalescing, WorkflowTemplate, BackpressurePropagation, SchedulerClock, AdmissionFilter, FairnessIndex, DynamicBudget, TaskAffinity |
| 2026-09-18 | PR #85 merged + integrated | 10 hardening features via SchedulerHarness |
| 2026-09-18 | Test milestone | 689 scheduler + 42 integration tests; 1435 full suite (6 skipped, 3 pre-existing) |

## DECISIONS

| ID | Decision | Rationale | Status |
|----|----------|-----------|--------|
| ARCH-001 | Strict 5-layer model with import discipline | Prevents architectural drift; cross-layer imports are errors requiring ADR | Accepted |
| ARCH-002 | Layer N may only import from layers 0 through N-1 | Unidirectional dependency graph; no cycles possible | Accepted |
| ARCH-003 | ThinkBoxEngine never imports governance/retry code | Engine is pure execution; GovernedEngine wraps it via dependency injection | Accepted |
| ARCH-004 | Dependency injection via `set_verified_task_runner()` | Engine stays ignorant of retry/admission; runner is supplied externally | Accepted |
| ARCH-005 | Each concurrent goal gets its own GovernedEngine | Shared `_verified_task_runner` attribute would race; per-goal engines isolate state | Accepted |
| ARCH-006 | Only shared object is global VerifiedRetrySession with synchronous counters | `_spend_call`/`retries_fired`/`conversions` are synchronous → asyncio serializes → mathematically correct shared accounting | Accepted |
| ARCH-007 | GovernedEngine is admission facade, not execution engine | Delegates to base ThinkBoxEngine; adds authorization + ledger only | Accepted |
| ARCH-008 | VerifiedRetrySession is sync-pure | No I/O; testable without network; deterministic retries | Accepted |
| ARCH-009 | BudgetExhausted is honest terminal failure | Never auto-retry beyond budget; failures are surfaced, not hidden | Accepted |
| ARCH-010 | Retry only retryable taxonomies | Arithmetic errors, inconsistency are NOT auto-retried (deterministic failure) | Accepted |
| ARCH-011 | pop_arena is canonical population arena | ExperimentManager owns jobs, ChallengeArena owns probes, pop_arena owns population+budget+classification | Accepted |
| ARCH-012 | DAG execution routes via metadata["verification"] | Binary: nodes with verification spec use runner; others use legacy swarm path | Accepted |
| ARCH-013 | Provenance-marked recovery from artifacts | After data loss, restored rows carry `agent_id=recovery-YYYYMMDD`, `source=recovered-from-artifacts` | Accepted |
| ARCH-014 | Leader election: ledger hash chain NOT reconstructable from artifacts | Only attested fields restored; empty ledger documented as limitation | Accepted |
| ARCH-015 | Provider independence via ModelProvider protocol | No provider SDK at runtime; swap = config change | Accepted |
| ARCH-016 | Memory First: 4 layers (Session, Task, Organizational, Verified Knowledge) | Distinct scope/lifetime/write policy; no transient UI state, no speculative claims in Organizational | Accepted |