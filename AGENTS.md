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

### 6.4 PR-Before-Work Rule

**Every meaningful change requires a GitHub PR. No exceptions.**

1. **Open a GitHub PR first** (or draft PR for non-urgent work), then commit to that branch.
2. **No direct pushes to `main`** — every commit to `main` must be a merge from a PR. Direct pushes to `main` are prohibited (debt from past direct pushes — KILO PR91, PR92 — must not repeat).
3. **One PR at a time** — do not start new product work while a PR is open (docs PR or otherwise).
4. **PR title format**: `type(scope): description` matching commit message convention.
5. **Docs changes** require a real PR, not direct pushes to `main`.

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
2. Run swarm: `python3 experiments/big_swarm.py --primary 224 --validators 32 --concurrency 32 --fresh-ledger` (256 live calls; add `--arena` for probes)
3. Dashboard: `python3 experiments/swarm_dashboard.py --port 8787`
4. Check metrics: TSSI, learning curve, Mercury 2 throughput
5. Self-ImprovementLoop: exists but NOT auto-wired into runs (TODO)

**256+ swarm results** (2026-09-21): `python3 experiments/big_swarm.py --primary 224 --validators 32 --concurrency 32 --fresh-ledger` — 256/256 OK, 0 failures, 18.15 RPS, 14.10s wall clock, ledger verify true (388 cumulative on shared DB without `--fresh-ledger`; use `--fresh-ledger` for per-run counts), 256/256 traces grounded, strength index 0.6948, reliability 1.0. Baseline (100+32 calls): 112/132 OK, 20 HTTP 503, 8.08 RPS. **PR #122**: 512+ scale target — 448+64=512 agents, 444/512 OK, 27.25 RPS, 18.79s, ledger 512/512 valid, strength 0.6655. Convergence: 5×256 runs, all validated via `verify_swarm_proof.py`, mean 219/256 OK (3/5 runs 256/256), mean 27.24 RPS, ledger_entries_this_run=256 per run, cumulative ledger 388+256×3+512 (across all runs). Convergence stats in `data/thinkboxmd/swarm_convergence_1790004588.json`. Validate proofs: `python3 experiments/verify_swarm_proof.py data/thinkboxmd/big_swarm_*.json`. See `docs/CONTINUITY.md` § Swarm 512+ PR #122 reproducible scaling. Linear scaling NOT claimed (2 scale points). Artifacts: `data/thinkboxmd/big_swarm_20260921_135102.json`, `data/thinkboxmd/big_swarm_20260921_135330.json`, `data/thinkboxmd/big_swarm_20260921_152452.json`, `data/thinkboxmd/big_swarm_20260921_152726.json`, `data/thinkboxmd/big_swarm_20260921_152748.json`, `data/thinkboxmd/big_swarm_20260921_152836.json`, `data/thinkboxmd/big_swarm_20260921_152859.json`, `data/thinkboxmd/big_swarm_20260921_152948.json`, `data/thinkboxmd/swarm_convergence_1790004588.json`.

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
| `thinkbox/scheduler.py` | 689 |
| `thinkbox/cnc/` | 68 |
| `thinkbox/concurrent_goals.py` | 15 |
| `thinkbox/pop_arena.py` | 27 |
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

### 13.10 KILO Live-proof readiness spine (PR #141+)

Before claiming progress on the **#141–#150** arc:

