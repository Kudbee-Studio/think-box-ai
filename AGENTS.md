# AGENTS.md — THINK BOX AI

**Purpose:** Single source of truth for every agent (human or AI) working in
this repository — **KILO**, **Cloud Bot**, **Cursor Cloud Agent**, **Coding
agents**, and founder-operated sessions. Operational rules live here;
structural boundaries live in `docs/architecture-v1.md` and
`docs/kudbee-control-fabric.md`.

**Related:** `KUDBEE_AGENT_RUNTIME_CONTRACT.md` (env inventory),
`STATUS.md` (live measurements), PR #62 lineage (`mock_vllm`, burst, harvest).

---

## 1. Mission / Thesis

THINK BOX AI is a **control fabric**, not a chat wrapper.

| Principle | Meaning |
|-----------|---------|
| **Durable state outside the context window** | Session, task, organizational, and verified-knowledge layers persist independently of any single model call. The context window is a scratch pad, not the system of record. |
| **Governance admission before side effects** | No token → draft/simulate only. With token → act within scope. Every admission or denial is append-only in `ActionLedger`. |
| **Occupancy mesh** | Horizontal isolation via mesh cells; a compromised cell is expelled and never inherits peer capabilities. |
| **THINK harvest → reuse → improve** | Capture grounded vs ungrounded contrast pairs, reasoning channels, and verifier scores; replay and improve — do not rely on one-shot prompts. |
| **Not billion-token windows** | Quality and governance beat raw context size. Bounded bursts, elastic-cash ceilings, stop-when-idle GPU policy. |

The thesis is **evidence-backed agent execution**: portable Think Boxes, substrate
handoffs, and fail-closed tool governance — not “give the model more tokens.”

---

## 2. PR Policy (Standing)

Every meaningful change follows this workflow. **No exceptions.**

1. **Feature branch** — never commit directly to `main`.
2. **Open or update a GitHub PR** — target `main`.
3. **Paste the PR URL in your summary** — the task is not done at “committed to branch.”
4. **Never merge** — founder-only merge via Graphite/GitHub.
5. **Default: one PR per checkpoint** — one logical change set, one review surface.

### Branch naming

| Agent / context | Pattern | Example |
|-----------------|---------|---------|
| Cursor Cloud Agent | `cursor/<descriptive-name>-4de1` | `cursor/agents-md-update-4de1` |
| KILO / human | `feat/…`, `fix/…`, `docs/…`, `refactor/…` | `feat/phase12-kudbee-control-fabric` |

### Commit messages

Format: `type(scope): description`

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

### What to commit

Source, tests, docs, config (`pyproject.toml`, etc.).

**Never commit:** secrets, `.env`, model weights, `__pycache__`, IDE configs.

### Git hygiene

- One logical change per commit; rebase or squash on feature branches (no merge commits).
- Keep the branch current with `main` before opening a PR.
- CI must pass; no PR merges without green checks.

---

## 3. Agent Lanes

Each agent owns a lane. **Do not hijack another lane’s infrastructure or PRs.**

| Lane | Owns | Does not own |
|------|------|--------------|
| **Cloud Bot** | AWS GPU ops on **think-v2** (`i-0685561c90845986d`): start/stop instance, vLLM health, SSM session availability, stop-when-idle | Repo code changes unless explicitly tasked; KILO app work |
| **KILO** | `think-box-ai` app, harness, docs, burst/disruptor/harvest code paths, PRs for product/eval | Starting/stopping GPU instances; AWS console ops; key hunts |
| **Cursor Cloud Agent** | Isolated feature branches + PRs per cloud task instructions | GPU lifecycle; merging |
| **Coding agents** (local IDE, OpenCode, etc.) | Scoped code edits in assigned areas | Cross-lane infra without handoff |
| **GROKBOT** | GitHub Discussions payloads for inter-agent messaging | Direct repo writes without PR policy |
| **Founder** | Merge authority, think-v2 start/stop, budget approval, lane arbitration | — |

**Handoff pattern:** Cloud Bot posts “models OK” (or equivalent) when think-v2
loopback is healthy; KILO runs `--live` bursts against `127.0.0.1:8001` only
after that signal. KILO does not SSH/SSM into production GPU boxes unless
explicitly authorized for a one-off debug with founder present.

---

## 4. gpt-oss-20b Access (think-v2)

Production 20B inference runs on AWS **think-v2**, not UpCloud CPU.

| Item | Value |
|------|-------|
| Instance | `i-0685561c90845986d` (A10G) |
| Access | **CloudShell SSM preferred** (Cloud Bot / founder) |
| SSM | `AWS_PAGER="" aws ssm start-session --target i-0685561c90845986d --region us-east-1` |
| Endpoint | `http://127.0.0.1:8001` — **loopback only** |
| Auth | `Authorization: Bearer EMPTY` (literal token `EMPTY`; no key hunt for think-connect) |
| Model id | **`openai/gpt-oss-20b`** — bare `gpt-oss-20b` → **404** |
| HTTP | Use **HTTP/1.0** if curl hangs: `curl -sS --http1.0 -m 20 …` |
| Reasoning | Capture `delta.reasoning` / `message.reasoning`; never drop the reasoning channel |
| Bind | **No public bind** on `:8000` / `:8001` |
| think-v1 | Leave **stopped** — do not use for 20B bursts |
| Idle | **Stop GPU when idle** (stop instance, do not terminate) |

