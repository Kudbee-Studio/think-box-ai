# ADR 029: The Think Token as a reconfigurable intelligence object

**Date:** 2026-10-01
**Status:** Proposed

Supersedes nothing. Builds on ADR 026 (Accepted: the unused Neon setup was reverted, so SQLite stays), ADR 027 (Proposed: default deny, tenant scoping) and ADR 028 (Proposed: Think Token persistence). Because 027 and 028 are still Proposed, the guardrails below inherit that status. Evidence base: [`docs/research/2026-10-01-think-box-findings.md`](../research/2026-10-01-think-box-findings.md). Docs only: this ADR changes no code.

Status words used below: CODE COMPLETE / TEST VERIFIED / LIVE VERIFIED / PRODUCTION READY, plus UNPROVEN (no evidence here) and CONCEPT (designed, not built). A status is the highest state with evidence and never implies the ones above it. Nothing here is PRODUCTION READY.

## Context

### Founder intent — VISION, not fact

> Think Box is a governed, persistent intelligence OS running the loop Intent → Plan → Execute → Observe → Learn → Prove → Reuse, built from Think Workers, Think Jobs, Memory and Proof. A Think Token is a dynamic intelligence object (NOT a crypto token; THNK is separate), visualised as a 100-square Rubik's-style cube whose squares reconfigure as it learns. Changes propagate across long-range connections between tokens and workers. A Disruption Token is new information that forces affected tokens to reconfigure. An Energy Core shows activity/propagation. The dashboard should feel like intelligence reorganising itself, not static SaaS cards.

Nothing in that paragraph is a claim about what exists today. The rest of this ADR separates what is built from what is intended.

### Where the code actually is (2026-10-01, `main` at `2bc4cf48`)

- Two Think Token systems coexist. **#288** (`learning-*.ts`, `think-token-*.ts`, table `learned_patterns` in `learning.db`) is wired into `AgentSession` and mints a token after a successful run that passes a content quality gate. **ADR 028** (`think-token-store.ts`, tables `think_tokens`, `think_token_uses`, `think_token_ledger` in `think-tokens.db`) adds reviewable learning units with an admission gate and a hash-chained ledger. They share no table. Evidence: ADR 028 implementation note; PR #306.
- The cube is a deterministic 100-cell reducer (`think-cube-state.js`), driven by real WebSocket thoughts, with a 12-stage vocabulary. It is a *visualization of one run's lifecycle*, not a per-token structure stored anywhere.
- The store holds 2 candidate tokens from one run, `uses` is 0, IDs are `tt_<16 hex of content hash>`, and the lessons are templates. See finding 9.

## Decision

Adopt the **Think Token intelligence object** as the target design, in five phases (P1–P5 below), each gated by tests and an `EVIDENCE.md`. Specifically:

1. A Think Token keeps ADR 028's SQLite store as its single system of record (ADR 026). No Postgres, no Neon, no Vercel, no second token model.
2. The 100-cell cube becomes a *view of a stored token*, derived deterministically from that token's row, its links and its run evidence — never from timers or demo events.
3. Tokens get a permanent human ID, `TT-000001`, allocated by SQLite.
4. Learning quality is treated as the main unproven risk and is measured, not assumed.
5. Disruption, long-range connections, the Energy Core and multi-worker propagation are **CONCEPT** until a phase delivers them with evidence.

## Glossary