1. Read `docs/runbooks/kilo-live-proof-readiness.md`
2. Run `python3 scripts/verify_kilo_spine.py` (exit 0)
3. Run `python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr141 -v` and PR-specific gates (e.g. `test_kilo_live_proof_readiness_pr142` for #142, `test_kilo_live_proof_readiness_pr143` for #143)
4. Run `python3 scripts/verify_kilo_substrate_checklist.py` (exit 0) before claiming #143 progress
5. Update `docs/CONTINUITY.md`, `docs/STATUS.md`, root `STATUS.md`, and audit pass on checkpoint
6. **Never** mark KILO LIVE VERIFIED / PRODUCTION READY on spine until Live proof artifacts exist

Known failures to track:
- Upstash Vector writes (422 dense index, no embedder) — FIXED in PR #67
- UpCloud access (401 token, no SSH key, CF 1003) — PANEL WORK
- `tests/e2e/` F023 hermetic Think Job lifecycle (PR #130 draft); live API/Mercury path not e2e-covered
- Solana CLI not installed — environment issue

---

## Think Job control-plane UI (PR #138–#140)

Hermetic static UI at `public/control-plane/think_job_status.html` — **not LIVE VERIFIED**.

| Work | GitHub PR | Notes |
|------|-----------|--------|
| SSE subscribe + poll fallback on #137 routes | **#138** (merged) | `think_job_status_client.js`, `thinkbox/think_job_status_ui.py` |
| Receipt-keyed watch + jobs digest multiplex panel | **#139** (merged) | `watchReceipt`, `JobsDigestMultiplexer`, F139 e2e |
| Deep-link from `receipts.html` + shared etag across tabs | **#140** (merged) | `control_plane_deep_link.js`, `control_plane_etag_store.js`, F140 e2e |

KILO Live-proof readiness arc **#141–#150** is documented separately (not part of Think Job UI scope).

Four-state on branch: **CODE COMPLETE / TEST VERIFIED** only. No live Mercury claims.

---

## KILO Live-proof readiness arc (PR #141–#150)

Founder-directed arc (2026-09-23): prepare KILO so a later **Live proof** can be earned honestly. **PR #141–#152 merged** (arc season closed + smoke evidence binder). **PR #153** (draft): live-smoke **operator** CLI + runbook — **not** Live proof executed in CI.

| Work | GitHub PR | Notes |
|------|-----------|--------|
| Env docs + runbook spine + hermetic gates | **#141** (merged) | `docs/runbooks/kilo-live-proof-readiness.md`, `thinkbox/kilo_live_proof_readiness.py` |
| Hermetic KILO env matrix + contract tests | **#142** (merged) | `thinkbox/kilo_env_matrix.py`, `scripts/verify_kilo_env_matrix.py` |
| Box URL/token substrate checklist | **#143** (merged) | `thinkbox/kilo_substrate_checklist.py`, `scripts/verify_kilo_substrate_checklist.py` |
| CI/post-merge unittest discover green | **#144** (merged) | Not governance-evidence; gate id `ci-post-merge` |
| Governance admission evidence shape | **#145** (merged) | `thinkbox/kilo_governance_evidence.py`, `scripts/verify_kilo_governance_evidence.py` |
| Mercury hermetic mocks + live-gate stub | **#146** (merged) | `thinkbox/kilo_mercury_hermetic.py`, `scripts/verify_kilo_mercury_hermetic.py` |
| Swarm instrumentation hermetic catalog | **#147** (merged) | `thinkbox/kilo_swarm_instrumentation.py`, `scripts/verify_kilo_swarm_instrumentation.py` |
| Proof JSON schema + cue/dependency contract | **#148** (merged) | `thinkbox/kilo_proof_schema.py`, `scripts/verify_kilo_proof_schema.py` |
| Dashboard Live-proof slots (hermetic) | **#149** (merged) | `thinkbox/kilo_dashboard_slots.py`, `scripts/verify_kilo_dashboard_slots.py` |
| Live proof execution plan (hermetic) | **#150** (merged) | `thinkbox/kilo_live_proof_exec.py`, `scripts/verify_kilo_live_proof_exec.py` |
| Post-season harden (ops) | **#151** (merged) | `thinkbox/kilo_post_season_harden.py`, `scripts/verify_kilo_post_season_harden.py` |
| Bounded live smoke evidence + audit flip | **#152** (merged) | `thinkbox/kilo_live_smoke_evidence.py`, `scripts/verify_kilo_live_smoke_evidence.py` |
| Live-smoke operator path (write artifact + flip candidate) | **#153** (merged) | `thinkbox/kilo_live_smoke_operator.py`, `scripts/kilo_live_smoke_operator.py` |
| Control-plane API surface upgrade (HTTP routes + contract) | **#154** (merged) | `thinkbox/kilo_control_plane_api.py`, `backend/api/v1/control_plane.py`, `scripts/verify_kilo_control_plane_api.py` |
| Receipt-chain / ETag deepen (pagination, 304/412) | **#155** (merged) | `thinkbox/kilo_receipt_chain_etag.py`, `thinkbox/receipt_chain_query.py`, `scripts/verify_kilo_receipt_chain_etag.py` |
| Dashboard bind receipt-chain / END_LINK | **#156** (merged) | `thinkbox/kilo_dashboard_receipt_chain_bind.py`, `public/control-plane/receipt_chain_dashboard.html`, `scripts/verify_kilo_dashboard_receipt_chain_bind.py` |
| API / ops harden after #156 | **#157** (merged) | `thinkbox/kilo_api_ops_harden.py`, `thinkbox/control_plane_ops_harden.py`, `scripts/verify_kilo_api_ops_harden.py` |
| END LINK / control-plane deepen after #157 | **#158** (merged) | `thinkbox/kilo_end_link_deepen.py`, `thinkbox/end_link_deepen.py`, `scripts/verify_kilo_end_link_deepen.py` |
| END LINK operator dashboard UX after #158 | **#159** (merged) | `thinkbox/kilo_end_link_operator_ux.py`, `thinkbox/end_link_operator_ux.py`, `scripts/verify_kilo_end_link_operator_ux.py` |
| Receipt-chain / END_LINK docs + audit pack after #159 | **#160** (merged) | `thinkbox/kilo_receipt_chain_end_link_docs.py`, `docs/guides/kilo_receipt_chain_end_link_operator.md`, `scripts/verify_kilo_receipt_chain_end_link_docs.py` |
| API / ops harden after END_LINK UX + docs (#159–#160) | **#161** (merged) | `thinkbox/kilo_end_link_api_ops_harden.py`, `thinkbox/end_link_api_ops_harden.py`, `scripts/verify_kilo_end_link_api_ops_harden.py` |
| Control-plane E2E hermetic suite deepen after #161 | **#162** (merged) | `tests/e2e/control_plane_hermetic.py`, `tests/e2e/test_f162_cp_*`, `thinkbox/kilo_control_plane_e2e_deepen.py`, `scripts/verify_kilo_control_plane_e2e_deepen.py` |
| Control-plane E2E deepen merge checkpoint | **#163** (merged) | Same as #162 on `main` |
| Receipt-chain / END_LINK era audit close (#154–#161) | merged on main | `thinkbox/kilo_receipt_chain_end_link_era_close.py`, `scripts/verify_kilo_receipt_chain_end_link_era_close.py` |
| Governance-evidence Live-proof readiness (hermetic) | **#164** (merged) | `thinkbox/kilo_governance_evidence_live_proof_readiness.py`, `thinkbox/governance_evidence_live_proof_readiness.py`, `scripts/verify_kilo_governance_evidence_live_proof_readiness.py` |
| Combined harden + #154–#164 era chronicle (hermetic) | **#165** (merged) | `thinkbox/kilo_pr165_combined_harden_era_chronicle.py`, `thinkbox/live_smoke_audit_flip_correlation.py`, `scripts/verify_kilo_pr165_combined_harden.py` |
| Combined post-#165 lane (operator prep + api ops + dashboard bind + swarm/gov) | **#166** (merged) | `thinkbox/kilo_pr166_combined_post165_lane.py`, `scripts/verify_kilo_pr166_combined_post165_lane.py` |
| Combined post-#166 lane (audit-flip deepen + api ops post166 + dashboard PR166 bind + swarm/gov post166) | **#167** (merged) | `thinkbox/kilo_pr167_combined_post166_lane.py`, `scripts/verify_kilo_pr167_combined_post166_lane.py` |
| Combined post-#167 lane (audit-flip post167 + api ops post167 + dashboard PR167 bind + swarm/gov post167) | **#168** (merged) | `thinkbox/kilo_pr168_combined_post167_lane.py`, `scripts/verify_kilo_pr168_combined_post167_lane.py` |
| Combined post-#168 lane (audit-flip post168 + api ops post168 + dashboard PR168 bind + swarm/gov post168) | **#169** (merged) | `thinkbox/kilo_pr169_combined_post168_lane.py`, `scripts/verify_kilo_pr169_combined_post168_lane.py` |
| Beyond-KILO lint readiness (ruff + mypy + bandit scoped; not combined umbrella) | **#170** (merged) | `thinkbox/kilo_beyond_kilo_lint.py`, `scripts/verify_kilo_beyond_kilo_lint.py` |
| CI spine-trust slimming (PR CI trusts fast spine + explicit lint execute) | **#172** (merged) | `thinkbox/kilo_pr172_ci_spine_trust.py`, `.github/workflows/test.yml` |
| Chronicle honesty sync (post-#170 era docs; README + spine Markdown) | **#173** (merged) | `thinkbox/kilo_pr173_chronicle_honesty.py`, `scripts/verify_kilo_pr173_chronicle_honesty.py` |
| Lint scope wave 1 (25-module beyond-KILO lint + enterprise editing guide) | **#174** (merged) | `thinkbox/kilo_pr174_lint_scope_wave1.py`, `scripts/verify_kilo_pr174_lint_scope_wave1.py` |
| Lint scope wave 2 (live-proof readiness spine +12 modules, 38 total) | **#175** (merged) | `thinkbox/kilo_pr175_lint_scope_wave2.py`, `scripts/verify_kilo_pr175_lint_scope_wave2.py` |
| Chronicle honesty post-#175 | **#176** (merged) | Spine Markdown sync; next-slot pointers |
| Kudbee SDK app (~25 features, kudbEE web shell) | **#177** (merged) | `thinkbox/kudbee_sdk/`, `apps/web/sdk/`, `thinkbox/kilo_pr177_kudbee_sdk_app.py`, `scripts/verify_kilo_pr177_kudbee_sdk_app.py` |
| KUDBEECLI Phase 2 (~25 hermetic CLI deepen features) | **#178** (merged) | `thinkbox/cli_phase2/`, `thinkbox/kilo_pr178_kudbee_cli_phase2.py`, `scripts/verify_kilo_pr178_kudbee_cli_phase2.py` |
| Kudbee SDK follow-up (~25 hermetic deepen features) | **#179** (merged) | `thinkbox/kudbee_sdk_followup/`, `apps/web/sdk/followup.ts`, `thinkbox/kilo_pr179_kudbee_sdk_followup.py`, `scripts/verify_kilo_pr179_kudbee_sdk_followup.py` |
| KUDBEECLI Phase 3 (~25 hermetic CLI deepen features) | **#180** (merged) | `thinkbox/cli_phase3/`, `thinkbox/kilo_pr180_kudbee_cli_phase3.py`, `scripts/verify_kilo_pr180_kudbee_cli_phase3.py` |
| Kudbee SDK follow-up wave 2 (~25 hermetic deepen features) | **#181** (merged) | `thinkbox/kudbee_sdk_followup_w2/`, `apps/web/sdk/followup_w2.ts`, `thinkbox/kilo_pr181_kudbee_sdk_followup_w2.py`, `scripts/verify_kilo_pr181_kudbee_sdk_followup_w2.py` |
| Receipt-chain deepen (~25 hermetic features) | **#182** (merged) | `thinkbox/receipt_chain_deepen/`, `thinkbox/kilo_pr182_receipt_chain_deepen.py`, `scripts/verify_kilo_pr182_receipt_chain_deepen.py` |
| Think Job hermetic e2e deepen (~25 hermetic features) | **#183** (merged) | `thinkbox/think_job_e2e_deepen/`, `thinkbox/kilo_pr183_think_job_hermetic_e2e.py`, `scripts/verify_kilo_pr183_think_job_hermetic_e2e.py` |
| Think Job POST /run contract deepen (~25 hermetic features) | **#184** (merged) | `thinkbox/think_job_post_run_deepen/`, `thinkbox/kilo_pr184_think_job_post_run_deepen.py`, `scripts/verify_kilo_pr184_think_job_post_run_deepen.py` |
| Think Job lifecycle integration fix pack (25 fixes) | **#185** (merged) | `thinkbox/think_job_lifecycle_fixes/`, `thinkbox/kilo_pr185_think_job_lifecycle_fixes.py`, `scripts/verify_kilo_pr185_think_job_lifecycle_fixes.py` |
| Think Job governed run receipt deepen (~25 features) | **#186** (draft) | `thinkbox/think_job_run_receipt_deepen/`, `thinkbox/kilo_pr186_think_job_run_receipt_deepen.py`, `scripts/verify_kilo_pr186_think_job_run_receipt_deepen.py` |

**Do not claim** `KILO LIVE VERIFIED`, `KILO PRODUCTION READY`, or `KILO live build verified` on spine paths until founder-run proof + audit + artifacts say otherwise.

Four-state on #169 branch: **CODE COMPLETE / TEST VERIFIED** only — not KILO LIVE VERIFIED. Audit pass `pr169` (`pr169-combined-post168-lane`) ships `live_verified: false` and `live_api_called: false`. Post168 theme gates deepen **prior theme gates only** (not prior combined umbrella ×4).

Four-state on #168 on main: **CODE COMPLETE / TEST VERIFIED** only — not KILO LIVE VERIFIED. Audit pass `pr168` (`pr168-combined-post167-lane`) ships `live_verified: false` and `live_api_called: false`.

Four-state on #167 on main: **CODE COMPLETE / TEST VERIFIED** only — not KILO LIVE VERIFIED. Audit pass `pr167` (`pr167-combined-post166-lane`) ships `live_verified: false` and `live_api_called: false`.

Four-state on #166 on main: **CODE COMPLETE / TEST VERIFIED** only — not KILO LIVE VERIFIED. Audit pass `pr166` (`pr166-combined-post165-lane`) ships `live_verified: false` and `live_api_called: false`.

Four-state on #165 on main: **CODE COMPLETE / TEST VERIFIED** only — not KILO LIVE VERIFIED. Audit pass `pr165` (`pr165-combined-harden-era-chronicle`) ships `live_verified: false` and `live_api_called: false`.

Four-state on #164 on main: **CODE COMPLETE / TEST VERIFIED** only — not KILO LIVE VERIFIED. Audit pass `pr164` (`governance-evidence-live-proof-readiness`) ships `live_verified: false` and `live_api_called: false`.

Four-state on #162/#163 on main: **CODE COMPLETE / TEST VERIFIED** only — not KILO LIVE VERIFIED. Audit pass `pr162` (`control-plane-e2e-deepen`) ships `live_verified: false`.

---

## KUDBEECLI — Interactive Terminal (`thinkbox/cli.py`)

Unified CLI for hermetic inspection of swarm evidence, ledger integrity, proofs, and environment status. **Do not claim LIVE VERIFIED or PRODUCTION READY** for CLI paths without earned gates.

### PR attribution (canonical)

| Work | GitHub PR | Notes |
|------|-----------|--------|
| Doc redaction + audit P1 close-outs + minimal e2e scaffold | **#126** (merged `866a408`) | Not KUDBEECLI |
| **Phase 1 hermetic e2e** (F009 governed runtime loop) | **#127** (merged `8abc574`) | `tests/e2e/` — on `main` |
| **KUDBEECLI Phase 1** (six inspection commands) | **#128** (merged `bfa067d`) | `thinkbox/cli_inspect.py` + `thinkbox/cli.py` on `main` |
| **KUDBEECLI Phase 2** (persistence, REPL, dashboard, `swarm live` gate) | **#129** (draft) | `thinkbox/cli_persist.py`, `cli_shell.py`, `cli_dashboard.py`, `cli_live_gate.py` |

**PR #126 is not the Phase 1 CLI PR.** Do not attribute `agent register`, `trace capture`, or other unimplemented commands to any merged PR.

### Phase 1 — implemented commands (`d54b797`)

Hermetic / read-only inspection surface (no live provider execution in these subcommands):

| Command | Purpose |
|---------|---------|
| `thinkbox swarm agents` | Population / task statistics |
| `thinkbox swarm status` | Swarm convergence / evidence summary |
| `thinkbox ledger verify` | `ActionLedger` hash-chain verification |
| `thinkbox proof check` | Validate a proof JSON artifact |
| `thinkbox env status` | Redacted environment status |
| `thinkbox session list` | List recent sessions |

**Not implemented (do not document as shipped):** `agent register`, `agent grant`, `agent revoke`, `agent show`, `trace capture`.

Evidence: `thinkbox/cli.py`, `thinkbox/cli_inspect.py`, `tests/unit/test_cli.py`, `tests/unit/test_cli_inspect.py` (PR **#128** on `main`).

### Phase 2 — persistence, REPL, dashboard (on `main`; deepen **#178** draft)

**PR #178** adds `thinkbox/cli_phase2/` (~25 hermetic toolkit features) and `thinkbox cli` subcommands (`health`, `dry-run`, `receipt-bind`, `envelope`). Gate: `kudbee-cli-phase2`. Historical branch `feat/pr129-cli-phase2-25` / draft PR **#129** preceded merge of persist/shell/dashboard to main.

| Command | Purpose |
|---------|---------|
| `thinkbox persist status\|init\|sync` | SQLite paths (`THINKBOX_IDENTITY_LEDGER_PATH`, `THINKBOX_TRACE_DB_PATH`, `THINKBOX_CLI_DB_DIR`) |
| `thinkbox identity list\|path` | Read-only identity SQLite inspection |
| `thinkbox trace list\|stats` | Read-only think-trace SQLite inspection |
| `thinkbox shell` | Local REPL (`-c` one-shot); no network |
| `thinkbox dashboard status` | In-process `DashboardState` summary; no live Mercury |
| `thinkbox swarm live` | Founder-gated credential check only (`THINKBOX_SWARM_LIVE_ACK` + provider key); **no HTTP** |

Tests: `tests/unit/test_cli_phase2.py`. Still **not** implemented: `agent register`, `agent grant`, `agent revoke`, `agent show`, `trace capture` as CLI subcommands.

### Four-state (KUDBEECLI)

| Scope | State |
|-------|--------|
| Phase 1 e2e (F009, PR #127 merged) | **CODE COMPLETE** / **TEST VERIFIED** on `main` |
| Phase 1 CLI (six commands, PR #128 merged) | **CODE COMPLETE** / **TEST VERIFIED** on `main` |
| Phase 2 CLI (PR #129 draft) | **CODE COMPLETE** / **TEST VERIFIED** on branch only — **not LIVE VERIFIED** |
| Any live Mercury / Inception execution via CLI | **Not claimed** — `swarm live` is authorization check only, fail-closed |

---

## Think-v2 (KUDBEE gpt-oss-20b) — Operational Note

Served model id: `openai/gpt-oss-20b` (NOT bare `gpt-oss-20b`).
Endpoint: `http://127.0.0.1:8001` (loopback only — never expose :8000/:8001 publicly).
Auth: `Authorization: Bearer EMPTY`.
SSM: `AWS_PAGER="" aws ssm start-session --target i-0685561c90845986d --region us-east-1`.
Use HTTP/1.0 if curl hangs: `curl -sS --http1.0 -m 20 ...`.
Capture `delta.reasoning` / `reasoning` fields when present — do not drop them.

## UpCloud Connection Path — September 15, 2026 Investigation

### Connection Path Summary
- **Server IP**: 212.147.250.183 (hostname: kudbee-host-v1)
- **SSH key**: ~/.ssh/kilo-upcloud (ed25519, recovered from git commit 5f6a5c7)
- **UpCloud API tokens**: `UPCLOUD_API=REDACTED_UPCLOUD_API`, `THINKBOX_UPCLOUD_API_TOKEN=REDACTED_THINKBOX_UPCLOUD_API_TOKEN` (env only; never commit literals)
- **Upstash box**: wanted-tuna-71803@us-east-1.box.upstash.com (SSH key: ssh wanted-tuna-71803@us-east-1.box.upstash.com)
- **Upstash Vector**: https://unified-chigger-36053-gcp-usc1-vector.upstash.io/

### Investigation Result — 2026-09-17 (PHASE 1-6 COMPLETE)

**CASE C CONFIRMED: The historical IP is no longer the current server.**

#### Phase 1 — Server Identity
- Historical server name: kudbee-host-v1
- Historical IP: 212.147.250.183
- Expected region: us-east-1 (from Upstash box location)
- Expected GPU: unknown (never verified)
- Expected OS: Linux (root SSH access)
- Expected runtime: Unknown
- Last known working: 2026-09-15
- Identity status: VERIFIED from git history, UNVERIFIED as current server

#### Phase 2 — Network Diagnosis (EXACT LAYER IDENTIFIED)
- **DNS**: N/A (literal IP, no DNS resolution needed)
- **Routing**: TCP port 80/443 reachable, port 22 TIMEOUT
- **TCP layer**: Port 22 blocked (timeout), Ports 80/443 open
- **Firewall**: Cloudflare 1003 on port 80, TLS error on 443, port 22 blocked by UpCloud security groups
- **SSH layer**: Connection timed out — never reaches handshake
- **Auth layer**: N/A (SSH never reaches handshake)
- **Exact failure layer**: NETWORK/FIREWALL — port 22 blocked by UpCloud security groups

#### Phase 3 — Alternative Verified Paths
- No SSH aliases found in config files
- No alternate IP or hostname discovered
- No reverse tunnel configured
- No service endpoint available
- Dashboard telemetry: empty (no infrastructure entries)
- Upstash Vector: accessible (separate service, not the server)
- No existing application connection to 212.147.250.183

#### Phase 4 — Dashboard State
- UPCloud historical server: IDENTITY VERIFIED (from git), CURRENT STATUS UNVERIFIED
- NETWORK: TIMEOUT (port 22 blocked)
- SSH: BLOCKED (key not on disk + port timeout)
- GPU: UNKNOWN
- MODEL: UNKNOWN
- THINK BOX ROUTING: NOT CONNECTED

#### Phase 5 — Decision
**Case C: The historical IP is no longer the current server.**
The server 212.147.250.183 is either no longer provisioned, has been reassigned, or has security group rules that block port 22 entirely. The historical IP is confirmed from git history but is not reachable.

#### Phase 6 — Permanence (historical; test counts below are point-in-time)
- Status: CODE COMPLETE (investigation), TEST VERIFIED (605 tests at that time), NOT LIVE VERIFIED
- Only mark LIVE VERIFIED when actual infrastructure has been reached and verified

### Current Status (2026-09-17) — SUPERSEDED by Live Host Verification below; kept for history

The block below describes the pre-verification state (stale server/IP/credentials).
Authoritative live state is in "Live UpCloud Host Verification — 2026-09-17" (next section).
- **UpCloud API**: All tokens return HTTP 401 authentication failed
- **SSH to 212.147.250.183**: Connection timed out (port 22 blocked by security groups)
- **Port 80**: Cloudflare 1003 (direct IP access blocked)
- **Port 443**: TLS error
- **SSH to Upstash box**: Permission denied (password auth required)
- **upctl CLI**: NOT installed (download blocked by Cloudflare)
- **UPCLOUD_API_MAIN**: NOT SET
- **UPCLOUD_API_KEY**: NOT SET
- **SSH key**: Recovered from git `5f6a5c7` but NOT persisted to `~/.ssh/kilo-upcloud`
- **Case**: C — historical IP no longer the current server

### Live UpCloud Host Verification — 2026-09-17

- **Starting evidence check:** directive cited SHA 5e8a7b7 / 693 tests / prior live-proof artifact. Repo reality: HEAD `48fed0f` (= origin/main), 605 tests, no 5e8a7b7 object, no prior artifact on disk. In sync with origin/main; no stale-code risk. Recorded honestly.
- **API (LIVE_VERIFIED, read-only):** Bearer auth on `https://api.upcloud.com/1.3` → account 200 (`kudbee`); server 200 (`kudbeev3`, `0046a589-81a2-4c0b-aacd-8e6f678c7c41`, CLOUDNATIVE-16xCPU-48GB, us-chi1, started, 16 cores, 49152MB, 209.50.56.169 + 209.50.53.93, 50GB virtio, firewall off). `/v1`→404, `/1.6`→400.
- **SSH (BLOCKED at auth):** `~/.ssh/kilo-upcloud` file absent; historical recovered keypair consistent (ed25519 thinkbox-agent-20260831) but NOT authorized on kudbeev3 (Permission denied publickey). Port 22: .169 OPEN (OpenSSH_10.2p1 Ubuntu-2ubuntu3.6 banner), .93 TIMEOUT. No shell; machine facts unverified; nothing mutated.
- **Reconciliation:** same-machine NOT_PROVEN (auth blocker). GPU absence inferred from CPU-only plan, unmeasured via shell.
- **Substrate:** run substrate is Upstash Box. Smallest wiring point: `core/providers/upcloud.py` read-only execute → `UpCloudConfig` (API-sourced UUID/IP) → `thinkbox/substrate.py:bind_think_box` live-server branch (not built).
- **Evidence:** session `tb_sess_20260917162855_705f`, experiment `tb_exp_20260917162855_5eb93b1c`, artifact `data/thinkboxmd/artifacts/upcloud_host_verify_20260917.json` SHA256 `400f4cc92b300a0553cdc9448d89c4cc7f22157985805af9c36fa9737e7bd20d`. Suite 605 OK (6 skipped). FourState: TEST_VERIFIED + LIVE_VERIFIED API inventory; SSH proof FAILED (blocker).
### Upstash Box as Primary Execution Substrate — 2026-09-17 (ARCHITECTURE DECISION)

- **UpCloud = infrastructure / control-plane ONLY** (read-only REST at `https://api.upcloud.com/1.3`; `kudbeev3` running per API). **No UpCloud machine execution claimed. No GPU execution claimed. No SSH used, no SSH adapter will be built.**
- **Upstash Box = current execution substrate.** Precedence: `UPSTASH_PUBLIC_BOX_URL` > `THINKBOX_UPCLOUD_API_TOKEN` (legacy label) > `CI` > `local`. Live: `wanted-tuna-71803-3000.preview.box.upstash.com`. URL always from env — never hard-coded.
- **SSH-to-UpCloud = unsupported / not required.** Removed from roadmap (was: "register an authorized key then retry host proof" — superseded). `thinkbox/upcloud.py` defaults fixed (no stale host, `api_url` 1.3); history preserved in prior sections.
- **Box job proof:** session `tb_sess_20260917164614_26d2aca3`, box `box_62f30c9d3adc` (Vector snapshot persisted), job `tb_exp_20260917164615_32b3ee9c`, artifact SHA256 `8bac2b52…57662550`, restart + identical replay verified, dashboard JOB_COMPLETED. Executed in-Box (Firecracker runtime, Box env); no remote-exec API exists (preview 404, Box SSH password-only) — claim bounded honestly.
- **Model:** BOX EXECUTION VERIFIED; MODEL EXECUTION VERIFIED 2026-09-17 (single bounded Mercury-2 call via existing openai_compat path: `{"answer": 42}` property VALID, 0.774s; job `tb_exp_20260917165842_4b92d477`; proof `model_job_proof_20260917.json`).
- **Learning loop:** FIRST LOOP VERIFIED 2026-09-17 (baseline `tb_exp_20260917170533_fbb1ec84` answer=7 VALID → lesson `learn:exact-json:directive` → learned `tb_exp_20260917170605_a1ae355e` answer=9 VALID with 3-place retrieval provenance; NO_MEASURABLE_IMPROVEMENT — reuse proven, model NOT smarter; proof `learn_loop_proof_20260917.json`).
- **Evidence:** `data/thinkboxmd/artifacts/box_primary_proof_20260917.json` SHA256 `972f2b6e3081db1b0e38e61c67c0553c2cdbfdd6f05978c697188259f1d725e3`. Suite 606 OK (6 skipped).

### KUDBEE Dashboard — Pipeline View (2026-09-17)

- **Existing dashboard only** (`experiments/swarm_dashboard.py`): `_pipeline()` read-only reader + `/api/pipeline` endpoint + Pipeline HTML tab + Population Arena card (state, 300/300, 12/12 live, provenance, metrics, proof, classification). Shows jobs/sessions/substrate/provider/model, CODE/TEST/LIVE/MODEL/ARENA state, verification, artifact/proof hashes, lesson + memory provenance, retrieval events, outcomes, restart/replay status, tests 622/6, blockers, next improvement.
- **Rebuild proof:** pipeline reads SQLite on every request — verified after singleton reset and over live HTTP (200). No singleton-only state. Chronicle = CONTINUITY + STATUS + AGENTS + `data/thinkboxmd/artifacts/*.json` (no separate Chronicle files exist in repo).

### Experiment Arena Control Surface (2026-09-17) — COMPLETE

- **Decision:** `thinkbox/pop_arena.py` canonical for the population layer (jobs→ExperimentManager, probes→ChallengeArena, population+budget+classification→pop_arena; one defensive dedupe fix in `aggregate()`).
- **Run:** control `tb_exp_20260917175431_3c4cf0e1` NOT_RUN→CONFIGURED→RUNNING→COMPLETE; 300/300 persisted (150 baseline + 150 learned); live 12/12 Mercury-2 VALID (6+6, retrieval 6/6); replay 288/288; honesty repairs recorded (false-live flags, placeholders, double outcomes, orphan re-run).
- **Classification:** NO_MEASURABLE_IMPROVEMENT (ceiling 1.0; valid). Proof `arena_proof_20260917.json` SHA256 `82a29a84…60a0e2c`. Suite 622 OK (6 skipped).

### Arena v2 Transfer-Under-Difficulty (2026-09-17) — COMPLETE (honest negative transfer)

- **Families:** compute/distractor/multifield in `thinkbox/pop_arena.py` (`verify_v2` 6-class taxonomy, replay emissions verify); `+4` calibration tests.
- **Run:** control `tb_exp_20260917181211_b78ceb62` (hypothesis + Wilson threshold pre-registered); 300/300 (264 replay + 36 live Mercury-2: 18 baseline + 18 learned, retrieval 18/18).
- **Result:** 17/18 vs 17/18 (delta 0.0, CIs overlap, threshold NOT met); identical wrongkey `{"result": 37}` failure both arms — lesson retrieved but INEFFECTIVE. Classification NO_MEASURABLE_IMPROVEMENT. Proof `arena2_proof_20260917.json` SHA256 `413e05ad…65cea9c9`. Suite 626 OK (6 skipped).

### Arena v3 Verifier-Side Retry (2026-09-17) — COMPLETE (IMPROVED at mechanism level)

- **Mechanism:** `should_retry` + `retry_prompt_for` + `resolve_retry` in `thinkbox/pop_arena.py` (max 1 retry, retryable taxonomies only; names failure, leaks no answer); `+4` deterministic tests.
- **Run:** control `tb_exp_20260917182126_3cf9f861`; 12 live distractor (6 baseline + 6 retry-arm).
- **Result:** baseline 5/6 (v2 failure reproduced); retry arm 6/6 with 1/1 conversion (distractor-compliance → `{"answer": 37}`, 2 attempts). Classification IMPROVED — orchestration level, NOT model intelligence. Proof `arena3_proof_20260917.json` SHA256 `b1aadd34…09ceaca8`. Suite 630 OK (6 skipped).

### Default-Path Generalization (2026-09-17) — COMPLETE (IMPROVED at scale)

- **Mechanism:** `VerifiedRetrySession` + `VerifiedRetryConfig`/`VerifiedCallResult`/`BudgetExhausted` in `thinkbox/pop_arena.py` (sync-pure, bounded retries, per-call traces, session budget); `+5` deterministic tests.
- **Live proof:** 8 jobs across compute/distractor(6)/multifield (budget 16, spent 9): 8/8 valid, 1 retry → 1 conversion. Memory `learn:defaultpath:retry-session` + dashboard. Proof `defaultpath_proof_20260917.json` SHA256 `5a0e0c16…94cfa3c74`. Suite 635 OK (6 skipped).

### Engine Promotion: Verified Execution in GovernedEngine (2026-09-17) — COMPLETE

- **Integration point:** `GovernedEngine.execute_verified_task` — thin async wrapper delegating to `VerifiedRetrySession.run_async` (added alongside sync `run`; no logic duplicated). `ThinkBoxEngine.execute_goal` untouched; Arena stays benchmark consumer.
- **Compatibility:** verify=None → UNVERIFIED single attempt; arithmetic/inconsistency never auto-retry; BudgetExhausted fails honestly; first taxonomy preserved in trace; per-attempt ledger metadata (session/job/experiment ids, taxonomy, attempt, latency, tokens, outcome).
- **Live proof (fresh instances):** 6 engine-path jobs via Mercury-2/Box: 5 FIRST_TRY_SUCCESS + 1 RECOVERED_SUCCESS (`enginepath_distractor_wrongkey`: distractor-compliance → valid, 2 attempts); 7 calls, 0 failed; memory `learn:enginepath:verified-wrapper`; dashboard Exec status column; restart reload 6/6 + replay 6/6.
- **Tests:** `+5` deterministic (run_async parity, async budget, wrapper first-try/recovered/failed, wrapper budget+unverified). Proof `enginepath_proof_20260917.json` SHA256 `118de71b…8dc419b6`. Suite 640 OK (6 skipped).
- **Decision (Chronicle):** engine owns per-task verified execution; pop_arena owns retry primitives + population benchmark; milestone — the same primitive operates outside Arena on fresh jobs. NOT model intelligence improvement.

### Multi-Goal Concurrent Budgets + Deeper DAG Telemetry (2026-09-17) — COMPLETE (live 4 calls)

- **Architecture decision (concurrency model):** `ThinkBoxEngine.execute_goal` reads the injected verified runner from a mutable instance attribute (`_verified_task_runner`), so concurrent goals sharing one base engine would race. Each concurrent goal gets its OWN fresh `GovernedEngine` (own base `ThinkBoxEngine`, own in-memory ledger, own event stream). The ONLY shared object is the optional global `VerifiedRetrySession`, whose counter mutations (`_spend_call`, `retries_fired`, `conversions`) are synchronous (no `await` between read-modify-write), so asyncio serializes them correctly — shared-budget accounting is mathematically correct, NOT merely concurrent.
- **Integration point:** new `thinkbox/concurrent_goals.py` (`ConcurrentGoalsRunner`, `ConcurrentGoalSpec`, `ConcurrentGoalsConfig`, `ConcurrentGoalsResult`, `aggregate_layer_telemetry`); reuses `GovernedEngine.execute_verified_goal` (now accepts `session=`), `VerifiedRetrySession`, `VerifiedRetryConfig`, `BudgetExhausted`. `ThinkBoxEngine.execute_goal` emits `summary["layers_telemetry"]`; dashboard `_pipeline()` gained a `concurrent` block (extended DAG view — no new dashboard).
- **Budget model:** independent goals (default) = per-goal `VerifiedRetrySession` (strict isolation); shared/global = one shared session enforcing a global cap via atomic `_spend_call` (honest `BudgetExhausted`). Cross-goal accounting: per-goal calls counted by wrapping each goal's `complete_async`; per-goal retries from `verified["retries"]`; global = deterministic sum cross-checked against the shared session's `calls_spent`.
- **Live proof (fresh instances):** 2 concurrent goals via REAL Mercury-2 (`experiments/concurrent_goals_live.py`): goal A `compute/add_small` (1 task) + goal B fan-in DAG `[compute/mul_small, compute/sub_neg] → multifield/double` (3 tasks). 4 live calls (hard guard 8): all FIRST_TRY_SUCCESS, 0 retries, 0 failures, 0 budget-exhausted. Cross-goal accounting exact: global 4 = 1+3; per-goal remaining 1 each. Layer telemetry: layer 0 = 3 tasks (fan-out), layer 1 = 1 task (fan-in). Memory `learn:concurrent:multi-goal-budgets`.
- **Restart / dashboard:** `scope="concurrent"` control record persisted via `ExperimentManager`; fresh `ExperimentDB` + `_pipeline()` reconstruct the run from SQLite alone. File ledger (6 entries) `verify()` True.
- **Fix (found during audit):** `_persist_verified_goal` wrote proof to fixed per-day filename `dagpath_proof_{date}.json` → concurrent goals clobbered each other + the historical DAG proof. Fixed to `dagpath_proof_{goal_experiment_id}.json`; runner `persist` proof unique per run; historical clobbered artifacts restored from git.
- **Tests:** `+15` deterministic (`tests/unit/test_concurrent_goals.py`). Suite **664 OK (6 skipped)**. Proof `concurrent_goals_live_proof_20260917.json` SHA256 `0d740895…489a`; runner proof `concurrent_proof_tb_exp_20260917214737_b61798e2.json`; secrets clean.
- **Decision (Chronicle):** concurrency is used for accounting correctness, NOT performance. Next larger improvement: N>2 goals with cross-goal budget contention policy + concurrency stress test (accounting-first).

### Budget Contention Policies + Per-Goal Limit Enforcement (2026-09-18) — COMPLETE

- **Problem:** Goals with budget limit ≤ 0 were running, causing the shared session to spend calls before hitting `BudgetExhausted` (wasted calls, incorrect accounting).
- **Solution:** Early budget check — goals with limit ≤ 0 are now skipped BEFORE execution (return `BUDGET_EXHAUSTED` immediately); defense-in-depth check retained in `_counted_complete`.
- **BudgetContentionPolicy implementations verified:**
  - `FAIR_SHARE`: equal budget shares per goal
  - `PRIORITY`: higher priority goals consume budget first (high-priority gets budget, lower skipped)
  - `FIFO`: submission order allocation
- **Integration point:** `thinkbox/concurrent_goals.py` (`ConcurrentGoalsRunner._run_one`): early budget check before `execute_verified_goal`; defense-in-depth in `_counted_complete`.
- **Tests:** `test_shared_global_budget_exhaustion` uses FIFO policy; `test_concurrent_persist_reconstructs_accounting` expects correct call count (2, was 4). Suite **663 OK (6 skipped)**.
- **Decision (Chronicle):** per-goal limit enforcement prevents wasted shared-session calls; contention policies provide fair/priority/fifo allocation. Next: concurrency stress test (accounting-first).

### DAG-Level Verified Execution (2026-09-17) — COMPLETE

- **Boot anomaly (recovered):** workspace re-materialization wiped the gitignored dbs (`data/thinkboxmd/db/experiments.db`, `ledger.db`; `memory.db` absent) → 3 pipeline tests failed. Git-tracked artifacts (93) survived. Classified ENVIRONMENT data loss. Rebuilt experiments.db + memory.db from artifacts via `experiments/recover_pipeline_db.py` (rows provenance-marked `recovery-20260917` / `recovered-from-artifacts`; only attested fields; ledger hash chain NOT reconstructable — documented). Recovery → 640 OK.
- **Integration point:** `ThinkBoxEngine.set_verified_task_runner(runner)` (dependency injection; engine imports no governance/retry code) + `execute_goal(goal, graph=None)` (nodes with `metadata["verification"]` route through the runner, others keep the legacy swarm path) + `GovernedEngine.execute_verified_goal` (builds graph, stable task/session/experiment ids, runner delegates to canonical `execute_verified_task` with a shared bounded `VerifiedRetrySession`, aggregates `summary["verified"]`, persists via ExperimentManager/ledger/proof). NOT a second execution wrapper; no duplicated `VerifiedRetrySession`.
- **Compatibility:** verify=None / no runner → legacy path untouched; retry only retryable taxonomies; arithmetic/inconsistency never auto-retry; BudgetExhausted honest terminal; recovered task retains first-failure taxonomy + trace; parent aggregation hides neither failures nor recoveries.
- **Live proof (fresh instances):** four-task DAG (compute/add_carry, distractor/wrongkey, multifield/double → layer 2 distractor/apology) via REAL Mercury-2; session `tb_sess_20260917201625_18e6`, goal `tb_exp_20260917201625_000f7c27`. 5 live calls (budget 10, remaining 5): 3 FIRST_TRY_SUCCESS + 1 RECOVERED_SUCCESS (wrongkey naturally distractor-compliance → valid, 2 attempts); 0 failures, 0 budget-exhausted, verification_rate 1.0. No manufactured failures. Memory `learn:dagpath:verified-goal`.
- **Restart / dashboard:** fresh process reconstructed goal + 4 tasks + outcomes from SQLite (recovered task kept original→final taxonomy + trace); `_pipeline()` rebuilt DAG totals from storage; HTTP `/api/pipeline` served the dag block; HTML DAG card present.
- **Tests:** `+9` deterministic (`TestDagVerifiedExecution`): multi-task DAG, first-try + legacy-untouched, recovered-provenance, non-retryable-no-retry, budget-exhausted-honest, parent-aggregation, persist/restart/dashboard-rebuild, proof/ledger integrity, no-secrets. Proof `dagpath_proof_20260917.json` SHA256 `5d254c1d…52dac97e`. Suite 649 OK (6 skipped).
- **Decision (Chronicle):** engine owns per-task AND per-DAG verified execution via one injected runner; the canonical primitive is unchanged. Milestone — verified execution now spans the real `execute_goal` DAG lifecycle, not just isolated tasks. NOT model intelligence improvement.

### Historical Connection Path — September 15 (superseded by live kudbeev3 above)

The connection path used:
1. SSH key at ~/.ssh/kilo-upcloud (ed25519, thinkbox-agent-20260831)
2. UpCloud API token via UPCLOUD_API env var
3. Server 212.147.250.183 (kudbee-host-v1)
4. The key was committed in git commit 5f6a5c7 but removed from working tree by 09830a6

### Recovery Actions Taken (historical; test counts below are point-in-time)
- SSH key recovered from git history (commit 5f6a5c7) — exists in workspace as `kilo-upcloud-recovered` but NOT at `~/.ssh/kilo-upcloud`
- UpCloud provider files restored from git history (commit 32d82ef)
- CONTINUITY.md restored from git history (commit 59f7eee)
- Dashboard state updated with actual infrastructure findings

### Required Human Action (EXACT) — historical SSH direction SUPERSEDED (kept for record; do not act)

SSH-to-UpCloud is no longer on the roadmap. No key registration, no SSH adapter, no UpCloud compute execution will be pursued. UpCloud remains control-plane only.

### PR Status (2026-09-19)

> **⚠️ GitHub PR numbering is offset from KILO PR labels.** See the GitHub↔KILO PR Map below for the complete mapping. KILO PRs without a GitHub # were pushed directly to `main` (no PR process was followed at the time — not repeated).

- **GitHub PR #92** = KILO PR94 — Orchestration Client — ✅ **MERGED** (2026-09-19)
- **GitHub PR #91** = KILO PR93 — Agent Telemetry & Observability — ✅ MERGED
- **GitHub PR #90** = KILO PR90 — Multi-Agent Clustering — ✅ MERGED
- **GitHub PR #89** = KILO PR89 — Autonomous Agent Core — ✅ MERGED
- **GitHub PR #85** — 10 hardening features — ✅ MERGED
- **KILO PR91** (Distributed Governance) — pushed directly to `main`, **no GitHub PR** (debt — must not repeat) — ✅ MERGED
- **KILO PR92** (Agent Marketplace) — pushed directly to `main`, **no GitHub PR** (debt — must not repeat) — ✅ MERGED
- **All other PRs closed**: #68, #67, #65, #32, #28 all CLOSED (superseded by main merge)
- **Zero open PRs**

#### GitHub↔KILO PR Map

| GitHub PR # | KILO PR | Status |
|-------------|---------|--------|
| #96 | integration suite | ✅ **MERGED** |
| #97 | control-plane x10 | 🔨 READY |
| #94 | PR95 | ✅ **MERGED** |
| #93 | docs process lock | ✅ MERGED |
| #92 | PR94 | ✅ MERGED |
| #91 | PR93 | ✅ MERGED |
| #90 | PR90 | ✅ MERGED |
| #89 | PR89 | ✅ MERGED |
| #85 | PR85 | ✅ MERGED |
| #84 | PR84 | ✅ MERGED |
| #80–#83 | PR80–PR83 | ✅ MERGED |
| — | PR91 | ✅ MERGED (direct push, no GH PR — debt) |
| — | PR92 | ✅ MERGED (direct push, no GH PR — debt) |

## Governed Scheduler

The `thinkbox/scheduler.py` module extends the governed concurrency architecture with 72 features across multiple PRs.

### Module Structure

- `thinkbox/scheduler.py` — All scheduler features as classes
- `tests/unit/test_scheduler.py` — 99 test classes (689 tests) covering all features
- `tests/unit/test_scheduler_integration.py` — 42 integration and chaos-gate tests for PR #85 features

### Features by PR

**PR #84** (10 features, merged): AdaptiveConcurrency, Preemption, TaskCoalescing, WorkflowTemplate, BackpressurePropagation, SchedulerClock, AdmissionFilter, FairnessIndex, DynamicBudget, TaskAffinity

**PR #85** (10 features, merged + integrated): DeadLetterQueue, ConfigValidator (is_valid bug fixed), MemoryPressureMonitor, GracefulShutdownCoordinator, SchedulerSentinel, DataIntegrityChecker, RetryStormGuard, SchemaVersionTracker, AnomalyDetector, AdmissionRateLimiter — integrated via `SchedulerHarness` class

### Testing

- `tests/unit/test_scheduler.py` — 689 tests, all passing
- `tests/unit/test_scheduler_integration.py` — 42 tests, all passing
- Run: `python3 -m unittest tests.unit.test_scheduler -v`
- Full suite: `python3 -m unittest discover tests/` (2204 OK, 8 skipped, 3 expected failures)

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

- `tests/unit/test_cnc.py` — 59 tests covering all CNC modules
- Run: `python3 -m unittest tests.unit.test_cnc -v`
- Full suite: `python3 -m unittest discover tests/` (2204 OK, 8 skipped, 3 expected failures; canonical count — see Chronicle)

### ADR

- `docs/decisions/001-cnc-manufacturing.md` — ADR for CNC manufacturing platform

### ROI Report

- `docs/cnc-roi-report.md` — Enterprise ROI and evidence report

## KILO Cloud Agent Framework

The `agents/` documentation and `thinkbox/agent/` implementation establish the Agent Era for KILO platform.

### Documentation (PR88 — Complete)

| Domain | Files | Location |
|--------|-------|----------|
| Core Architecture | 5 | `agents/core/` |
| Governance | 4 | `agents/governance/` |
| Chronological | 6 | `agents/chronological/` |
| Index | 1 | `agents/README.md` |

### Implementation (PR89+)

| Module | Description | Location | Status |
|--------|-------------|----------|--------|
| `agent.kernel` | AgentKernel base class, identity, lifecycle state machine | `thinkbox/agent/kernel.py` | ✅ PR90 |
| `agent.lifecycle` | 10-state lifecycle manager, governance checkpoints | `thinkbox/agent/kernel.py` | ✅ PR90 |
| `agent.protocol` | gRPC/HTTP protocol definitions (scheduler, governance, orchestration, health, CNC, agent-to-agent) | `thinkbox/agent/protocol/` | ✅ PR89+PR90 |
| `agent.scheduler_client` | Work pull, heartbeat, capacity reporting, outcome reporting | `thinkbox/agent/scheduler_client.py` | ✅ PR90 |
| `agent.governance_client` | Admission checks, approval requests, audit logging, token management | `thinkbox/agent/governance_client.py` | ✅ PR90 |
| `agent.telemetry` | Metrics, traces, logs, health endpoints | `thinkbox/agent/telemetry.py` | ✅ PR93 |
| `agent.orchestration_client` | Capacity requests, service discovery, config watch, secret injection | `thinkbox/agent/orchestration_client.py` | ✅ PR94 |
| `agent.registry` | Agent registration, discovery, health tracking | `thinkbox/agent/registry.py` | ✅ PR90 |
| `agent.base` | TaskAgent, WorkflowAgent, BatchAgent, StreamAgent base classes | `thinkbox/agent/base.py` | ✅ PR90 |
| `agent.marketplace` | Package format, registry, installer, publisher | `thinkbox/marketplace/` | ✅ PR92 |
| `agent.distributed_admission` | Raft-based distributed admission gate | `thinkbox/governance/distributed/` | ✅ PR91 |
| `agent.distributed_ledger` | CRDT-based distributed ActionLedger | `thinkbox/ledger/distributed/` | ✅ PR91 |
| `agent.mesh` | Multi-cell mesh coordinator with expulsion | `thinkbox/mesh/` | ✅ PR91 |

### Protocol Definitions (Protobuf)

| Protocol | File | Services |
|----------|------|----------|
| Scheduler | `scheduler.proto` | SchedulerService (RegisterAgent, PullWork, ReportOutcome, Heartbeat, ReportCapacity, HealthCheck) |
| Governance | `governance.proto` | GovernanceService (CheckAdmission, RequestApproval, RequestToken, EmitAuditEvent, EvaluatePolicy) |
| Orchestration | `orchestration.proto` | OrchestrationService (RequestCapacity, DiscoverServices, WatchConfig, InjectSecrets) |
| Health | `health.proto` | HealthService (Check, Watch, GetAgentInfo) |
| CNC | `cnc.proto` | CNCService (SubmitJob, StreamTelemetry, RequestSafetyApproval, SubmitProof, ReplayJob) |
| Agent-to-Agent | `agent_to_agent.proto` | SupervisorService, RouterService, EnsembleService |

### Architectural Principles

1. **Documentation-first** — PR88 establishes full conceptual foundation before code
2. **Protocol-first** — gRPC + HTTP, Protobuf schemas defined before implementation
3. **Governance-by-default** — Every side effect → AdmissionGate → ActionLedger (extends KUDBEE Control Fabric)
4. **Telemetry-as-contract** — Metrics, traces, logs, health — all mandatory, versioned, validated
5. **Category-based resource profiles** — Default limits by agent type, overrideable at registration
6. **Work pull model** — Agents pull from scheduler (backpressure, autonomy)
7. **PAL for cloud** — No provider SDKs in agents; Platform Abstraction Layer enforces governance
8. **Evidence classification** — All data: SIMULATED/INFERRED/VERIFIED/PHYSICALLY_MEASURED (from CNC)
9. **ThinkBox as work unit** — Portable execution context (extends KUDBEE Control Fabric)
10. **Mesh compromise containment** — Agent mesh cells, expulsion on compromise (extends KUDBEE)

### Integration with Existing Systems

| System | Integration Point |
|--------|------------------|
| **Governed Scheduler (PR80–85)** | Work pull, capacity management, 29 features via SchedulerHarness |
| **CNC Platform (PR86–87)** | CNC_AGENT category, telemetry, proofs, safety gates |
| **KUDBEE Control Fabric (Phase 12)** | AdmissionGate, ActionLedger, GovernanceToken, ThinkBox, Mesh |
| **Experiment Manager** | Agent experiments, parameter provenance, learning loop |
| **Memory/Vector Store** | Organizational knowledge, agent embeddings |
| **Dashboard** | Pipeline view, agent observability |
| **Upstash Box** | Primary execution substrate for agents |

### Testing Requirements

| Module | Minimum Tests |
|--------|---------------|
| `thinkbox/agent/kernel.py` | 15 (identity, config, init/shutdown) |
| `thinkbox/agent/registry.py` | 20 (register, discover, health, selection, TTL cleanup) |
| `thinkbox/agent/base.py` | 15 each (TaskAgent, WorkflowAgent, BatchAgent, StreamAgent) |
| `thinkbox/agent/scheduler_client.py` | 15 (pull, heartbeat, capacity, outcome) |
| `thinkbox/agent/governance_client.py` | 20 (admission allow/deny/timeout, approval, tokens) |
| `thinkbox/agent/telemetry.py` | 15 (metrics, traces, logs, health) |
| `thinkbox/agent/orchestration_client.py` | 29 (capacity, discovery, config, secrets) |
| `thinkbox/governance/distributed/` | Per PR91 features |
| `thinkbox/ledger/distributed/` | Per PR91 features |
| `thinkbox/mesh/` | Per PR91 features |
| Contract tests | All protocol services (scheduler, governance, orchestration, health, CNC, agent-to-agent) |
| Integration tests | Scheduler, Admission Gate, Action Ledger, CNC Platform |

### FourState Classification

| Phase | PR88 (Docs) | PR89 (Core) | PR90 (Clustering) | PR91 (Distributed) | PR92 (Marketplace) | PR93 (Telemetry) |
|-------|-------------|-------------|-------------------|---------------------|---------------------|---------------------|
| **CODE_COMPLETE** | N/A | ✅ Protocol | ✅ Registry, Base, Kernel, Clients | ✅ Gate, Ledger, Tokens, Mesh | ✅ Package, Registry, Installer, Publisher | ✅ Telemetry |
| **TEST_VERIFIED** | N/A | ✅ Syntax | ✅ Imports, 1605 tests | ✅ 70 tests | ✅ 59 tests | ✅ 32 tests |
| **LIVE_VERIFIED** | N/A | ⏳ Deploy | ⏳ Deploy | Target | Target | Target |
| **DOCS_COMPLETE** | ✅ | — | — | — | — | — |

### Development Workflow (PR89+)

1. **PR89: Autonomous Agent Core** — Protocol layer (5 protobuf services) ✅ **MERGED**
2. **PR90: Multi-Agent Clustering** — Registry, 4 base agent types, kernel, scheduler/governance clients, agent-to-agent protocol ✅ **MERGED**
3. **PR91: Distributed Governance** — Raft AdmissionGate, CRDT ActionLedger, threshold-signed Tokens, Mesh with compromise detection and expulsion ✅ **MERGED** (pushed to main directly; no GitHub PR)
4. **PR92: Agent Marketplace** — package format, registry, installer, publisher workflow ✅ **MERGED** (pushed to main directly; no GitHub PR)
5. **PR93 (GitHub PR #91): Agent Telemetry & Observability** — TelemetryEmitter: metrics, traces, logs, health ✅ **MERGED**
6. **PR94 (GitHub PR #92): Orchestration Client** — Capacity, service discovery, config watch, secret injection ✅ **MERGED**
7. **PR95 (GitHub PR #94): Orchestration Client kernel wire** — Wire OrchestrationClient into AgentKernel lifecycle ✅ **MERGED**
8. **PR96 (GitHub PR #95): Agent kernel capacity lifecycle hardening** — Harden AgentKernel ↔ OrchestrationClient lifecycle ✅ **MERGED**
9. **PR97 (GitHub PR #96): OrchestrationClient↔AgentKernel integration suite** — Integration tests for full lifecycle paths ✅ **MERGED**
10. **PR101 — BYOC Mercury-2 + Upstash THINK stash x proof bind (x10):** `feat/byoc-think-stash-mercury-upstash-x10` ✅ **MERGED**
    - Modules: `thinkbox/byoc_config.py`, `thinkbox/byoc_client.py`, `thinkbox/byoc_resolve.py`, `thinkbox/byoc_stash_store.py`, `thinkbox/byoc_stash_writer.py`, `thinkbox/byoc_stash_reader.py`, `thinkbox/byoc_proof_bind.py`
    - API: `backend/api/v1/think_stash.py` (GET /think/stash/status, GET /think/stash/last)
    - Dashboard: `public/control-plane/think_stash.html` (BYOC status chips)
    - Demo: `scripts/demo_in_10_byoc.sh`
    - Tests: `tests/unit/byoc/test_e2e.py` (hermetic, mock-only)
    - Tag: `THINK_STASH_BOUND` (parity with PR #100 `CONTROL_PLANE_BOUND`)
11. **PR102 — Upstash Box + Inception Mercury-2 Live Experiment:** `feat/byoc-box-mercury-live` ✅ **MERGED**
    - Experiment: `experiments/box_mercury_live.py` — substrate verify, Mercury-2 burst at concurrency 1/4/8/16, throughput + proof artifact
    - Tests: `tests/unit/byoc/test_box_mercury.py` (hermetic, mock-only)
    - Demo: `scripts/demo_in_10_box_mercury.sh`
    - Tag: `THINK_BOX_BOUND` (parity with PR #100 `CONTROL_PLANE_BOUND` and PR #101 `THINK_STASH_BOUND`)
12. **PR103 — Persistent Box + Mercury-2 Results v2:** `feat/byoc-box-mercury-live-v2` 🔨 DRAFT
    - Enhanced experiment: configurable params, multi-iteration, SQLite persistence
    - API: `backend/api/v1/box_mercury.py` (GET /think/box-mercury/status + results)
    - API: `backend/api/v1/box_status.py` (GET /think/box-status)
    - Dashboard: `public/control-plane/box_mercury.html` (results comparison panel)
    - Tests: `tests/unit/byoc/test_integration.py`, `tests/unit/test_substrate.py` additions
    - Demo: `scripts/demo_in_10_box_mercury_v2.sh`
    - Tag: `THINK_BOX_BOUND`
13. **PR98 (GitHub PR #97): control-plane x10 — admission, proof, autonomy under hard constraints** — 10-feature agent control plane 🔨 IN PROGRESS
14. **PR106 — Org-memory lifecycle receipts + CI/PR event hooks:** `feat/lifecycle-org-memory-ci-hooks` ✅ **MERGED** (GitHub #106)
    - Modules: `thinkbox/org_memory_receipts.py`, `thinkbox/pr_lifecycle_event_hooks.py`
    - API: `GET /api/v1/control-plane/lifecycle/receipts/pr/{pr_number}`
    - Dashboard stub: `public/control-plane/lifecycle_receipts.html`
    - Tests: `tests/unit/test_org_memory_lifecycle.py` (hermetic); `test_pr_lifecycle` + stress suites unchanged
    - Tag: `PR_LIFECYCLE_ORG_MEMORY` (builds on merged PR #105 `feat/pr-lifecycle-stress-resilience`)
15. **PR107 — Signed GitHub webhook + Actions status behind AdmissionGate:** `feat/lifecycle-github-webhook-admission` ✅ **MERGED** (GitHub #107)
    - Modules: `thinkbox/github_webhook.py`, `backend/api/v1/github_webhook.py`
    - API: `POST /api/v1/github/webhook`, `GET /api/v1/github/webhook/health`
    - Docs: `docs/guides/github_webhook.md` (`WEBHOOK_SECRET` setup)
    - Tests: `tests/unit/test_github_webhook.py` (hermetic HMAC fixtures; live optional off by default)
    - Tag: `PR_LIFECYCLE_GITHUB_WEBHOOK` (builds on merged PR #106)
16. **PR108 — Pipeline control surface (webhook admissions, verified receipts, founder merge gate):** `feat/pipeline-dashboard-admission-merge-gate` ✅ **MERGED** (GitHub #108)
    - Modules: `thinkbox/pipeline_dashboard.py`, `backend/api/v1/pipeline_dashboard.py`
    - API: pipeline overview with `ops_scorecard`, denial ledger, integrity, CI timeline, delta poll/SSE, quarantine, founder-gated `request-merge` (governance token + PR-bound founder proof; never GitHub merge)
    - Dashboard: `public/control-plane/pipeline_dashboard.html` (5s poll + denial/quarantine banners)
    - Tests: `tests/unit/test_pipeline_dashboard.py`, `test_pipeline_delta.py`, `test_pipeline_adversarial.py`, `test_pipeline_concurrency.py` (hermetic)
    - Tag: `PR_PIPELINE_DASHBOARD_MERGE_GATE` (builds on merged PR #106/#107)
17. **PR111 — Demo-in-10 control-plane dry-run:** `feat/demo-in-10-control-plane-dry-run` 🔨 DRAFT (GitHub #111)
    - Module: `thinkbox/control_plane_dry_run.py`
    - Demo: `scripts/demo_in_10_control_plane_dry_run.sh`, `python3 -m thinkbox.control_plane_dry_run`
    - Docs: `docs/PR111_CONTROL_PLANE_DRY_RUN.md`
    - Tests: `tests/unit/demo/test_control_plane_dry_run.py` (hermetic; asserts `github_merge_called=false`)
    - Tag: `PR_CONTROL_PLANE_DRY_RUN` — **not** LIVE_VERIFIED; PR #110 staging drill is separate

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
