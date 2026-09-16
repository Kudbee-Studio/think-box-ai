# AGENTS.md — THINK BOX AI

**Purpose:** This file defines the rules that every agent (human or AI) working
on this repository must follow. It is the operational layer of the architecture
defined in `docs/architecture-v1.md`.

---

## 1. Architecture Principles

These are non-negotiable. Violating them requires a decision record.

### 1.1 Layer Discipline

The system has five layers (Foundation, Provider, Memory, Governance/Tools,
Runtime). A layer may only import from layers beneath it. Cross-layer imports
are architectural errors.

**Check:** Before committing, verify imports with:
`python3 -c "import ast,sys; [print(f) for f in sys.argv[1:] if True]"` or manual
review.

### 1.2 Provider Independence

No model provider is hardcoded. The runtime must work identically with:
- OpenAI-compatible APIs (OpenAI, Groq, Together, vLLM, Ollama)
- Anthropic Messages API
- Local models (Phase 2+)

Swapping a provider is a configuration change, not a code change.

**Rule:** Never import a provider-specific SDK at the runtime layer. The
runtime only knows the `ModelProvider` protocol.

### 1.3 Memory First

Memory is not a chat history. It has four layers: Session, Task,
Organizational, Verified Knowledge. Each has a distinct scope, lifetime, and
write policy.

**Rule:** Never store transient UI state in memory. Never store speculative
claims in Organizational Memory.

### 1.4 Governance by Default

Tools do not execute without permission checks. Audit logs are append-only.
Approval gates are opt-out, not opt-in.

**Rule:** A tool without an explicit `permission` level is `RESTRICTED` and
requires approval.

### 1.5 Evidence Over Assumptions

Claims about model performance, tool reliability, or system behavior must be
backed by measurements stored in Organizational Memory.

**Rule:** Never commit a claim like "Model X is better" without a benchmark
result in `benchmarks/`.

---

## 2. Coding Rules

### 2.1 Language

- **Core:** Python 3.10+
- **CLI wrapper (future):** TypeScript/Node (deferred)
- **No other languages** without a decision record.

### 2.2 Dependencies

- Phase 0: Python standard library only.
- Every external dependency must have a documented trigger (see
  `docs/project-foundation.md` §4).
- No "maybe we'll need it" imports.

### 2.3 Style

- Follow PEP 8.
- Use type hints on all public functions and methods.
- Use `dataclasses` for data structures (Phase 1). Add `pydantic` when
  schemas stabilize.
- Docstrings on all public classes and functions.
- No comments that explain *what* the code does. Comments explain *why*.

### 2.4 Async

- The runtime is async (`asyncio`). All I/O-bound operations must be async.
- Blocking operations must be explicitly marked and isolated.

### 2.5 Error Handling

- Never swallow exceptions silently.
- All errors carry: `agent_id`, `task_id`, `think_box_id`, `timestamp`,
  `error_type`, `context`.
- The runtime raises structured errors. It does not log and continue.

### 2.6 Logging

- Use `logging` from stdlib.
- Log levels: `DEBUG` (internal state), `INFO` (significant events),
  `WARNING` (recoverable issues), `ERROR` (failures).
- Never log secrets, tokens, or PII.

---

## 3. Testing Requirements

### 3.1 Test Coverage

- Phase 1 target: 80% coverage for `core/` and `core/tools/`.
- Tests run in CI. No PR merges without passing tests.

### 3.2 Test Structure

```
tests/
  unit/           # Pure logic, no I/O, no network
  integration/    # Memory store, provider HTTP client, tool execution
  e2e/            # Full runtime loop with a mock provider
```

### 3.3 Test Requirements

- Every public function has at least one test.
- Every error path has a test.
- Tools have tests for: valid input, invalid input, permission denied,
  approval required.
- Memory has tests for: write, read, delete, conflict, retention.

### 3.4 Test Commands

```bash
python3 -m pytest tests/unit/          # Fast, no I/O
python3 -m pytest tests/integration/   # Requires SQLite
python3 -m pytest tests/                # All tests
```

### 3.5 Mocking

- Mock providers in unit tests. Do not make real HTTP calls.
- Use `unittest.mock` from stdlib. No external mocking libraries in Phase 1.

---

## 4. Documentation Requirements

