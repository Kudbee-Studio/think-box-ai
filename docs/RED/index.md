# RED: Master Index

## RED File System — Think Box AI

| File | Domain | Quick Description |
|------|--------|-------------------|
| [README.md](README.md) | Index | RED format explanation and file index |
| [scheduler.md](scheduler.md) | Scheduler Module | 92 classes across PR #76–84; governed scheduling features |
| [architecture.md](architecture.md) | Core Architecture | Engines, layers, DAG, concurrency, dependency rules |
| [agents.md](agents.md) | Agent Coordination | Session handoffs, workflows, documentation, PR cycles |

## Quick Orientation by Role

**New agent starting work:**
1. Read `agents.md` — rules and session protocol
2. Read `architecture.md` — system structure and import rules
3. Read `scheduler.md` if working on scheduling features

**Working on specific areas:**
- Scheduling / queue management → `scheduler.md`
- Engine / execution / DAG → `architecture.md`
- Process / handoff / PR workflow → `agents.md`

## Project Layer Map

```
Layer 5 — Agent Implementations (specific workflows)
Layer 4 — Runtime (ThinkBoxEngine, GovernedEngine, DAG)
Layer 3 — Governance/Tools (AdmissionGate, ActionLedger, IdentityLedger)
Layer 2 — Memory (Session, Task, Organizational, Verified Knowledge)
Layer 1 — Provider Abstraction (OpenAI-compatible, Anthropic, local)
Layer 0 — Foundation (config, schemas, logging, errors)
```

## Key Commands

| Command | Purpose |
|---------|---------|
| `python3 -m unittest discover tests/` | Full test suite |
| `python3 -m unittest tests.unit.test_scheduler` | Scheduler tests |
| `python3 -m unittest tests.unit.test_cnc` | CNC module tests |
| `python3 -m unittest tests.unit.test_concurrent_goals` | Concurrent goals tests |

## Key Documents (outside RED)

| Document | Location | Purpose |
|----------|----------|---------|
| AGENTS.md | Repo root | Rules for all agents |
| STATUS.md | Repo root | Current project status |
| PREP.md | `docs/PREP.md` | Handoff & readiness brief |
| CONTINUITY.md | `docs/CONTINUITY.md` | Canonical persistent state |
| architecture-v1.md | `docs/architecture-v1.md` | System architecture definition |
| ADRs | `docs/decisions/` | Architecture decision records |