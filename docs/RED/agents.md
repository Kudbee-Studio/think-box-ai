# RED: Agent Coordination

## RESOURCES

| Name | Type | Location | Description |
|------|------|----------|-------------|
| `AGENTS.md` | Document | `AGENTS.md:1` | Rules for every agent; operational layer of architecture; 812 lines |
| `STATUS.md` | Document | `STATUS.md:1` | Current project status, test counts, module structure, experiment details |
| `PREP.md` | Document | `docs/PREP.md:1` | Handoff & readiness brief; verified state, known defects, next steps |
| `CONTINUITY.md` | Document | `docs/CONTINUITY.md:1` | Canonical agent state artifact; persistent memory across sessions |
| `docs/architecture-v1.md` | Document | `docs/architecture-v1.md:1` | Structural boundaries; 5-layer model; core concepts |
| `docs/CONTINUITY.md` | Document | `docs/CONTINUITY.md:1` | Agent exit checklist, current state, recent changes |
| `tests/unit/test_scheduler.py` | Test File | `tests/unit/test_scheduler.py:1` | 99 test classes, 689 scheduler tests |
| `tests/unit/test_scheduler_integration.py` | Test File | `tests/unit/test_scheduler_integration.py:1` | 42 integration and chaos-gate tests |
| `tests/unit/test_cnc.py` | Test File | `tests/unit/test_cnc.py:1` | 43 CNC module tests |
| `tests/unit/test_concurrent_goals.py` | Test File | `tests/unit/test_concurrent_goals.py:1` | 40 tests for concurrent execution, budgets, accounting |
| `tests/unit/test_session_tracker.py` | Test File | `tests/unit/test_session_tracker.py:1` | 27 tests for Phase 9 session tracker |
| `tests/unit/test_experiment.py` | Test File | `tests/unit/test_experiment.py:1` | 46 experiment persistence and learning loop tests |
| `thinkbox/scheduler.py` | Module | `thinkbox/scheduler.py:1` | Governed scheduler (103 public classes, 6905 lines + SchedulerHarness) |
| `thinkbox/engine.py` | Module | `thinkbox/engine.py:1` | ThinkBoxEngine — unified execution pipeline |
| `thinkbox/governed.py` | Module | `thinkbox/governed.py:1` | GovernedEngine — admission-gated execution |
| `thinkbox/concurrent_goals.py` | Module | `thinkbox/concurrent_goals.py:1` | Multi-goal concurrent budget execution |
| `thinkbox/pop_arena.py` | Module | `thinkbox/pop_arena.py:1` | Experiment arena population + VerifiedRetry primitives |
| `thinkbox/experiment.py` | Module | `thinkbox/experiment.py:1` | Experiment records, persistence, learning loop |
| `docs/decisions/` | Directory | `docs/decisions/` | Architecture Decision Records (ADRs) |
| `data/thinkboxmd/artifacts/` | Directory | `data/thinkboxmd/artifacts/` | Proof artifacts (SHA256-verified JSON) |
| `data/thinkboxmd/db/` | Directory | `data/thinkboxmd/db/` | SQLite databases (experiments.db, ledger.db) |
| Git branches | VCS | `feat/scheduler-*` | PR branches for scheduler features |

## EVENTS

| Date | Event | Details |
|------|-------|---------|
| Ongoing | Agent session handoff protocol | Every agent reads AGENTS.md → STATUS.md → PREP.md → CONTINUITY.md before acting |
| 2026-09-15 | PREP.md created | Handoff brief established: verified state, known defects, next steps |
| 2026-09-17 | CONTINUITY.md established | Canonical agent state artifact; persists across sessions |
| 2026-09-17 | PR #82 merged | 10 scheduler features via `feat/scheduler-10-pr82` |
| 2026-09-18 | PR #83 merged | 10 scheduler features via `feat/scheduler-10-pr83`; 82 new tests |
| 2026-09-18 | PR #84 merged | 10 scheduler features via `feat/scheduler-10-pr84` |
| 2026-09-18 | Agent exit checklist updated | CONTINUITY.md includes mandatory verification before declaring completion |
| Ongoing | Test gate enforcement | `python3 -m unittest discover tests/` must pass before commit |
| Ongoing | PR cycle | Feature branch → PR → founder review → merge (no direct pushes to main) |
| Ongoing | Dashboard state updates | Every task/job/infrastructure change emits via `get_dashboard_state().emit()` |
| Ongoing | Evidence recording | Every claim backed by artifacts in `data/thinkboxmd/artifacts/` |

## DECISIONS

| ID | Decision | Rationale | Status |
|----|----------|-----------|--------|
| AGT-001 | Every agent must read AGENTS.md before acting | Rules are non-negotiable; violations require ADR | Accepted |
| AGT-002 | Session orientation order: AGENTS.md → STATUS.md → PREP.md → CONTINUITY.md | AGENTS.md (rules) → STATUS (state) → PREP (handoff) → CONTINUITY (persistent) | Accepted |
| AGT-003 | CONTINUITY.md is the canonical persistent state | Conversations are temporary; CONTINUITY persists across sessions | Accepted |
| AGT-004 | Agent exit requires checklist verification | Prevents incomplete work from being reported done | Accepted |
| AGT-005 | PRs required for meaningful changes | One PR per feature branch; founder review before merge; no direct main pushes | Accepted |
| AGT-006 | Test gate = `python3 -m unittest discover tests/` | All tests must pass before commit; canonical test command | Accepted |
| AGT-007 | Every claim backed by artifact evidence | No invented numbers; unknowns marked as `—` | Accepted |
| AGT-008 | Dashboard state updated in real-time via emit() | WebSocket + SSE provide live client updates; every event recorded | Accepted |
| AGT-009 | Branch naming: `feat/phase-N-description`, `fix/NNN-description` | Consistent naming enables automated branch analysis | Accepted |
| AGT-010 | Conventional commit messages: type(scope): description | Enables automated changelog; clear intent in git history | Accepted |
| AGT-011 | No secrets in code, config, or documentation | Secrets injected via env vars; audit logs append-only | Accepted |
| AGT-012 | ADR required for significant decisions | Every ADR drafted before implementation, reviewed, then marked Accepted | Accepted |
| AGT-013 | Architecture compliance checked via import review | Cross-layer imports require decision record; layer discipline is non-negotiable | Accepted |
| AGT-014 | Phase boundaries enforced | Phase 1 features not in Phase 9; no premature multi-agent or benchmarks | Accepted |
| AGT-015 | No speculative claims in Organizational Memory | Memory First principle: only attested, verified facts in organizational layer | Accepted |
| AGT-016 | PR status tracked in CONTINUITY.md | Open/merged/closed state documented; no stale PRs | Accepted |