### 4.1 What Must Be Documented

| Artifact | Location | Required |
|----------|----------|----------|
| Architecture | `docs/architecture-v1.md` | Yes |
| Project foundation | `docs/project-foundation.md` | Yes |
| Decision records | `docs/decisions/NNN-*.md` | Yes (for every ADR) |
| Module docstrings | In-code | Yes |
| Public API docstrings | In-code | Yes |
| Setup guide | `docs/guides/setup.md` | Phase 1 |
| Tool authoring guide | `docs/guides/tools.md` | Phase 1 |

### 4.2 Decision Records

Every significant decision gets a record:

```
docs/decisions/
  001-*.md   # First decision
  002-*.md   # Second decision
  ...
```

Format:

```markdown
# ADR NNN: Title

**Date:** YYYY-MM-DD
**Status:** Accepted | Rejected | Superseded

## Context
What problem are we solving?

## Options Considered
1. Option A
2. Option B

## Decision
We chose Option X because...

## Consequences
What changes as a result?
```

---

## 5. Decision Recording Process

1. **Draft:** Author writes the ADR before implementing the decision.
2. **Review:** At least one other contributor reviews.
3. **Accept:** ADR is marked `Accepted` and committed with the implementation.
4. **Supersede:** If a later decision invalidates an ADR, mark it
   `Superseded` and reference the new ADR.

ADRs are never deleted. They are historical records.

---

## 6. Branching and Commits

### 6.1 Branch Naming

```
feat/phase-N-description   # New feature or phase
fix/NNN-description        # Bug fix, references ADR if applicable
docs/description           # Documentation only
refactor/description       # Code restructuring, no behavior change
```

### 6.2 Commit Messages

Format: `type(scope): description`

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

Examples:
```
feat(providers): add OpenAI-compatible provider
fix(memory): handle SQLite lock on concurrent write
docs(architecture): update Think Box lifecycle
refactor(runtime): extract Planner class from Agent
test(tools): add permission denied tests for shell_exec
```

No commit without a message. No "fix stuff" or "wip" messages in main branch
commits.

### 6.3 What to Commit

- Source code
- Tests
- Documentation
- Configuration files (`pyproject.toml`, etc.)

**Never commit:**
- Secrets, tokens, API keys
- `.env` files
- Model weights or large binaries (use Git LFS or external storage)
- `__pycache__`, `.pytest_cache`, `.mypy_cache`
- IDE config files (`.vscode/`, `.idea/`)

---

## 7. Git Hygiene

- Commit early, commit often.
- One logical change per commit.
- No merge commits in feature branches (rebase or squash).
- PRs target `main`. Do not push directly to `main`.
- Keep the branch up to date with `main` before opening a PR.

### 7.1 PRs Required (Standing Rule)

For every meaningful change: commit on a feature branch → open/update a GitHub PR → paste the PR URL in your summary.

Do not stop at "committed to branch." Do not merge. Founder reviews on Graphite/GitHub.

Batch only when founder says so; default = one PR per checkpoint.

If a branch already exists without a PR (e.g. kilo/amused-voxel-h11 gcode work), open the PR now and return the URL.

---

## 8. Code Review

- Every PR requires at least one review.
- Reviewers check: architecture compliance, test coverage, documentation,
  security.
- Reviewers do not approve PRs that violate layer discipline or introduce
  undocumented dependencies.

---

## 9. Security Rules

- No secrets in code, config files, or documentation.
- Secrets are injected via environment variables at runtime.
- Tool execution must be permission-checked before it runs.
- Audit logs are append-only and tamper-evident.
- External HTTP calls must have timeouts and retry limits.
- Shell execution must be explicitly approved by the user.

---

## 10. Phase Boundaries

| Phase | Goal | Phase 1 Boundary |
|-------|------|-----------------|
| Phase 0 | Foundation | This document |
| Phase 1 | Prove architecture with single agent, single provider, 5 tools | No multi-agent, no benchmarks, no UI |
| Phase 2 | Add pattern extraction, local models, benchmarks | — |
| Phase 3 | Multi-agent, UI, organizational memory scaling | — |
| Phase 9 | Zero-to-one innovations (55 features) | No Phase 2+ features |
| Phase 12 | KUDBEE control fabric | Governance admission, durable workspaces, occupancy mesh |

