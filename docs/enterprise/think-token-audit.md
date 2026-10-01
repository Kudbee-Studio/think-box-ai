# Think Token / THNK / DTHINK audit

Status: evidence-only audit, 2026-09-30. Nothing was changed, minted, provisioned or contacted to produce it. Every
claim below was read from a file or a git object in this repository.

Labels follow AGENTS.md section 4.4: IMPLEMENTED (code exists), TEST VERIFIED (a test exercises it), LIVE VERIFIED
(observed working against a real environment), UNPROVEN, PLANNED (only a document), BLOCKED (needs an input that does
not exist). "Think Token" is used for at least five unrelated things in this repository. They are kept apart here.

| Class | What it is | Where |
|-------|-----------|-------|
| **A** | KUDBEE operational Think Tokens: units of learned reasoning inside the dashboard | `apps/web/think-token*.ts` (#288) |
| **B** | THNK economic token, and the simulated agent economy | `think_box_ai/token.py`, `thinkbox/economy.py`, `THINK_TOKEN_STRATEGY.md` |
| **B2** | DTHINK, a design-only idea | `docs/DTHINK_DESIGN.md` on an unmerged branch only |
| **C** | Future decentralized or network settlement layer | `docs/savanna-solana-plan.md`, `core/solana/` |
| **D** | Governance and admission tokens | `thinkbox/governance_token.py`, `thinkbox/admission.py` |
| **E** | Orchestrator pipeline labels `token_<uuid>` | `experiments/kudbee_orchestrator.py` |

None of these A to E share code, a data store, or a type. No file links A to B, B to C, or any of them to D.

---

## A. KUDBEE operational Think Tokens (#288)

**EVIDENCE**
- Types and collections: `apps/web/think-token.ts` (169 lines). Minting helper: `apps/web/think-token-factory.ts` (295).
  Propagation to workers: `apps/web/think-token-propagation.ts` (234).
- Persistence: `apps/web/learning-store.ts` (305 lines) opens `apps/web/learning.db` with three tables,
  `learned_patterns`, `session_learning`, `thought_artifacts`. SQLite, file next to the source.
- Wiring: `server-learning-integration.ts` imports `worker-initialization.ts`, which imports `learning-integration.ts`.
  A grep of `server.ts` and `agent.ts` for `ThinkToken`, `LearningManager` and the integration classes finds nothing.
  `grep` for importers of `worker-initialization` and `server-learning-integration` outside those files finds nothing.
  So the chain has no caller in the running server.
- Tests: none on this branch. The `origin/fix/web-typecheck-288-debt` branch (PR #300) adds
  `apps/web/tests/server-learning-integration.test.ts` (3 tests) and types the store and extractor; it is unmerged.
- The dashboard Learning panel is simulated client-side (earlier finding, `apps/web/public/js/app.js`).

**CLASSIFICATION**
- Code for minting, storing and propagating units: IMPLEMENTED.
- Unit-level behaviour: TEST VERIFIED only on #300's branch (unmerged); nothing on main.
- Used by a live agent run: UNPROVEN. No caller exists, so no run can have produced a persisted token.
- Effect on agent prompts (the point of the feature): PLANNED. Wiring changes prompts, so it is a founder decision.
- "Minting" here means constructing an object. There is no supply, owner, signature or cost.

**NEXT ACTION** (none started): founder decides D-token-wiring in `roadmap.md`; if yes, one PR that calls
`server-learning-integration` from the session end path, with a test that a finished run leaves rows in `learning.db`.

## B. THNK economic token

**EVIDENCE**
- `think_box_ai/token.py` (36 lines): `SYMBOL="THNK"`, `DECIMALS=18`, `TOTAL_SUPPLY=1_000_000_000`, class `ThinkToken`
  with `balance` and `transfer`. Balance is a Python int on the instance. Test: `tests/test_token.py`.
  Only importer outside tests: `think_box_ai/__init__.py` re-exports `SYMBOL`.
- `thinkbox/economy.py` (202 lines): `AgentTokenEconomy`, `ContributionMining`, `StakingMechanism`, `SlashConditions`,
  `TreasuryGovernance`. No `sqlite`, file or network use in the module (`json` is imported and never called).
  Tests: `tests/unit/test_economy.py`, plus three cases in `tests/unit/test_session_tracker.py` and one in
  `tests/unit/test_swarm_instrumentation.py`. No production caller imports it.
- Plan document: `THINK_TOKEN_STRATEGY.md` (repo root; a banner says it concerns THNK, not #288). It says the token
  "exists in `think_box_ai/token.py` as a basic balance/transfer class" and lists utility ideas (stake for tools,
  research rewards). Those are proposals.

**CLASSIFICATION**
- `ThinkToken` and `AgentTokenEconomy` in memory: IMPLEMENTED and TEST VERIFIED (unit tests, no I/O).
- Persistence: none. Every balance is lost at process exit. Not IMPLEMENTED.
- Supply enforcement, issuance, wallets, on-chain existence: none in this code. UNPROVEN as an asset; the 1,000,000,000
  figure is a constant, not a ledger.
- Utility plan (staking for access, rewards): PLANNED.

**NEXT ACTION**: nothing to build. Do not describe the economy as a simulation of a live system or as a running
economy; say "in-memory, no persistence, no production caller".

## B2. DTHINK

**EVIDENCE**
- The only design text is `docs/DTHINK_DESIGN.md`, present only in commit 46a9233b on
  `origin/agent/dashboard-command-center/kilo-20260916`. It opens "Status: Proposed / Not implemented" and has sections
  Summary, Motivation, Relationship to THINK, Non-Goals, Requirements, Architecture, Lifecycle, Security and Abuse,
  Migration and Interop, Open Questions, Milestones.
- The word "DTHINK" does not appear in any tracked source, test or config on this branch. (Matches in
  `public/control-plane/receipts.html` are the substring inside `loadThinkJobs`, not the name.)

**CLASSIFICATION**: PLANNED (document, unmerged). No code. Not TEST VERIFIED, not LIVE VERIFIED.

**NEXT ACTION**: none until the design is reviewed. Do not merge that branch on the strength of this audit.

## C. Decentralized or network settlement layer

**EVIDENCE**
- `core/solana/__init__.py`, `agents.py`, `protocols.py`: a wrapper that shells out to the `solana` and SPL token CLI
  through `subprocess.run` (binary from `SOLANA_CLI_PATH`). It has create-token, mint, burn, transfer and balance
  methods. `think_box_ai/commands/solana.py` exposes it. `docs/savanna-solana-plan.md` is the plan.
- No record exists of a token mint address, a devnet or mainnet transaction, or a wallet that holds THNK.
- Nothing connects `think_box_ai/token.py` to these methods.

**CLASSIFICATION**: CLI wrapper IMPLEMENTED; any on-chain THNK UNPROVEN; settlement layer for DTHINK PLANNED.
Not LIVE VERIFIED: no transaction evidence.

**NEXT ACTION**: none. Anything on-chain needs a founder decision, a named network and a signing-key plan first.

## D. Governance and admission tokens (different thing)

`thinkbox/governance_token.py` (115 lines) and `thinkbox/admission.py` (86) issue permission-style tokens for
agents. They are authorization artifacts, not currency, and have no relation to A to C. IMPLEMENTED; unit tests exist
in `tests/unit/test_governance_token.py` and `tests/unit/test_admission.py` (not re-run for this audit).

## E. Orchestrator pipeline: Jury, Challenge, Proof, Token

**EVIDENCE**
- `experiments/kudbee_orchestrator.py` docstring: "Intent → Decompose → Burst → Execute → Evidence → Jury → Challenge →
  Retry → Proof → Token → Harvest → Commons → Repeat". Methods `_jury_evaluate`, `_adversarial_challenge` exist.
- The Token stage returns `{"minted": True, "token_id": f"token_{uuid.uuid4().hex[:16]}", ...}`. The id is a random
  string. Nothing is stored, signed, or sent anywhere, and the reason text is fixed.
- The constructor defaults `mock_vllm=True`.
- The only other reference to these methods is `experiments/test_interrupt_resume.py`; no test under `tests/` names the
  orchestrator file.
- `core/multi_agent.py` defines a `JURY` role; `think_box_ai/cli.py` and `scripts/validate_jobs.py` accept `jury` as a
  job "hat". A checkpoint `data/checkpoints/interrupt_test/interrupt_test_job_jury.json` is a test fixture.
- There is no class, function or file named "ExecutionChallenge"; "execution challenge" as a token-earning mechanism
  does not exist in code.

**CLASSIFICATION**: pipeline stages IMPLEMENTED in an experiment script; against the mock model TEST VERIFIED only to
the extent `test_interrupt_resume.py` runs it (not re-run for this audit); "minted token" is a label, not a token.
Real-model runs: UNPROVEN. Link to A or B: none.

**NEXT ACTION**: rename the output field in a later PR so "minted" stops implying a token (low priority, needs a test).

---

## Persistence, proof artifacts, and Neon

| Question | Answer from the repository |
|----------|---------------------------|
| Is any Think Token (A or B) durable across restarts? | A: only if something calls `LearningStore`, and nothing does. B: no. |
| Are there proof artifacts that a token was issued? | Orchestrator `proof` metadata goes to `ledger.append` (a governance ledger), keyed by task id, not by token. No artifact ties an issued token to a holder. |
| Does anything need Postgres/Neon? | No. ADR 028 (Proposed) keeps SQLite and lists the criteria that would reopen Neon. Not reversed here. |
| Was Neon provisioned for this? | No. ADR 026 reverted it; nothing was created in this audit. |

## Rubik's cube design

BLOCKED. No file, commit, branch, issue or code in this repository contains a Rubik's cube specification. It is not
inferred or implemented here; it needs the founder's spec.

---

## Architecture provable today

```
A  KUDBEE operational Think Tokens (dashboard learning units)
   apps/web/think-token.ts  think-token-factory.ts  think-token-propagation.ts
   apps/web/learning-store.ts -> apps/web/learning.db (SQLite)
   wiring: server-learning-integration.ts -> worker-initialization.ts -> learning-integration.ts
   IMPLEMENTED; TEST VERIFIED only on unmerged #300; LIVE: no caller, UNPROVEN

B  THNK in-memory token and agent economy
   think_box_ai/token.py, thinkbox/economy.py
   IMPLEMENTED + TEST VERIFIED (unit, in-memory); no persistence, no production caller

B2 DTHINK
   docs/DTHINK_DESIGN.md (unmerged branch, commit 46a9233b)   PLANNED

C  Settlement layer
   core/solana/*, think_box_ai/commands/solana.py (CLI wrapper), docs/savanna-solana-plan.md
   wrapper IMPLEMENTED; on-chain THNK UNPROVEN; no link to B

D  Governance tokens   thinkbox/governance_token.py, admission.py   IMPLEMENTED (not currency)
E  Orchestrator token_<uuid> labels   experiments/kudbee_orchestrator.py   label only
```

Bottom line: a Think Token in the sense of #288 is a locally persisted learning record that no running code creates
yet. THNK is an in-memory balance class and a separate in-memory economy. DTHINK is a draft document. No link between
A, B and C exists in code, and nothing on-chain is proven.

Related: `docs/decisions/028-think-token-persistence.md`, `docs/enterprise/gap-analysis.md`, `docs/enterprise/roadmap.md`.
