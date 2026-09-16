# Agent Work Templates

**Purpose:** a template branch is the *operating system* for a class of agent work.
It answers **"how should an agent execute this type of work?"** so the next agent
does not rediscover the procedure from a conversation.

A **feature branch** answers **"what did this particular agent build?"**

```
agent-template/<domain>        ← the reusable protocol (how to work)
        │  instructs
        ▼
agent/<domain>/<agent>-<date>  ← one execution (what was built)
        │
        ▼
      PR → review → verification → merge → main
```

## Why branches, not prompts

| A prompt | A template branch |
|---|---|
| lives in one conversation | lives in git, versioned and reviewable |
| lost when the session ends | cloneable by any future agent |
| cannot be tested | carries runnable verification |
| drifts per agent | has one contract and one checker |

## Registry

| Template branch | Domain | Status |
|---|---|---|
| `agent-template/dashboard-evolution` | dashboard / observability surface | **active** |
| `agent-template/backend` | API, middleware, persistence | planned |
| `agent-template/provider` | model providers, transport boundaries | planned |
| `agent-template/security` | auth, permission, audit hardening | planned |
| `agent-template/research` | evidence workflows, tiering, provenance | planned |
| `agent-template/experiment` | A/B runs, instrumentation, measurement | planned |
| `agent-template/integration` | external systems (MCP, Redis, Box, cloud) | planned |

Templates are **not merged into `main`**. They persist as long-lived operational
branches so any future agent (KILO, Claude, Codex, a human) can start from one.

## Using a template

```bash
# 1. read the contract
git fetch origin agent-template/dashboard-evolution
git show origin/agent-template/dashboard-evolution:docs/agent-templates/dashboard-evolution/AGENT_CONTRACT.md

# 2. create a compliant work branch (naming is enforced by the checker)
git checkout -b agent/dashboard-evolution/kilo-20260916 origin/main

# 3. verify you are compliant BEFORE working
python3 scripts/agent_work.py check --template dashboard-evolution --branch "$(git branch --show-current)"

# 4. do the work, then verify BEFORE pushing
python3 scripts/agent_work.py verify --template dashboard-evolution

# 5. push, open a NEW PR, review the diff, merge only when verify is green
python3 scripts/agent_work.py report --template dashboard-evolution
```

## The contract, in one screen

Every template defines the same nine fields:

1. **branch naming** — `agent/<domain>/<agent>-<YYYYMMDD>`
2. **baseline** — tests that must pass *before* work starts
3. **required tests** — what the change must add or update
4. **verification commands** — the exact commands that constitute proof
5. **evidence** — every claimed capability needs a test, artifact, telemetry
   source, or an explicitly labelled synthetic fixture
6. **failure semantics** — no fake green; signals are not failures;
   environmental blockers ≠ software failures; unproven stays unproven
7. **security** — secrets, permissions, audit, input handling
8. **review protocol** — self-review of the diff before the PR; independent
   review of the PR before merge
9. **merge conditions** — what must be true to merge, and what to report after

Machine-readable form: `docs/agent-templates/_contract.template.yaml`.
Executable form: `scripts/agent_work.py`.

## Discoverability

A future agent should find this by:
- `docs/agent-templates/README.md` (this file, on `main`)
- `.kilo/command/` templates that invoke `scripts/agent_work.py`
- the remote branch list: `git branch -r | grep agent-template/`