### Phase 12 — KUDBEE Control Fabric Rules

- Every side effect must pass `AdmissionGate` with a valid governance token.
- No token means draft/simulate only, never execute.
- Every admission or denial is appended to `ActionLedger`; the chain must
  verify (`ledger.verify()`).
- Think Boxes are the portable unit of work; handoffs must preserve integrity.
- A compromised mesh cell is expelled and never inherits peer capabilities.
- Do not bypass `GovernedEngine` to call the base engine's side effects
  directly in agent code.

### Phase 9 Modules

Phase 9 adds the following modules to `thinkbox/`:
- `coalition.py` — CRDT shared memory, task bidding market, pub/sub bus, capability registry, governance voting
- `consensus.py` — Multi-model voting, Bayesian confidence scoring, disagreement resolution, model ranking, audit trail
- `economy.py` — Token economy, contribution mining, staking mechanism, slash conditions, treasury governance
- `intelligence.py` — Knowledge graph, self-healing, reputation, federated learning, post-quantum security
- `benchmark.py` — High-throughput concurrency scaling sweeps (16–512 workers), system metrics, markdown report generation
- `session.py` — Session tracking with Upstash Vector sync

### Phase 9 Testing

Phase 9 innovations are tested in `tests/unit/test_session_tracker.py` (27 tests)
covering all Phase 9 modules. Each innovation must have at least one unit test
covering valid input, invalid input, and edge cases.

Do not implement Phase 2+ features in Phase 1. Do not implement Phase 1
features before the foundation is solid.

---

## 11. When in Doubt

1. Read `docs/architecture-v1.md`.
2. Read `docs/project-foundation.md`.
3. Check `docs/decisions/` for prior decisions on the topic.
4. If still uncertain, write an ADR before writing code.
5. Default to simplicity. The simplest solution that satisfies the
   architecture is correct.

---

## 12. Enforcement

These rules are enforced by:
- Code review
- CI checks (tests, lint, import ordering)
- Architectural review for cross-layer imports

Violations are bugs. Fix them before merging.

---

## 13. Workflows

Step-by-step procedures for common agent tasks. Every agent should know these by heart.

---

### 13.1 Session Start

Every new agent session must:

1. **Read AGENTS.md** (this file)
2. **Read STATUS.md** — current project state
3. **Read docs/PREP.md** — handoff & readiness brief
4. **Check git state** — branch, working tree, last commits
5. **Run tests** — `python3 -m unittest discover tests/`
6. **Report** — current branch, test count, blockers

---

### 13.2 RPO Assessment

Full project status check (see skill: `rpo-assess`):

1. Check git state
2. Run test suite
3. Check infrastructure status (Inception, Upstash, UpCloud, OpenAI)
4. Read known defects from STATUS.md and PREP.md
5. Produce prioritized output:
   - **P0** — Immediate blockers (infrastructure, credentials)
   - **P1** — Test gaps, missing capabilities
   - **P2** — Optimization, polish
   - **P3** — Enhancement

---

### 13.3 Code Change → PR

Full workflow (see skill: `pr-workflow`):

1. Sync to main: `git checkout main && git pull`
2. Branch: `git checkout -b feat/descriptive-name`
3. Make changes following AGENTS.md coding rules
4. Run tests — all must pass
5. Commit with conventional message: `type(scope): description`
6. Push and create ONE PR targeting main
7. **STOP** — wait for founder review. Do not create another PR.
8. After approval: merge with `--no-ff`, push main, stop.

---

### 13.4 Upstash Vector Debug

Debug Upstash Vector write failures (see skill: `upstash-vector-fix`):

1. Read `data/findings/thinkboxmd_upstash_vector_defect.md`
2. Check index type: must be DENSE with matching dimension
3. Verify embedder: `OpenAICompatEmbedder` (production) or `DeterministicEmbedder` (test-only)
4. Verify upsert payload includes `vector` field (1536 floats)
5. Fix fail-closed: raise `EmbeddingError`, never silent `False`
6. Test: `python3 -m unittest tests.unit.test_session_tracker.TestUpstashVectorSyncEmbedder -v`

---

### 13.5 UpCloud Setup

Set up UpCloud infrastructure (see skill: `upcloud-setup`):