| Term | Meaning in this ADR | Exists today? |
|---|---|---|
| Think Box | The governed runtime that runs the loop: admission, execution, evidence, proof. In code: the Python backend control plane plus the Node `AgentSession`. | Partly. Two tiers; no single "box" object. |
| Think Worker | One execution unit (an `AgentSession` run, or a specialist allocation). | In-process only. TEST VERIFIED. Distributed workers UNPROVEN. |
| Think Job | One unit of work with an id, a state and evidence (a goal run, or a specialist job with `jobId`). | CODE COMPLETE. Plain runs lack `run_id` on the goal thought (gap 8). |
| Think Token | A reusable, evidence-linked learning unit. **Not** THNK, not a crypto token, grants no permission. | Stored form TEST VERIFIED (ADR 028). The "intelligence object" form is CONCEPT. |
| Disruption | New information that may invalidate or change tokens: a tool error, new data, an opportunity, a changed decision. | Only the narrow "tool failure → disrupted cells" case is CODE COMPLETE. Otherwise CONCEPT. |
| Energy Core | The live indicator of real activity: jobs, workers, events, proofs. | Term and loop documented (`AGENTS.md` §1.3a). A live view is CONCEPT. |
| Memory | Continuity between runs: tiers `task`, `org`, `verified` on disk, plus transient `session`. | TEST VERIFIED. Vector retrieval UNPROVEN. |
| Proof | Evidence that a result happened and was independently checked (Validator, Proof Keeper, ledger receipts). | Specialist proof and token ledger TEST VERIFIED. Not linked to the backend's signed ledger (UNPROVEN). |

## 1. The two loops

Loop A (system): Intent → Plan → Execute → Observe → Learn → Prove → Reuse.
Loop B (token): Think → Act → Observe → Learn → Connect → Reconfigure.

| Step | Where it exists | Status |
|---|---|---|
| Intent | goal submitted over WebSocket / CLI | LIVE VERIFIED |
| Plan | planner context assembled in `runAgentGoal`; specialist selection by `selectSpecialists` | TEST VERIFIED |
| Execute | tool loop in `agent.ts` with approval gate | LIVE VERIFIED (real Mercury-2 runs) |
| Observe | tool results become `thoughts`; the cube maps them to stages | LIVE VERIFIED |
| Learn | token extraction after a successful run (`think-token-extract.ts`, #288 factory) | TEST VERIFIED; quality UNPROVEN |
| Prove | specialist validation + Proof Keeper; token ledger receipts | TEST VERIFIED (specialist path); the plain-run path has no independent validator |
| Reuse | top-3 accepted tokens injected into the planner context | TEST VERIFIED (mock model); `think_token_uses` is empty in the real database, so real reuse is UNPROVEN |
| Connect | `ThinkTokenPropagator` broadcasts #288 tokens to "similar workers" in one process | TEST VERIFIED (single process); link table CONCEPT |
| Reconfigure | no mechanism changes a stored token after creation except score updates and status changes | CONCEPT |

## 2. The 100-cell token and the existing reducer

The reducer is `apps/web/public/js/think-cube-state.js` (pure, no DOM), rendered by `think-cube-render.js`, tested by `apps/web/tests/think-cube-state.test.ts` (21 tests) and exercised against the real server in `docs/screenshots/think-token-dashboard-live/live-check-results.json` (cube sequence `intent>execution>challenge>execution>evidence>harvest>proof>think_token`, 54 active / 31 locked / 1 disrupted cells). Status: CODE COMPLETE, TEST VERIFIED, LIVE VERIFIED (as a run visualization).

**Layout as built.** 100 cells, `CELL_COUNT = 100`. Cell `i` has `face = i % 6` and `role = ROLES[i % 10]`, so each of 10 roles owns exactly 10 cells (a test asserts this) and the six "faces" are index buckets with no system-part meaning. Each cell carries `active`, `locked`, `disrupted`, `shared`, `value`.

| Role (10 cells each) | Lit by stage | Driven by (live) | Founder region it corresponds to |
|---|---|---|---|
| identity | `intent` | `goal` thought | intent |
| jobState | `decompose` | none (demo only) | worker / job |
| thinkBox | `swarm` | `specialist_wave_started` | worker |
| propagation | `execution` (progressive by step) | `tool_call` | action |
| evidence | `evidence` (locks) | successful `tool_result` | evidence |
| validation | `challenge` (disrupts), `jury` | failed `tool_result`; `specialist_validation` | evidence / proof |
| memory | `proof` (locks) | `proof_accepted`, or a `think_token` thought | memory |
| outcome | `proof` (locks) | same | outcome |
| tokenState | `think_token` (locks) | `think_token` thought | learning |
| relationship | `harvest`, `commons` (shared) | `memory` "Saved episode…" drives `harvest`; `commons` has no signal | relation |

The founder's nine regions (worker, intent, action, memory, relation, learning, evidence, proof, outcome) map onto the ten built roles as shown; "proof" has no cells of its own and is expressed through locked memory/outcome cells plus the `jury` verdict. This mapping is a proposal for P2, not an implemented meaning.

**Decision:** keep the reducer and its 100 cells as the single cube model. P2 may re-derive `face` from the token's system part, but must do so inside this reducer and keep its determinism and purity (same input events → byte-identical state; no mutation).

**Open question (founder):** an earlier proposal described the cube as six faces equal to six system parts (Dashboard, Agent runtime, Tools & plugins, Local models, Memory, Security gate) with 54 concept squares. The built cube is 100 cells over 10 roles. The two are not the same design; P2 must choose one before building (see Known gaps, item 11).

## 3. Permanent IDs: `TT-000001`

- Format: `TT-` plus a six-digit zero-padded decimal (`TT-000001`); widens past 999999 without changing the prefix.
- Allocation: a SQLite `INTEGER PRIMARY KEY AUTOINCREMENT` sequence (or a dedicated `think_token_seq` row) incremented inside the insert transaction, so concurrent writers cannot collide and a rolled-back insert cannot hand out a duplicate. `AUTOINCREMENT` guarantees a number is never reused after the row is deleted.
- Never reused: retiring, rejecting or deleting a token never frees its number.
- Duplicates: the same content hash returns the **existing** `TT-` ID and bumps its score inputs; it never mints a second ID.
- Migration from today's IDs: keep the existing `tt_<hash16>` value as an indexed `legacy_id` column; assign `TT-000001…` to existing rows in `created_at` order (today: 2 rows); update `think_token_uses` and `think_token_ledger` references in the same transaction; add a ledger entry recording the mapping. A rollback path must exist (ADR 028's `migrateDown` pattern).
- Shown everywhere: cube card and tooltip, token list, ledger receipt, WebSocket events (`token_id`), the creating run, planner citations (`[tt:TT-000042]`), CLI. Search and jump accept `TT-42` and `TT-000042`.
- Status: CONCEPT. Today IDs are hash-derived (`think-token-store.ts`, `const id = \`tt_${hash.slice(0, 16)}\``).