Health check on-box:

```bash
nvidia-smi -L
curl -sS --http1.0 -m 20 -H 'Authorization: Bearer EMPTY' http://127.0.0.1:8001/v1/models
```

Live burst (after governance token + models OK):

```bash
python3 -m thinkbox.burst --live --pairs 24 --minutes 12 --max-calls 64 --budget 5.00 --out data/evals/burst
```

---

## 5. Mock / Demo-in-10

**Demo-in-10** is the ship wedge: prove the control fabric in ~10 minutes without
burning GPU dollars.

### mock_vllm (transport boundary only)

- Module: `thinkbox/mock_vllm.py`
- Binds **`127.0.0.1:8001` only** — strict transport mock, no governance fork
- Model id: `openai/gpt-oss-20b`; auth `Bearer EMPTY`; HTTP/1.0 supported
- Start: `python3 -m thinkbox.mock_vllm`

### Prove the path

```bash
# Terminal A
python3 -m thinkbox.mock_vllm

# Terminal B — smoke (adjust budgets for CI)
python3 -m thinkbox.burst --live --pairs 2 --minutes 1 --max-calls 8 --budget 1.00 --out data/evals/burst-smoke
```

Offline (no server): `python3 -m thinkbox.burst` uses synthetic model; unit
tests must pass without GPU.

### Lineage

Prefer **PR #62** lineage (`kilo/amber-link-x8y`): `burst`, `disruptor`,
`harvest`, `grounding`, `factcards`, `reasoning`, `verifier`. Do not fork
governance semantics for demos — mock at the **HTTP transport** layer only.

Full burst checklist (when documented): `docs/think-burst-protocol.md`.

---

## 6. UpCloud

| Item | Detail |
|------|--------|
| Host | **KUDBEEV3** (US-CHI1) |
| Role | CPU control-plane / worker (~**$286/mo**) |
| Use | Orchestration, dashboards, CPU workloads — **not** a substitute for A10G 20B |
| Idle | **Shut down when idle** — same elastic-cash discipline as GPU |
| Legacy | `kudbee-host-v1` references in older docs; treat access tokens/SSH as **unverified until founder confirms** |

UpCloud does **not** serve `gpt-oss-20b`. For 20B, use think-v2 (§4).

---

## 7. Safety / Secrets

- **Never commit secrets** — API keys, tokens, `.env`, SSH private keys, passwords.
- **Never print token values** in logs, PR bodies, or agent summaries. Name-only inventory is OK (`THINKBOX_*` set/unset).
- **Inject secrets at runtime** via environment variables or founder-managed secret stores.
- **Elastic cash / budget awareness** — burst runner enforces `max_calls`, `max_spend`, `max_minutes`; agents must not leave GPU or UpCloud running idle.
- **Tool governance** — tools without explicit `permission` are `RESTRICTED` and require approval.
- **Shell execution** — explicitly approved by the user; permission-checked before run.
- **Audit logs** — append-only; external HTTP with timeouts and retry limits.
- **No PII** in logs.

---

## 8. Evidence Over Assumptions

Label claims honestly:

| Label | Use when |
|-------|----------|
| **Proven** | Measured in CI, burst jsonl, benchmark output, or reproducible probe — cite path/command |
| **Hypothesized** | Design intent or expected behavior not yet measured |
| **Broken** | Probe failed — document defect path (see `STATUS.md`, `data/findings/`) |

Rules:

- Never commit “Model X is better” without a benchmark in `benchmarks/` or eval jsonl.
- Never store speculative claims in Organizational Memory.
- Report construction-based metrics honestly (e.g. offline `bind_failure_rate` reflects contrast-pair design, not live attack success).
- Prefer `STATUS.md` for live service state; prefer `AGENTS.md` for standing policy.

---

## 9. Architecture Principles

Non-negotiable. Violations require an ADR.

### 9.1 Layer Discipline

Five layers: Foundation → Provider → Memory → Governance/Tools → Runtime.
A layer may only import from layers beneath it.

### 9.2 Provider Independence

No model provider is hardcoded at the runtime layer. Swapping providers is
configuration, not code change. Runtime knows only the `ModelProvider` protocol —
never a provider-specific SDK.

Supported families: OpenAI-compatible APIs, Anthropic Messages API, local/vLLM
(Phase 2+).

### 9.3 Memory First

Four memory layers: Session, Task, Organizational, Verified Knowledge — each
with distinct scope, lifetime, and write policy. Never store transient UI state
in memory.

### 9.4 Governance by Default

Tools do not execute without permission checks. Approval gates are opt-out, not
opt-in. Side effects go through `GovernedEngine` / `AdmissionGate` — do not
bypass for convenience.

### 9.5 KUDBEE Control Fabric (Phase 12)