1. Create API token in UpCloud panel → `THINKBOX_UPCLOUD_API_TOKEN`
2. Upload SSH public key → place private key at `UPCLOUD_SSH_KEY_PATH`
3. Handle Cloudflare block → direct IP, SSH tunnel, or Floating IP
4. (Recommended) Purchase Floating IP → stable dashboard endpoint
5. Verify: `detect_substrate()` returns `upcloud-gpu`

---

### 13.6 THINK Burst Execution

Run burst evaluations (see skill: `burst-execute`):

1. Verify governance token available (required to start)
2. Offline: `python3 examples/think_burst_demo.py`
3. Live: `python3 -m thinkbox.burst --live --pairs N --minutes M --max-calls C --budget X`
4. Capture reasoning fields — never drop `delta.reasoning` / `reasoning`
5. Hard stops enforced — do not bypass limits
6. Never expose :8000/:8001 publicly

---

### 13.7 Swarm Instrumentation

Run swarm experiments (see skill: `swarm-instrument`):

1. Verify instrumentation: `python3 experiments/verify_instrumentation.py --live` (expect 11/11)
2. Run swarm: `python3 experiments/big_swarm.py --primary 256 --validators 64 --concurrency 32 --arena`
3. Dashboard: `python3 experiments/swarm_dashboard.py --port 8787`
4. Check metrics: TSSI, learning curve, Mercury 2 throughput
5. Self-ImprovementLoop: exists but NOT auto-wired into runs (TODO)

---

### 13.8 Test-Driven Development

Every change follows this pattern:

1. **Write failing test first** — valid input, invalid input, edge case
2. **Implement code** — make test pass
3. **Refactor** — clean up, preserve all test passes
4. **Verify** — full suite: `python3 -m unittest discover tests/`

Minimum test counts by module:

| Module | Minimum Tests |
|--------|---------------|
| `thinkbox/session.py` | 9 (embedder + upsert) |
| `thinkbox/substrate.py` | 9 |
| `core/providers/` | Per-provider |
| All public functions | At least 1 each |
| All error paths | At least 1 each |

---

### 13.9 Failure Recovery

When something fails:

1. **Do not hide it** — document in STATUS.md or findings
2. **Classify the failure** — infrastructure, code, environment, external dependency
3. **Determine scope** — does this block other work?
4. **Fix or work around** — choose honestly
5. **Record** — update docs, findings, STATUS.md
6. **Test the fix** — prove it works

Known failures to track:
- Upstash Vector writes (422 dense index, no embedder) — FIXED in PR #67
- UpCloud access (401 token, no SSH key, CF 1003) — PANEL WORK
- `tests/e2e/` empty — TODO
- Solana CLI not installed — environment issue

---

## Think-v2 (KUDBEE gpt-oss-20b) — Operational Note

Served model id: `openai/gpt-oss-20b` (NOT bare `gpt-oss-20b`).
Endpoint: `http://127.0.0.1:8001` (loopback only — never expose :8000/:8001 publicly).
Auth: `Authorization: Bearer EMPTY`.
SSM: `AWS_PAGER="" aws ssm start-session --target i-0685561c90845986d --region us-east-1`.
Use HTTP/1.0 if curl hangs: `curl -sS --http1.0 -m 20 ...`.
Capture `delta.reasoning` / `reasoning` fields when present — do not drop them.

## CNC Manufacturing Intelligence Platform

The `thinkbox/cnc/` module extends Think Box AI into a manufacturing intelligence system.

### Module Structure

- `thinkbox/cnc/job.py` — CNCJob, Material, Tool, MachineProfile, Operation, ValidationResult, InspectionResult, ApprovalRecord, ExecutionRecord
- `thinkbox/cnc/memory.py` — ManufacturingMemory, KnowledgeEntry (persistent knowledge across jobs)
- `thinkbox/cnc/proof.py` — ProofPackage, ProofStore (evidence packages for every decision)
- `thinkbox/cnc/adapter.py` — CADInterface, MachineControllerInterface, InspectionSystemInterface, SimulatorInterface, ShopDatabaseInterface, CNCAdapterRegistry
- `thinkbox/cnc/safety.py` — ApprovalGate, SafetyGate, SafetyGateStore (human approval before execution)
- `thinkbox/cnc/tenant.py` — Tenant, TenantPermission, TenantBoundary, TenantStore (multi-tenant isolation)
- `thinkbox/cnc/dashboard.py` — ROIStats, ROIDashboard (measurable business value)
- `thinkbox/cnc/demo.py` — DemoMode, DemoResult (deterministic end-to-end demonstration)
- `thinkbox/cnc/engine.py` — CNCManufacturingEngine (wires all subsystems)
- `thinkbox/cnc/__init__.py` — All exports