## 4. Lifecycle

Target states: `candidate → extracted → scored → challenged → accepted | rejected`, then used and reconfigured.

| Today (ADR 028, `think-token-store.ts`) | Target | Notes |
|---|---|---|
| `candidate` (CHECK constraint allows `candidate`, `accepted`, `retired`) | `candidate` | A token proposed from a proven run. |
| (extraction happens before the write; no stored state) | `extracted` | Text produced from the run's actual tool calls and outcome. |
| (score computed on write by `computeScore`) | `scored` | Store the breakdown (components and weights) next to the score. |
| (none) | `challenged` | A second pass critiques the token (true? specific? supported by the run's evidence?) and stores a verdict and reason. Generic template lessons are rejected here. |
| `accepted` (founder action) | `accepted` | Only after the challenge passes; founder promotion stays available. |
| `retired` (founder action) | `rejected` (failed challenge) and `retired` (founder removed) | Keep both; they mean different things. |

- **Model routing (target):** extraction, scoring and challenge call Mercury 2 using the key from the environment variable `INCEPTION_API_KEY_2` (read only from the existing `.env` loading path), falling back to local `qwen2.5:1.5b` when the key is missing or the call fails. Which model handled each step is recorded on the token row and in the ledger. The key is never logged, stored or put in an event; a test must fail if it appears in logs, database rows, events or evidence files. Prompts leave the machine, so secrets and paths are redacted and inputs size-capped before sending, with a per-run and per-day call cap. Status: CONCEPT.
- **Memory tiers and truth:** tokens are advisory text in their own table. They do not become `verified` memory, and no code path promotes a token into `org` or `verified` memory today. Any future path must require evidence and a human action, matching the existing `org → verified` rule (`memory.ts`). A token is never "true"; it is "supported by run X, checked by Y".
- Status of the lifecycle as designed: CONCEPT. The `candidate`/`accepted`/`retired` subset is TEST VERIFIED. Extraction is currently a deterministic template (`think-token-extract.ts`); an optional local rewrite exists but is not exercised against a real Ollama.

**Extractor accuracy requirement.** A lesson must be derived from the run's recorded tool calls and outcome. A test must fail if a lesson cites a tool the run never called. The challenge step must reject generic template lessons ("Ground X in evidence" style). Reference case: run ab5e5299 called `list_files`, `recall`, `fetch_url` ×2 and `write_file`; the stored lesson is accurate about `fetch_url` but carries no reusable insight (see the findings doc, "Correction recorded").

## 5. Disruption Token (CONCEPT)

Not built. The only runtime analog is the cube's `challenge` stage, which marks validation cells disrupted when a real tool call fails and never changes a stored token.

Proposed event (stored in SQLite and ledgered like any write):

```json
{
  "disruption_id": "DT-000001",
  "source": "run:ab5e5299-… | tool:fetch_url | founder | connector:<name>",
  "type": "new_info | error | opportunity | new_connection | decision_change",
  "affected_token_ids": ["TT-000007"],
  "delta": { "field": "score | status | content_hash | link", "from": "…", "to": "…", "reason": "…" },
  "evidence_ref": "run:<run_id> | receipt:<id>",
  "created_at": 1790873865734
}
```

Rules: a disruption never edits a token silently. It either (a) changes score inputs or status through the normal admission gate with a ledger receipt, or (b) creates a *new* candidate token linked to the old one and leaves the old one intact. `affected_token_ids` must exist; an event naming unknown tokens is rejected and no row is written. Size limits and a closed schema apply, as for ADR 028's WebSocket actions.

## 6. Long-range connections (CONCEPT; one partial precedent)

Precedent: `ThinkTokenPropagator` (`think-token-propagation.ts`) shares #288 tokens with similar workers inside one process. TEST VERIFIED there; no stored relationships, no weights, no depth control.

Proposed table `think_token_links`:

| Column | Meaning |
|---|---|
| `id` | integer key |
| `src_token_id` | `TT-…` |
| `dst_kind` | `token`, `worker`, or `outcome` |
| `dst_id` | a `TT-…`, a worker/job id, or a run/outcome id |
| `kind` | `supports`, `contradicts`, `refines`, `derived_from`, `used_by` |
| `weight` | 0–1, set by an explicit rule, never by an opaque model |
| `evidence_ref`, `created_at`, `updated_at` | provenance |

Propagation rules (all bounded): depth cap 3 hops; weight multiplied by 0.5 per hop (decay); a visited-set per propagation so cycles terminate; a per-event cap on touched rows; every propagated change goes through the admission gate and is ledgered. Token↔worker and token↔outcome links are written only from real run records.

## 7. Energy Core (CONCEPT)

Intended meaning: a live indicator built only from real signals. Candidate metrics, each tied to an existing source:

| Metric | Source | Exists today? |
|---|---|---|
| Active jobs | `RunStatus === 'running'` in `runs.ts`, exposed as `running` by `/api/stats` | LIVE VERIFIED (field exists) |
| Workers in use | specialist allocations from `specialist_wave_started` | TEST VERIFIED |
| Events per second | count of WebSocket `thought` messages over a window | not exposed |
| Recent proofs | `proof_accepted` / `proof_refused` thoughts | emitted; not aggregated |

The Energy Core must show nothing that is not measured: no animation on a timer, no simulated "propagation". `docs/roadmap.md:322` ticks the Energy Core as "documented and implemented"; only the documentation is true today.

## 8. Layer separation

| Layer | Responsibility | Not responsible for |
|---|---|---|
| Think Box | Governance and orchestration: admission, approval, ledger, proof gating. | Executing arbitrary capabilities. |
| MCP | Capability discovery (`mcp-registry.ts`, 10 tests). No execution bridge exists, so MCP is UNPROVEN as a capability. | Authorization. |
| Workers | Execution units (in-process sessions and specialist allocations). | Deciding what is true. |
| Substrate (Upstash Box / local) | Where code runs. Local is real; Upstash Box is UNPROVEN (ADR 024). | Governance. |
| Memory | Continuity (task, org, verified; vector not live). | Proof. |
| Proof | Trust: independent validation plus ledger receipts. | Storage of lessons. |

Separation from other things named "token": **Think Token** (this ADR) is a learning unit. **THNK** is a separate economic-token concept (`docs/strategy/THINK_TOKEN_STRATEGY.md`) and shares no code, table or UI with it. **HERMES** is an agent profile whose tools are `algorand` (read-only chain queries), `recall` and `remember` (`agent.ts:252`); it writes nothing to a chain, but `remember` does write memory behind the evidence gate, so "read-only" applies to the chain only.

## 9. CLI and dashboard parity

Requirement: the `kudbee` CLI and the dashboard (127.0.0.1) read the **same** store through **one** shared module, with no duplicated queries or formatting.

- Today: the CLI has no Think Token commands; only `server.ts` reads `think-tokens.db`. The 🎫 Learning view is in-memory and session-only; the 🧩 Tokens view is persisted. A user can therefore see different things in the two places. Status of parity: UNPROVEN (absent).
- Target: one reader module (working name `think-token-reader.ts`) used by the WebSocket handler, any REST route and the CLI (`kudbee tokens list`, `kudbee tokens show <id>`). It formats the ID, title, lesson text, status, score with breakdown, `run_id` and ledger receipt once.
- Acceptance: a parity test runs one real goal via the CLI, fetches the dashboard API for that `run_id`, and asserts the fields are identical; the "Captured N Think Token(s)" count equals what the dashboard shows for that run. The two token views are merged into one Think Tokens view inside the dashboard.

## 10. Guardrails

- A token is advisory text and carries no field that grants a permission, tool or approval (ADR 027 default deny; ADR 028).
- Every write goes through the admission gate and produces a ledger receipt (ADR 028; TEST VERIFIED).
- SQLite only (ADR 026). No Postgres, Neon or Vercel. No Algorand writes. Dashboard bound to 127.0.0.1 with Host/Origin gating unchanged.
- The Mercury 2 key is read from the environment and never logged, stored or emitted.
- No event is emitted without a database row behind it, and no UI element is driven by a timer or a demo event in the normal path.
- THNK stays separate; HERMES's tool allowlist is unchanged.

## Known gaps

| # | Gap | Evidence | Status |
|---|---|---|---|
| 1 | The lifecycle states `extracted`, `scored`, `challenged`, `rejected` do not exist; the store has `candidate`/`accepted`/`retired`. | `think-token-store.ts` CHECK constraint | CONCEPT |
| 2 | The ADR 028 pipeline is wired into `runAgentGoal`, but the lifecycle is not a first-class part of `AgentSession`; the #288 and ADR 028 paths run side by side. | `server.ts` (`saveThinkTokens`, `recordGoalExecution`) | CODE COMPLETE, divergent |
| 3 | Disruption Tokens do not exist. | §5 | CONCEPT |
| 4 | No distributed swarm; specialists run in one process. | findings #6 | UNPROVEN |
| 5 | MCP discovery is not an execution bridge. | findings #3 | UNPROVEN |
| 6 | Vector memory is not live. | findings #5 | UNPROVEN |
| 7 | The dashboard is local-only by design. | `server.ts` loopback gating | by design |
| 8 | Plain-run goal thoughts carry no `run_id`; the token card shows a status message instead of the learned text. | findings, "Other things found" | LIVE VERIFIED defect |
| 9 | Lessons are generic templates; reuse has never happened (`think_token_uses` is empty). | findings #9 | UNPROVEN |
| 10 | IDs are `tt_<hash>`, not permanent `TT-` numbers; scores have no stored breakdown. | §3, §4 | CONCEPT |
| 11 | The cube's faces carry no system-part meaning; the six-face/54-square proposal conflicts with the built 100-cell/10-role design. | §2 | open founder decision |
| 12 | No CLI token commands; two token views disagree in scope. | §9 | UNPROVEN |
| 13 | The `think-cube-state.js` header comment is stale about `harvest`; `docs/roadmap.md:322` overstates the Energy Core. | findings, "Other things found" | doc defect |

## Phases

Each phase ships as one PR, runs all tests locally before one push, and includes an `EVIDENCE.md` with a claims ledger (claim, reproduction command, expected vs actual, evidence, state), real-run proof for any LIVE claim (no mocks, seeds or timers count), a challenge pass that tries to break every claim, and a "What could be fake" section. No PR text may exceed what `EVIDENCE.md` proves.

| Phase | Scope | Acceptance tests | Evidence required |
|---|---|---|---|
| **P1** Lifecycle + permanent IDs | States in §4 through `AgentSession`; `TT-000001` IDs with migration; extractor derived from actual tool calls; stored score breakdown; Mercury 2 (`INCEPTION_API_KEY_2`) with local fallback and per-step model record; challenge step; plain-run `run_id` and real token text on the card; one merged Think Tokens view; shared reader plus `kudbee tokens list/show`. | ID allocator monotonic, no reuse after delete or reject, safe under concurrent allocation; illegal transitions rejected; a lesson citing a tool the run never called fails; a generic template lesson is rejected by the challenge; model fallback with a mocked missing/erroring Mercury; the key never appears in logs, rows, events or evidence; dedupe returns the existing ID; end-to-end: a real local run produces `TT-xxxxxx` with `run_id` and evidence links; CLI/dashboard parity test; existing reducer tests unchanged. | Real runs with run ids, minted `TT-` IDs, SQLite `SELECT` output, ledger receipts, the model per step, CLI output beside dashboard JSON for the same token; red-team: ID reuse, forged `run_id`, oversized or malformed payload, missing key. |
| **P2** Live cube view + Energy Core | Cube derived from stored tokens (§2 decision on faces/regions); Energy Core from the §7 real metrics; used/learned events with schema and size limits; reduced-motion behavior; persisted counts labeled apart from session counts. | Cube state is a pure function of token rows; no event without a row; forged or oversized event rejected; Energy Core shows zero when idle. | Screenshots at 1440, 1024 and 390 px from a real run; console errors listed. |
| **P3** Long-range connections | `think_token_links` (§6) with depth cap, decay and cycle protection. | Cycle terminates; depth cap enforced; decay arithmetic; link to unknown token rejected; rows only from real run records. | Real run that creates links; SQL output; ledger receipts. |
| **P4** Disruption Tokens | Event schema (§5) and reconfiguration through the admission gate. | Unknown token ids rejected; a disruption never mutates silently; reconfiguration is ledgered; replay determinism. | A real disruption from a real tool failure or new input, with before/after rows. |
| **P5** Multi-worker propagation, vector memory, Upstash Box | Only after P1–P4 have evidence and the founder approves a substrate decision. | Defined at that point. | Real multi-worker run; real vector index; real Box execution. Until then all UNPROVEN. |

## Consequences

- Positive: one source of truth for tokens; the dashboard and CLI cannot disagree; claims are tied to evidence; the cube becomes a view of real data.
- Cost: an ID and state migration on `think-tokens.db`; a model dependency (Mercury 2) for extraction and challenge, with prompts leaving the machine; more tables and tests.
- Risk: learning quality may stay poor even with a correct pipeline. P1's challenge step and the extractor test are there to make that visible rather than hidden.

## Related

ADR 024, ADR 026, ADR 027, ADR 028; PRs #288, #303, #306, #311; `docs/research/2026-10-01-think-box-findings.md`; `AGENTS.md` §1.3a; `docs/strategy/THINK_TOKEN_STRATEGY.md` (THNK, separate).