- Every side effect passes `AdmissionGate` with a valid governance token.
- No token → draft/simulate only.
- Every admission/denial appended to `ActionLedger`; chain must verify (`ledger.verify()`).
- Think Boxes are portable; handoffs preserve integrity.
- Compromised mesh cells expelled via `MeshCellManager`.
- Reference: `docs/kudbee-control-fabric.md`, modules in `thinkbox/identity.py`,
  `governance_token.py`, `admission.py`, `workspace.py`, `handoff.py`,
  `occupancy.py`, `capacity.py`, `ledger.py`, `thinktrace.py`, `governed.py`.

---

## 10. Coding Rules

### 10.1 Language

- **Core:** Python 3.10+
- **CLI wrapper (future):** TypeScript/Node (deferred)
- **No other languages** without a decision record

### 10.2 Dependencies

- Foundation phases: stdlib-first where possible.
- Every external dependency needs a documented trigger (`docs/project-foundation.md`).
- No speculative imports.

### 10.3 Style

- PEP 8; type hints on public functions; `dataclasses` for structures.
- Docstrings on public classes/functions.
- Comments explain *why*, not *what*.

### 10.4 Async

- Runtime is async (`asyncio`); I/O-bound work must be async.
- Blocking work isolated and explicitly marked.

### 10.5 Error Handling

- Never swallow exceptions silently.
- Structured errors carry: `agent_id`, `task_id`, `think_box_id`, `timestamp`,
  `error_type`, `context`.

### 10.6 Logging

- Stdlib `logging`; never log secrets, tokens, or PII.

---

## 11. Testing Requirements

### 11.1 Coverage

- Target 80% coverage for `core/` and `core/tools/` where applicable.
- CI runs on every PR; no merge without passing tests.

### 11.2 Structure

```
tests/
  unit/           # Pure logic, no I/O, no network
  integration/    # Memory store, provider HTTP client, tool execution
  e2e/            # Full runtime loop with mock provider
```

### 11.3 Requirements

- Every public function: at least one test.
- Every error path: a test.
- Tools: valid input, invalid input, permission denied, approval required.
- Memory: write, read, delete, conflict, retention.
- Phase 9/12 modules: valid, invalid, edge cases (`tests/unit/test_session_tracker.py` and control-fabric tests).

### 11.4 Commands

```bash
python3 -m unittest discover tests/ -v          # CI default (.github/workflows/test.yml)
python3 -m pytest tests/unit/                   # Fast subset when pytest available
python3 -m pytest tests/                        # Full pytest run
```

### 11.5 Mocking

- Mock providers in unit tests; no real HTTP in unit tests.
- Use `unittest.mock` from stdlib.

---

## 12. Documentation Requirements

| Artifact | Location | Required |
|----------|----------|----------|
| Architecture | `docs/architecture-v1.md` | Yes |
| Control fabric | `docs/kudbee-control-fabric.md` | Yes |
| Project foundation | `docs/project-foundation.md` | Yes |
| Decision records | `docs/decisions/NNN-*.md` | Per ADR |
| Module docstrings | In-code | Yes |
| Public API docstrings | In-code | Yes |
| Agent policy | `AGENTS.md` (this file) | Yes |
| Live status | `STATUS.md` | As needed |

### ADR format

See `docs/decisions/` — ADRs are never deleted; supersede with references.

Process: draft → review → accept with implementation → supersede when obsolete.

---

## 13. Code Review

- Every PR requires review before founder merge.
- Reviewers check: architecture compliance, tests, documentation, security, lane discipline.
- Reject cross-layer imports and undocumented dependencies.
- **Agents do not self-merge.**

---

## 14. Phase Boundaries

Historical phases built the stack; **do not revert completed work**. New work
must respect layer discipline and the phase that owns the feature.

| Phase | Scope | Notes |
|-------|-------|-------|
| 0 | Foundation | Docs, schemas, rules |
| 1 | Single agent, single provider, core tools | Baseline runtime |
| 2+ | Pattern extraction, local models, benchmarks | Incremental |
| 9 | Innovations (`coalition`, `consensus`, `economy`, `intelligence`, `benchmark`, `session`) | 55 features; see `PHASE9_INDEX.md` |
| 12 | KUDBEE control fabric | Governance admission, durable workspaces, occupancy mesh |

**Phase 9 modules** (`thinkbox/`): `coalition.py`, `consensus.py`, `economy.py`,
`intelligence.py`, `benchmark.py`, `session.py`.

Do not add unrelated phase scope in a single PR without an ADR.

---

## 15. When in Doubt

1. Read `docs/architecture-v1.md`.
2. Read `docs/project-foundation.md` and `docs/kudbee-control-fabric.md`.
3. Check `docs/decisions/` for prior ADRs.
4. Check `STATUS.md` for what is proven vs broken **today**.
5. If still uncertain, write an ADR before code.
6. Default to simplicity — the simplest solution that satisfies architecture wins.

---

## 16. Enforcement

- Code review (founder merge gate)
- CI: tests, lint, import ordering
- Architectural review for cross-layer imports
- Lane ownership (§3) and PR policy (§2)

Violations are bugs. Fix before merge.