### Key Design Principles

1. **No autonomous execution** — Human approval required before production
2. **Evidence labeling** — All data labeled as "simulated", "inferred", "verified", or "physically_measured"
3. **Tenant isolation** — Customer knowledge remains isolated
4. **Replayable** — Every job is persistent and replayable via ReplayDriver
5. **Self-improving** — SelfImprovementLoop compares outcomes and improves future plans
6. **No new dependencies** — Reuses existing Think Box infrastructure

### Testing

- `tests/unit/test_cnc.py` — 43 tests covering all CNC modules
- Run: `python3 -m unittest tests.unit.test_cnc -v`
- Full suite: `python3 -m unittest discover tests/` (477 tests, 1 skip)

### ADR

- `docs/decisions/001-cnc-manufacturing.md` — ADR for CNC manufacturing platform

### ROI Report

- `docs/cnc-roi-report.md` — Enterprise ROI and evidence report

## THINK Burst Protocol — Operational Note

Short bounded bursts on `openai/gpt-oss-20b` maximize THINK-token quality per
GPU-dollar. Never leave the A10G idle.

- Runner: `python3 -m thinkbox.burst --live --pairs N --minutes M --max-calls C --budget X`
  (refuses to start without a governance token; hard-stops on calls/spend/time).
- Offline demo/tests: `python3 examples/think_burst_demo.py`, `python3 -m unittest tests.unit.test_burst`.
- Founder starts and **stops** (never terminates) think-v2; Cloud Bot / CloudShell
  holds SSM access. KILO does not hold the key and never binds :8000/:8001 publicly.
- Full checklist: `docs/think-burst-protocol.md

## Dashboard Control Plane — Permanent Agent Completion Contract

The dashboard (`backend/main.py`, `thinkbox/dashboard_state.py`) is the
living control plane for Think Box AI. Every agent task, phase, capability,
infrastructure change, Think Job, CNC job, provider change, test milestone,
or execution event MUST update canonical dashboard state in real-time.

### Mandatory Rules

1. **Every event updates dashboard state.** Use `get_dashboard_state().emit()`
   or `broadcast_event()` from `thinkbox.dashboard_state`.
2. **WebSocket `/dashboard/ws`** broadcasts all state changes to connected
   clients in real-time.
3. **SSE `/dashboard/stream`** provides a persistent event stream.
4. **Every Think Job** creates a `ThinkJobEntry` in dashboard state.
5. **Every CNC job** creates a `CNCJobEntry` in dashboard state.
6. **Every infrastructure change** creates an `InfrastructureEntry`.
7. **Every provider change** creates a `ProviderEntry`.
8. **Every test run** creates a `TestMilestoneEntry`.
9. **UpCloud investigation** must call `investigate_upcloud()` and update
   dashboard state with the trace results.
10. **Evidence labels** on all data: "simulated", "inferred", "verified", or
    "physically_measured". Never claim physical validation without proof.

### Dashboard State Model

- `DashboardCategory`: THINK_BOXES, THINK_JOBS, CNC, INFRASTRUCTURE,
  AGENT_ACTIVITY, PROVIDERS, TESTS, EXECUTION
- `DashboardEvent`: TASK_STARTED, TASK_COMPLETED, JOB_CREATED, etc.
- `DashboardEventEntry`: event_id, category, event_type, timestamp, data,
  source, evidence_label
- `ThinkBoxEntry`, `ThinkJobEntry`, `CNCJobEntry`, `InfrastructureEntry`,
  `ProviderEntry`, `TestMilestoneEntry`

### Testing Requirements

- Dashboard state updates must be tested
- CNC lifecycle must appear in dashboard
- Replay status must update dashboard
- Self-improvement status must update dashboard
- Provider state must update dashboard
- UpCloud unverified state must be reflected
`.
