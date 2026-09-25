## Draft — GitHub PR #213 Trait Lab local environment prep (not merged)

- **Branch:** `cursor/memory-trait-lab-local-env-prep-25-723f`
- **Gate:** `memory-trait-lab-local-env-prep-25`
- **Scope:** E01–E25 local Python/SQLite prep, redact, workflow dry-run, prep receipt
- **Write policy:** Hash-only except prep receipt persist; no pack/run apply; refuses live ack; `live_verified: false`
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** prep file **8 OK**; memory suite pending full run — **not merged**
- **AGENTS.md:** GitHub #202–#213 Trait Lab / memory lane rows added; §4.3 standing rule **Always update MD** (this draft)

## GitHub PR #212 — Trait Lab catalog pin bind workflow (merged)

- **Merge:** `581fab3` — W01–W25 hermetic plan/dry-run/run/receipt
- **Gate:** `memory-trait-lab-catalog-pin-bind-workflow-25`
- **Scope:** Signed plan, dry-run skips writes, run pins/drops unbound, persist receipt
- **Write policy:** Hash-only except pin_catalog, drop_unbound, and receipt persist; no pack/run apply; live claim fail-closed
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** workflow file **10 OK**; memory suite **196 OK**; engine harden **61 OK** (257 combined)

## GitHub PR #211 — Trait Lab catalog pin bind lane (merged)

- **Merge:** `e416bd7` — D01–D25 bind filters, compose, rematch index, drop unbound
- **Gate:** `memory-trait-lab-catalog-pin-bind-ops-25`
- **Scope:** Bind filters, compose (merge/intersect/subtract/xor/retain), rematch index, drop unbound, catalogs from bound
- **Write policy:** Hash-only except drop_unbound (unpin facts only); no pack/run apply; live claim, same index, bind conflict, missing pin fail-closed
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** bind-ops file **10 OK**; memory suite **186 OK**; engine harden **61 OK** (247 combined)

## GitHub PR #210 — Trait Lab catalog↔pin bind (merged)

- **Merge:** `2846d02` — B01–B25 rematch pins against store packs
- **Gate:** `memory-trait-lab-catalog-pin-bind-25`
- **Scope:** Rematch pin pack hashes; bound/unbound reports; pin retain/xor/merge; catalog_from_pin
- **Write policy:** Hash-only except pin/import writes of pin facts; no pack/run apply; live claim, unbound pin, and missing pin fail-closed
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** bind file **13 OK**; memory suite **176 OK**; engine harden **61 OK** (237 combined)

## GitHub PR #209 — Trait Lab catalog follow-through (merged)

- **Merge:** `415acb0` — xor + retain-best on rematched pack catalogs
- **Gate:** `memory-trait-lab-catalog-follow`
- **Scope:** Symmetric diff + retain-best after catalog compose (parity with #208 pin follow-through)
- **Write policy:** Hash-only; no pack/run writes; live claim, empty retain, invalid keep, and same catalog fail-closed
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** catalog-follow file **4 OK**; memory suite **163 OK**; engine harden **61 OK** (224 combined)

## GitHub PR #208 — Trait Lab catalog pin follow-through (merged)

- **Merge:** `eb622d5` — xor + retain-best + fact_id/id-set harden
- **Gate:** `memory-trait-lab-catalog-pin-follow`
- **Scope:** Symmetric diff + retain-best after pin compose
- **Write policy:** Hash-only; no pin/pack/run writes; live claim, empty retain, invalid keep, and pin conflict fail-closed
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** follow file **5 OK**; memory suite **159 OK**; engine harden **61 OK** (220 combined)

## GitHub PR #207 — Trait Lab catalog pin compose (merged)

- **Merge:** `8a120d2` — merge / intersect / subtract rematched pin indexes
- **Gate:** `memory-trait-lab-catalog-pin-compose`
- **Scope:** Compose two rematched pin-index snapshots
- **Write policy:** Hash-only compose; no pin/pack/run writes; same index, live claim, pin conflict, and invalid index fail-closed
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** pin-compose file **6 OK**; memory suite **154 OK**; engine harden **61 OK** (215 combined)

## GitHub PR #206 — Trait Lab catalog pin operators (merged)

- **Merge:** `50211b4` — P01–P25 pin-index operators
- **Gate:** `memory-trait-lab-catalog-pin-ops-25`
- **Scope:** Filter, page, export/verify/import, digest/etag, pack membership
- **Write policy:** Pin facts only; import does not apply packs or runs; live claims fail-closed
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** pin-ops file **14 OK**; memory suite **148 OK**; engine harden **61 OK** (209 combined)

## GitHub PR #205 — Trait Lab catalog pin (merged)

- **Merge:** `8367f5a` — pin / get / list / unpin rematched catalog snapshots
- **Gate:** `memory-trait-lab-catalog-pin`
- **Scope:** Persist a rematched catalog hash as `verified:trait-lab-catalog-{sha[:16]}`
- **Write policy:** Pin fact only; unpin does not delete pack facts or run rows; live claim, missing pin, and missing provenance fail-closed
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** pin file **5 OK**; memory suite **134 OK**; engine harden **61 OK** (195 combined)

## GitHub PR #204 — Trait Lab catalog compose (merged)

- **Merge:** `388fde8` — merge / intersect / subtract rematched catalogs
- **Gate:** `memory-trait-lab-catalog-compose`
- **Scope:** Compose two rematched catalog snapshots
- **Write policy:** Hash-only compose; no run writes; same catalog, live claim, pack conflict, and invalid catalog fail-closed
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** compose file **6 OK**; memory suite **129 OK**; engine harden **61 OK** (190 combined)

## GitHub PR #203 — Trait Lab catalog operator pack (merged)

- **Merge:** `595dbb5` — C01–C25 seed-pack catalog operators
- **Gate:** `memory-trait-lab-catalog-ops-25`
- **Scope:** Filter, page, purge, export/verify/import index, digest/etag
- **Write policy:** Catalog facts only; purge does not delete run rows; live claims fail-closed
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** memory suite **123 OK**; engine harden **61 OK** (184 combined)

## PR #224 — Trait Lab seed pack catalog (merged)

- **Merge:** `5db0c37` — catalog imported/applied packs by `pack_sha256`
- **Gate:** `memory-trait-lab-seed-pack-catalog`
- **Scope:** Catalog imported/applied packs by `pack_sha256` without executing them
- **Write policy:** Apply now writes the same pack fact as import; malformed pack rows are skipped; invalid limit and missing hash fail-closed
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** memory suite **99 OK**; engine harden **61 OK** (160 combined)

## PR #223 — Trait Lab seed pack diff (merged)

- **Merge:** `29e4ff9` — compare two rematched packs for one seed
- **Gate:** `memory-trait-lab-seed-pack-diff`
- **Scope:** Compare two rematched packs for one seed
- **Write policy:** Rematch both packs; seed mismatch, same pack, live claim, and invalid pack fail-closed
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** memory + trait-lab suites → **95 OK** (156 with engine harden)

## PR #222 — Trait Lab seed pack apply (merged)

- **Merge:** `2cfa121` — write rematched pack runs into a destination store
- **Gate:** `memory-trait-lab-seed-pack-apply`
- **Scope:** Write rematched pack runs into a destination store
- **Write policy:** Rematch first; live claim, invalid run, missing run, and missing provenance fail-closed
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** memory + trait-lab suites → **92 OK** (153 with engine harden)

## PR #221 — Trait Lab seed pack import (merged)

- **Merge:** `a05b31d` — rematch seed pack SHA and write a verified import fact
- **Gate:** `memory-trait-lab-seed-pack-import`
- **Scope:** Verify `pack_sha256` and write a verified import fact
- **Write policy:** Live claim, invalid pack, missing hash, rematch fail, and missing provenance fail-closed
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** memory + trait-lab suites → **89 OK** (150 with engine harden)

## PR #220 — Trait Lab seed pack export (merged)

- **Merge:** `d66cc4a` — portable snapshot of stored runs for one seed
- **Gate:** `memory-trait-lab-seed-pack`
- **Scope:** Portable snapshot of stored runs for one seed
- **Write policy:** Missing seed fail-closed; pack is not a live ranking
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** memory + trait-lab suites → **86 OK**

## PR #219 — Trait Lab seed XP band (merged)

- **Merge:** `e0d400c` — seed history rows between a stored XP floor and ceiling
- **Gate:** `memory-trait-lab-seed-xp-band`
- **Scope:** Seed history rows between a stored XP floor and ceiling
- **Write policy:** Missing seed/band match and inverted/invalid bounds fail-closed; not a live ranking
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** memory + trait-lab suites → **83 OK**

## PR #218 — Trait Lab seed XP ceiling (merged)

- **Merge:** `528ac80` — seed history rows at or below a stored XP threshold
- **Gate:** `memory-trait-lab-seed-xp-ceiling`
- **Scope:** Seed history rows at or below a stored XP threshold
- **Write policy:** Missing seed/ceiling match and invalid ceiling fail-closed; not a live ranking
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** memory + trait-lab suites → **80 OK**

## PR #217 — Trait Lab seed XP floor (merged)

- **Merge:** `50c5a9d` — seed history rows at or above a stored XP threshold
- **Gate:** `memory-trait-lab-seed-xp-floor`
- **Scope:** Seed history rows at or above a stored XP threshold
- **Write policy:** Missing seed/floor match and invalid floor fail-closed; not a live ranking
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** memory + trait-lab suites → **77 OK**

## PR #216 — Trait Lab seed daily filter (merged)

- **Merge:** `f99af45` — seed history rows filtered by daily-seed flag
- **Gate:** `memory-trait-lab-seed-daily`
- **Scope:** Seed history rows filtered by daily-seed flag
- **Write policy:** Missing seed/daily match and invalid daily fail-closed; not a live ranking
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** memory + trait-lab suites → **74 OK**

## PR #215 — Trait Lab seed operator filter (merged)

- **Merge:** `88d9c45` — seed history rows filtered by operator name
- **Gate:** `memory-trait-lab-seed-operator`
- **Scope:** Seed history rows filtered by operator name
- **Write policy:** Missing seed/operator and invalid operator fail-closed; not a live ranking
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** memory + trait-lab suites → **71 OK**

## PR #214 — Trait Lab seed difficulty filter (merged)

- **Merge:** `77eb188` — seed history rows filtered by difficulty tier
- **Gate:** `memory-trait-lab-seed-difficulty`
- **Scope:** Seed history rows filtered by difficulty tier
- **Write policy:** Missing seed/difficulty and invalid difficulty fail-closed; not a live ranking
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** memory + trait-lab suites → **68 OK**

## PR #213 — Trait Lab seed grade filter (merged)

- **Merge:** `690979c` — seed history rows filtered by letter grade
- **Gate:** `memory-trait-lab-seed-grade`
- **Scope:** Seed history rows filtered by letter grade
- **Write policy:** Missing seed/grade and invalid grade fail-closed; not a live ranking
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** memory + trait-lab suites → **65 OK**

## PR #212 — Trait Lab seed index (merged)

- **Merge:** `413c28a` — seeds with stored runs: count + best XP
- **Gate:** `memory-trait-lab-seed-index`
- **Scope:** Seeds with stored runs: count + best XP
- **Write policy:** Empty index is empty; invalid limit fail-closed; not a live ranking
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** memory + trait-lab suites → **62 OK**

## PR #211 — Trait Lab seed history (merged)

- **Merge:** `8536fa4` — all stored runs for one seed, highest XP first
- **Gate:** `memory-trait-lab-seed-history`
- **Scope:** All stored runs for one seed, highest XP first
- **Write policy:** Missing seed fail-closed; not a live ranking
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** memory + trait-lab suites → **58 OK**

## PR #210 — Trait Lab best per seed (merged)

- **Merge:** `7b0e0df` — highest stored XP per seed
- **Gate:** `memory-trait-lab-best-seed`
- **Scope:** Highest stored XP per seed
- **Write policy:** Missing seed fail-closed; not a live ranking
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** memory + trait-lab ledger/replay/compare/board/best-seed suites → **55 OK**

## PR #209 — Trait Lab local board (merged)

- **Merge:** `abdf325` — local board from stored proofs
- **Gate:** `memory-trait-lab-board`
- **Scope:** Local `rank_board` over stored Trait Lab proofs
- **Write policy:** Not a live ranking; `live_verified` false
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** memory + trait-lab ledger/replay/compare/board suites → **51 OK**

## PR #208 — Trait Lab run compare (merged)

- **Merge:** `b9074c6` — list/compare stored Trait Lab proofs
- **Gate:** `memory-trait-lab-compare`
- **Scope:** List stored Trait Lab proofs; compare two hashes
- **Write policy:** Same-run and missing proofs fail closed; not a live ranking
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** memory + trait-lab ledger/replay/compare suites → **47 OK**

## PR #207 — Trait Lab replay verify (merged)

- **Merge:** `d989255` — replay rematch against stored proof
- **Gate:** `memory-trait-lab-replay`
- **Scope:** Store `encode_replay` and verify it matches `proof_sha256`
- **Write policy:** Replay must rematch the stored proof; live claims rejected
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** memory + trait-lab ledger + replay suites → **42 OK**

## PR #206 — Trait Lab memory ledger (merged)

- **Merge:** `1c8294f` — Trait Lab proof → four layers
- **Gate:** `memory-trait-lab-ledger`
- **Scope:** Bind Trait Lab proofs into four layers with provenance
- **Write policy:** Requires agent_id + task_id + proof_sha256; rejects live claims
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** `python3 -m unittest tests.unit.test_memory_layers tests.unit.test_memory_layers_query tests.unit.test_memory_layers_version tests.unit.test_memory_trait_lab -v` → **37 OK**

## PR #205 — Organizational versioning + snapshot (merged)

- **Merge:** `01f46c6` — versioned org history + portable snapshot
- **Gate:** `memory-org-version`
- **Scope:** Versioned org history; portable four-layer export/import
- **Write policy:** Org append-only + versioned; import rejects live claims
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** `python3 -m unittest tests.unit.test_memory_layers tests.unit.test_memory_layers_query tests.unit.test_memory_layers_version -v` → **32 OK**

## PR #204 — Memory query + retention (merged)

- **Merge:** `0b3fc87` — read / query / decay / retention
- **Gate:** `memory-query-retention`
- **Scope:** Read / query / end-session / end-task / decay / retention on the four layers
- **Write policy:** Org append-only; verified decays (no delete); session/task may expire
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** `python3 -m unittest tests.unit.test_memory_layers tests.unit.test_memory_layers_query -v` → **24 OK**

## PR #203 — Memory layers ingest (merged)

- **Merge:** `3976930` — four-layer ingest + fail-closed deepen
- **Gate:** `memory-layers`
- **Scope:** Session / Task / Organizational / Verified Knowledge writes via `MemoryStore`
- **Write policy:** Session rejects transient UI; org needs evidence; verified needs how + fact + confidence `[0,1]`; contradictions require `corrects`
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** `python3 -m unittest tests.unit.test_memory_layers -v` → **16 OK**

## PR #202 — Trait Lab (merged)

- **Merge:** `75a36c5` — seeded game U01–U50 + harden
- **Four-state cap:** TEST VERIFIED only — not LIVE VERIFIED

## PR #201 — Upstash Box access verification (draft)

- **Gate:** `upstash-box-access-verification`
- **This-run class:** A `ENV_NOT_CONFIGURED` (`UPSTASH_PUBLIC_BOX_URL` / `UPSTASH_PUBLIC_BOX_TOKEN` absent)
- **Four-state cap:** TEST VERIFIED only — `live_verified: false`
- **Verify:** `python3 scripts/verify_kilo_pr201_upstash_box_access.py`

## KILO spine — post-#170 era (2026-09-24)

- **#170 merged:** beyond-KILO lint (`scripts/verify_kilo_beyond_kilo_lint.py`)
- **#171 merged:** `docs/roadmaps/kilo-post-170-pr-roadmap.md`
- **#172 merged:** PR CI trusts fast `scripts/verify_kilo_spine.py` + explicit lint execute (H31)
- **#173 merged:** chronicle honesty — README + AGENTS/CONTINUITY/runbook sync
- **#174 merged:** lint scope wave 1 — 25 modules + enterprise editing commitments
- **#175 merged:** lint scope wave 2 — 38 modules (`beyond_kilo_lint` v3)
- **Four-state cap:** TEST VERIFIED for hermetic work; `live_verified: false` on spine audits until founder Live proof

---

## PR #125 — Audit ledger (draft)

- **Artifacts:** `docs/audit/` (index, pass `passes/2026-09-22-pr125.json`, checklists, checked areas)
- **CLI:** `python3 scripts/audit_ledger.py list|mark-checked|stale`
- **Canonical health:** `docs/STATUS.md` + `docs/CONTINUITY.md`
- **Test gate (2026-09-22):** `python3 -m unittest discover tests/` → **2235 OK**, 8 skipped, 3 expected failures

---

## CNC Manufacturing Intelligence Platform

**Status:** Complete

### Module Structure

- `thinkbox/cnc/job.py` — CNCJob, Material, Tool, MachineProfile, Operation, ValidationResult, InspectionResult, ApprovalRecord, ExecutionRecord
- `thinkbox/cnc/memory.py` — ManufacturingMemory, KnowledgeEntry
- `thinkbox/cnc/proof.py` — ProofPackage, ProofStore
- `thinkbox/cnc/adapter.py` — CADInterface, MachineControllerInterface, InspectionSystemInterface, SimulatorInterface, ShopDatabaseInterface, CNCAdapterRegistry
- `thinkbox/cnc/safety.py` — SafetyGate, ApprovalGate, SafetyGateStore
- `thinkbox/cnc/tenant.py` — Tenant, TenantPermission, TenantBoundary, TenantStore
- `thinkbox/cnc/dashboard.py` — ROIStats, ROIDashboard
- `thinkbox/cnc/demo.py` — DemoMode, DemoResult
- `thinkbox/cnc/engine.py` — CNCManufacturingEngine
- `thinkbox/cnc/__init__.py` — All exports

### CLI Integration

- `think_box_ai/commands/cnc.py` — CNC CLI commands (job, demo, memory, proof, safety, tenant, replay, dashboard, engine)
- `think_box_ai/cli.py` — CNC subcommand registered

### Backend Integration

- `backend/api/v1/router.py` — CNC endpoints (POST /cnc/job, POST /cnc/demo, GET /cnc/dashboard, POST /cnc/safety/approve, GET /cnc/tenant)

### Tests

- `tests/unit/test_cnc.py` — 68 tests
- Full suite: see PR #125 gate above (`docs/STATUS.md` for module breakdown)

## Experiment + Learning Dashboard

**Status:** Complete

### Module Structure

- `thinkbox/experiment.py` — `ExperimentRecord`, `ExperimentManager`, `ExperimentDB`, `AgentSessionRecord`, `ParameterProvenance`, `ParameterClassification`, `ExperimentStatus`, `FourState`, `ProvenanceSource`, `get_experiment_manager`
- `tests/unit/test_experiment.py` — 45 tests covering all experiment features

### Key Features

- **Persistent Experiment Records**: Every agent run becomes a tracked experiment with durable session ID, inputs, execution evidence, outputs, tests, outcome, and learned parameters
- **SQLite Persistence**: Zero-dollar, stdlib-only persistence layer with migrations for `experiments`, `experiment_parameters`, `experiment_events`, `artifacts`, `proof_records`, `outcomes`, `lessons`, `agent_sessions`
- **Parameter Provenance**: Every parameter carries `value`, `unit`, `source`, `confidence`, `classification` (OBSERVED/ESTIMATED/SIMULATED), `session_id`, `timestamp`
- **Learning Loop**: Intent → Hypothesis → Parameters → Plan → Execute → Test → Artifact → Proof → Outcome → Learn → Updated Parameters → Next Experiment
- **Four-State Classification**: CODE_COMPLETE, TEST_VERIFIED, LIVE_VERIFIED, PRODUCTION_READY
- **Session Continuity**: Parent/child session relationships, start/end state, last completed action, blockers, next larger improvement
- **Zero-Server Execution**: Complete lifecycle works without Docker, Kubernetes, SSH, cloud server, or external database
- **Dashboard Aggregation**: Dashboard data generated from persisted SQLite data, not manually maintained status text
- **Restart/Recovery**: Full recovery from SQLite after restart
- **Corrupted/Missing Artifact Handling**: Graceful handling of missing or corrupted artifacts

### Backend Integration

- `backend/api/v1/router.py` — Experiment endpoints: POST /experiment, GET /experiment/{id}, POST /experiment/{id}/parameter, POST /experiment/{id}/outcome, GET /experiment/dashboard, POST /experiment/zero-server, GET /experiment/restart

### Tests

- `tests/unit/test_experiment.py` — 46 tests (incl. learning-loop provenance round-trip)
- `tests/unit/test_cnc.py` — 44 tests (UpCloud control-plane config: no stale defaults, explicit-server)
- `tests/unit/test_providers.py` — 10 tests (openai_compat incl. Mercury-2 endpoint contract, mocked)
- `tests/unit/test_swarm_instrumentation.py` — incl. `TestPipelineDashboard` 4 tests + `TestPopulationArena` 26 tests + `TestDagVerifiedExecution` 9 tests (v1 + v2 families/taxonomy + v3 retry + default-path session + engine wrapper + DAG-level verified execution)
- `tests/unit/test_concurrent_goals.py` — 40 tests (concurrent execution, budget isolation, shared-budget exhaustion, cross-goal accounting, retry accounting, fan-out/fan-in telemetry, restart/persist, dashboard block, no-secrets, adaptive retry backoff, resource profiling, error classification)
- Full suite: **1605 tests, 6 skipped, 3 expected failures**

### Multi-Goal Concurrent Budgets + Deeper DAG Telemetry (2026-09-17) — COMPLETE (live 4 calls)

- **Architecture decision (concurrency model):** `ThinkBoxEngine.execute_goal` reads the injected verified runner from a mutable instance attribute (`_verified_task_runner`), so concurrent goals sharing one base engine would race. Each concurrent goal therefore gets its OWN fresh `GovernedEngine` (own base `ThinkBoxEngine`, own in-memory ledger, own event stream). The ONLY shared object is the optional global `VerifiedRetrySession`, whose counter mutations (`_spend_call`, `retries_fired`, `conversions`) are synchronous (no `await` between read-modify-write), so asyncio serializes them correctly — this makes shared-budget accounting mathematically correct, NOT merely concurrent.
- **Integration point:** new `thinkbox/concurrent_goals.py` (`ConcurrentGoalsRunner`, `ConcurrentGoalSpec`, `ConcurrentGoalsConfig`, `ConcurrentGoalsResult`, `aggregate_layer_telemetry`); reuses `GovernedEngine.execute_verified_goal` (now accepts `session=`), `VerifiedRetrySession`, `VerifiedRetryConfig`, `BudgetExhausted`. `ThinkBoxEngine.execute_goal` emits `summary["layers_telemetry"]`; dashboard `_pipeline()` gained a `concurrent` block (extended DAG view, no new dashboard).
- **Budget model:** independent goals (default) = per-goal `VerifiedRetrySession` (strict isolation); shared/global = one shared session enforcing a global cap via atomic `_spend_call` (honest `BudgetExhausted`). Cross-goal accounting: per-goal calls counted by wrapping each goal's `complete_async`; per-goal retries from `verified["retries"]`; global = deterministic sum cross-checked against the shared session's `calls_spent`.
- **Live proof (fresh instances):** 2 concurrent goals via REAL Mercury-2 (`experiments/concurrent_goals_live.py`): goal A `compute/add_small` (1 task) + goal B fan-in DAG `[compute/mul_small, compute/sub_neg] → multifield/double` (3 tasks). 4 live calls (hard guard 8): all FIRST_TRY_SUCCESS, 0 retries, 0 failures, 0 budget-exhausted. Cross-goal accounting exact: global 4 = 1+3; per-goal remaining 1 each. Layer telemetry: layer 0 = 3 tasks (fan-out), layer 1 = 1 task (fan-in). Memory `learn:concurrent:multi-goal-budgets`.
- **Restart / dashboard:** `scope="concurrent"` control record persisted via `ExperimentManager` (per-goal accounting + layer telemetry + goal_results JSON); fresh `ExperimentDB` + `_pipeline()` reconstruct the run from SQLite alone. File ledger (6 entries) `verify()` True.
- **Fix (found during audit):** `_persist_verified_goal` wrote proof to fixed per-day filename `dagpath_proof_{date}.json` → concurrent goals clobbered each other + the historical DAG proof. Fixed to `dagpath_proof_{goal_experiment_id}.json`; runner `persist` proof unique per run; historical clobbered artifacts restored from git.
- **Integrity:** proof `data/thinkboxmd/artifacts/concurrent_goals_live_proof_20260917.json` SHA256 `0d740895…489a`; runner proof `concurrent_proof_tb_exp_20260917214737_b61798e2.json`; secrets scan clean.
- **Evidence:** FourState CONCURRENT_VERIFIED (CODE_COMPLETE / TEST_VERIFIED 664 / LIVE_VERIFIED substrate / MODEL_EXECUTION_VERIFIED 4 live calls; PRODUCTION not claimed)

### Budget Contention Policies + Per-Goal Limit Enforcement (2026-09-18) — COMPLETE

- **Problem:** Goals with budget limit ≤ 0 were running, causing the shared session to spend calls before hitting `BudgetExhausted` (wasted calls, incorrect accounting).
- **Solution:** Early budget check — goals with limit ≤ 0 are now skipped BEFORE execution (return `BUDGET_EXHAUSTED` immediately); defense-in-depth check retained in `_counted_complete`.
- **BudgetContentionPolicy implementations verified:**
  - `FAIR_SHARE`: equal budget shares per goal
  - `PRIORITY`: higher priority goals consume budget first (high-priority gets budget, lower skipped)
  - `FIFO`: submission order allocation
- **Integration point:** `thinkbox/concurrent_goals.py` (`ConcurrentGoalsRunner._run_one`): early budget check before `execute_verified_goal`; defense-in-depth in `_counted_complete`.
- **Test updates:** `test_shared_global_budget_exhaustion` uses FIFO policy; `test_concurrent_persist_reconstructs_accounting` expects correct call count (2, was 4).
- **Suite:** 663 OK (6 skipped).
- **Evidence:** FourState CONTENTION_VERIFIED (CODE_COMPLETE / TEST_VERIFIED 663 / LIVE_VERIFIED substrate / CONTENTION_VERIFIED; PRODUCTION not claimed)


### DAG-Level Verified Execution (2026-09-17) — COMPLETE

- **Boot anomaly (recovered):** workspace re-materialization wiped the gitignored dbs (`data/thinkboxmd/db/experiments.db`, `ledger.db`; `memory.db` absent) → 3 pipeline tests failed (0 experiments). Git-tracked artifacts (93) survived. Classified ENVIRONMENT data loss (not code regression). Rebuilt experiments.db + memory.db from artifacts via `experiments/recover_pipeline_db.py` — every restored row provenance-marked (`agent_id=recovery-20260917`, `source=recovered-from-artifacts`); only artifact-attested fields; ledger hash chain NOT reconstructable (left empty, documented limitation). Recovery → 640 OK.
- **FIRST TRACE:** `execute_goal` → `TaskDecomposer.decompose` → `TaskGraph` → `get_execution_order()` layers → per-node `_execute_task` → swarm. Smallest integration point = per-node branch in `_execute_task`.
- **Integration point:** (1) `ThinkBoxEngine.set_verified_task_runner(runner)` — dependency injection, engine never imports governance/retry code; (2) `execute_goal(goal, graph=None)` — nodes with `metadata["verification"]` route through the runner, all others keep the legacy swarm path; (3) `GovernedEngine.execute_verified_goal` — builds graph, assigns stable task/session/experiment ids per task, injects a runner delegating to canonical `execute_verified_task` (shared bounded `VerifiedRetrySession` across the DAG), aggregates child outcomes into `summary["verified"]`, persists via existing ExperimentManager/ledger/proof. NOT a second execution wrapper.
- **Compatibility:** verify=None / no runner → legacy path untouched (asserted); retry only retryable taxonomies; arithmetic/inconsistency never auto-retry; BudgetExhausted honest terminal; recovered task retains first-failure taxonomy + trace; parent aggregation hides neither failures nor recoveries.
- **Live proof (fresh instances):** 1 four-task DAG (compute/add_carry, distractor/wrongkey, multifield/double → layer 2 distractor/apology) via REAL Mercury-2 / Inception path; session `tb_sess_20260917201625_18e6`, goal `tb_exp_20260917201625_000f7c27`. 5 live calls (budget 10, remaining 5): 3 FIRST_TRY_SUCCESS + 1 RECOVERED_SUCCESS (distractor/wrongkey naturally failed distractor-compliance → valid, 2 attempts, converted). 0 failures, 0 budget-exhausted, verification_rate 1.0. No manufactured failures, no inflated sample. Memory `learn:dagpath:verified-goal`.
- **Restart / dashboard:** fresh process reconstructed goal + 4 tasks + params + outcomes from SQLite; recovered task kept original taxonomy→final→trace. `_pipeline()` rebuilt DAG totals from storage (tasks 4 / first-try 3 / recovered 1 / failures 0 / retries 1 / rate 1.0); HTTP `/api/pipeline` served the dag block; HTML DAG card present.
- **Integrity:** ledger `verify()` True (admission + per-task + DAG_COMPLETE entries carry session/experiment ids); proof `dagpath_proof_20260917.json` SHA256 `5d254c1d…52dac97e` recomputed-match; 4 task-artifact SHA256 match; no secrets in pipeline/ledger/proof/artifacts.
- **Evidence:** `data/thinkboxmd/artifacts/dagpath_proof_20260917.json` + 4 `dagpath_*_tb_exp_*.json`; FourState DAG_VERIFIED (CODE_COMPLETE / TEST_VERIFIED 649 / LIVE_VERIFIED / MODEL_EXECUTION_VERIFIED; PRODUCTION not claimed)

### Engine Promotion: Verified Execution in GovernedEngine (2026-09-17) — COMPLETE

- **Integration point:** `GovernedEngine.execute_verified_task` — thin async wrapper delegating to `VerifiedRetrySession.run_async` (no logic duplicated); `ThinkBoxEngine.execute_goal` untouched; Arena stays benchmark consumer
- **Compatibility:** verify=None → legacy single attempt with status UNVERIFIED; arithmetic/inconsistency never auto-retry; BudgetExhausted fails honestly; first-failure taxonomy preserved in trace
- **Live proof (fresh instances):** 6 engine-path jobs (compute×2, distractor×3, multifield×1) via Mercury-2/Box: 5 FIRST_TRY_SUCCESS + 1 RECOVERED_SUCCESS (`enginepath_distractor_wrongkey`: distractor-compliance → valid, 2 attempts); 7 calls, 0 failed; ledger verified; memory `learn:enginepath:verified-wrapper`
- **Telemetry:** execution_status persisted per job as experiment parameter; dashboard jobs table shows Exec status column; restart reload 6/6 telemetry + replay 6/6
- **Evidence:** `data/thinkboxmd/artifacts/enginepath_proof_20260917.json` (SHA256 `118de71b…8dc419b6`, 7 files secrets-clean); FourState ENGINE_PROMOTED

### Default-Path Generalization (2026-09-17) — COMPLETE (IMPROVED mechanism at scale)

- **Mechanism:** `VerifiedRetrySession` + config/result/budget in `thinkbox/pop_arena.py` (sync-pure, injected complete/verify/reprompt; bounded retries; per-call traces; session call budget with `BudgetExhausted`)
- **Live proof:** 8 jobs across compute/distractor(6)/multifield (budget 16, spent 9): 8/8 valid, 1 retry → 1 conversion (distractor-compliance → valid, 2 attempts); memory + dashboard recorded
- **Classification:** IMPROVED — orchestration level, NOT model intelligence; small-n honestly bounded
- **Evidence:** `data/thinkboxmd/artifacts/defaultpath_proof_20260917.json` (SHA256 `5a0e0c16…94cfa3c74`, 9 files secrets-clean); FourState ARENA_VERIFIED

### Arena v3 Verifier-Side Retry (2026-09-17) — COMPLETE (IMPROVED at mechanism level)

- **Mechanism:** `should_retry` gate (retryable taxonomies only, max 1) + `retry_prompt_for` (names failure, no answer leak) + `resolve_retry` trace — in `thinkbox/pop_arena.py`, deterministically tested
- **Run:** control `tb_exp_20260917182126_3cf9f861`; 12 live distractor (6 baseline + 6 retry-arm) via existing Mercury-2 path
- **Result:** baseline 5/6 (reproduced `{"result": 37}`); retry arm 6/6 final-valid with 1/1 conversion (distractor-compliance → valid, 2 attempts, 716 tokens)
- **Classification:** IMPROVED — mechanism level only (orchestration, NOT model intelligence); small-n, honestly bounded
- **Restart:** fresh handles reload control + lesson + ledger verified
- **Evidence:** `data/thinkboxmd/artifacts/arena3_proof_20260917.json` (SHA256 `b1aadd34…09ceaca8`, 13 files secrets-clean); FourState ARENA_VERIFIED

### Arena v2 Transfer-Under-Difficulty (2026-09-17) — COMPLETE (honest negative transfer)

- **Families:** compute (6 variants) + distractor (6) + multifield (6); `verify_v2` taxonomy (parse-fail/wrong-key/arithmetic/distractor-compliance/inconsistency/valid); replay emissions verify by construction
- **Control:** `tb_exp_20260917181211_b78ceb62` with pre-registered hypothesis + Wilson-CI threshold (delta > 0.15, non-overlapping CI)
- **Population:** 300/300 (264 replay + 36 live: 18 baseline + 18 learned REAL Mercury-2)
- **Results:** baseline 17/18 (CI [0.742, 0.99]) vs learned 17/18 (same CI); identical `{"result": 37}` wrongkey failure both arms — lesson `learn:arena2:failures` retrieved 18/18 but fix INEFFECTIVE
- **Classification:** NO_MEASURABLE_IMPROVEMENT (delta 0.0, threshold NOT met; ceiling broken at 0.944 but no transfer)
- **Restart:** fresh handles reload control + 300 rows + lesson + ledger verified
- **Evidence:** `data/thinkboxmd/artifacts/arena2_proof_20260917.json` (SHA256 `413e05ad…65cea9c9`, 37 files secrets-clean); FourState ARENA_VERIFIED

### Experiment Arena Control Surface (2026-09-17) — COMPLETE

- **Decision:** `thinkbox/pop_arena.py` canonical for the population layer (ExperimentManager owns jobs, ChallengeArena owns probes; pop_arena owns population + budget + classification, delegating all writes; one defensive dedupe fix)
- **State:** NOT_RUN→CONFIGURED→RUNNING→COMPLETE, control `tb_exp_20260917175431_3c4cf0e1`, all transitions + Chronicle lessons persisted
- **Population:** 300/300 (150 baseline + 150 learned); live 12/12 REAL Mercury-2 (6+6, 1/variant/arm, 12/12 VALID, retrieval 6/6); replay 288/288 (deterministic, never model calls)
- **Honesty repairs:** 12 false-live flags corrected, 11+1 placeholders superseded, 12 double outcomes deduped, 1 orphaned call re-run — all recorded
- **Metrics:** verified 300/300, errors/retries 0, latency live 0.6–51.5s, tokens live 101–299; no invented score. Classification: NO_MEASURABLE_IMPROVEMENT (ceiling 1.0)
- **Dashboard:** `/api/pipeline` arena block + Population Arena card, restart-proof
- **Evidence:** `data/thinkboxmd/artifacts/arena_proof_20260917.json` (SHA256 `82a29a84…60a0e2c`, secrets-clean); FourState ARENA_VERIFIED

### KUDBEE Dashboard — Learning Pipeline View (2026-09-17)

- **Existing dashboard only** (`experiments/swarm_dashboard.py`; no parallel system): new `_pipeline()` reader (read-only SQLite across experiments/outcomes/proofs/artifacts/lessons/events/params + memory.db + ledger verify) at `/api/pipeline` + Pipeline HTML tab (KPIs, jobs table, lessons/retrieval/memory/blockers)
- **Restart-proof:** pipeline rebuilds from storage after singleton reset (tested); served live from fresh module load over HTTP (200 on `/api/pipeline` + `/healthz`)
- **Live state shown:** 6 experiments / 6 outcomes / 4 proofs / 9 artifacts / 6 lessons / 3 memory keys / ledger verified; 3 Mercury-2 jobs VALID; lesson `learn:exact-json:directive`; 2 retrieval events; CODE/TEST/LIVE/MODEL verified, ARENA NOT_RUN
- **Blockers shown:** SSH-to-UpCloud unsupported; `record_outcome` status stays pending

### End-to-End Learning Think Job (2026-09-17)

- **Path (existing only):** ExperimentManager lessons/events + MemoryStore provenance + ActionLedger + ExperimentStore/SelfImprovementLoop; no competing architecture; no EvidenceDrivenLearningEngine/OutcomeClassifier classes in repo (vocabulary used as plain classification)
- **Baseline:** job `tb_exp_20260917170533_fbb1ec84` — exact-JSON answer=7, live Mercury-2 VALID, 0.39s, 98 tokens, artifact `6cc76885…bd0f5`
- **Lesson:** row id 5 + memory `learn:exact-json:directive` (conf 0.9, task=baseline; known/unknown recorded)
- **Learned:** job `tb_exp_20260917170605_a1ae355e` — same family answer=9, lesson retrieved (event + param + ledger provenance), live Mercury-2 VALID, 0.433s, 91 tokens, artifact `814b63e0…150f2`
- **Compare:** True/True, 0 retries, reuse proven, latency 0.39/0.433, tokens 98/91 — no invented score. Classification: NO_MEASURABLE_IMPROVEMENT (ceiling at 1.0; valid, model NOT smarter)
- **Restart/replay:** both experiments + lessons + memory + hashes + ledger reload OK; property replay True/True
- **Evidence:** `data/thinkboxmd/artifacts/learn_loop_proof_20260917.json` (SHA256 `e05be996…22ffb7f90`, secrets-clean); FourState MODEL_EXECUTION_VERIFIED + TEST_VERIFIED

### Real Model-Backed Think Job (2026-09-17)

- **Path (existing, no new architecture):** `openai_compat` provider + `MercuryClient` contract (`api.inceptionlabs.ai/v1`, `mercury-2`, key from `INCEPTION_API_KEY` presence only)
- **Live call (ONE, bounded):** temp 0.2, max_tokens 3500, 60s timeout; response 14 chars → parsed `{"answer": 42}` → property VALID; 36/77/113 tokens, 0.774s latency
- **Job:** session `tb_sess_20260917165841_b7bdb508`, box `box_950e971d6d1b` (Vector persisted), job `tb_exp_20260917165842_4b92d477`, artifact SHA256 `e41e8f9e…caf8f6`, ledger verified, memory + proof + outcome TEST_VERIFIED + dashboard; executed from in-Box runtime via existing provider POST `{base}/chat/completions` — no SSH, no UpCloud compute, no GPU
- **Replay:** fresh-process reload + property re-validation True (byte-identical response explicitly NOT required)
- **Safety:** no keys/headers/env in artifacts; single call; honest FAILED path on invalid property
- **Evidence:** `data/thinkboxmd/artifacts/model_job_proof_20260917.json` (SHA256 `a4171cdc…356c12`); FourState MODEL_EXECUTION_VERIFIED (path proven, no intelligence claim)

### Upstash Box as Primary Execution Substrate (2026-09-17)

- **Contract (LIVE_VERIFIED):** precedence `UPSTASH_PUBLIC_BOX_URL` > `THINKBOX_UPCLOUD_API_TOKEN` > `CI` > `local`; live selection `wanted-tuna-71803-3000.preview.box.upstash.com`
- **Box job (TEST_VERIFIED):** session `tb_sess_20260917164614_26d2aca3`, box `box_62f30c9d3adc` (Vector snapshot persisted), job `tb_exp_20260917164615_32b3ee9c`, artifact SHA256 `8bac2b52…57662550`, validation PASS, ledger verified, memory + outcome + dashboard recorded; executed in-Box (Firecracker runtime, Box env) — no remote-exec API exists so no remote-dispatch claim
- **Restart/replay (TEST_VERIFIED):** fresh-process reload of box/session/job/artifact/hash/proof/memory/outcome all verified; replay identical `[1,2,3,4,5]`; dashboard reconstructed
- **Model readiness:** BOX EXECUTION VERIFIED; MODEL EXECUTION VERIFIED 2026-09-17 (single bounded Mercury-2 call via existing openai_compat path: `{"answer": 42}` property VALID, 0.774s; job `tb_exp_20260917165842_4b92d477`; proof `model_job_proof_20260917.json`)
- **Classification:** UpCloud = infrastructure/control-plane ONLY; Upstash Box = current execution substrate; SSH-to-UpCloud = unsupported/not required (`thinkbox/upcloud.py` defaults fixed, history preserved)
- **Evidence:** `data/thinkboxmd/artifacts/box_primary_proof_20260917.json` (SHA256 `972f2b6e3081db1b0e38e61c67c0553c2cdbfdd6f05978c697188259f1d725e3`)

### Live UpCloud Host Verification (2026-09-17)

- **API (LIVE_VERIFIED, read-only):** account `kudbee` (200); server `kudbeev3` (`0046a589-81a2-4c0b-aacd-8e6f678c7c41`, CLOUDNATIVE-16xCPU-48GB, us-chi1, started, 16 cores, 49152MB, 209.50.56.169 + 209.50.53.93, 50GB virtio, firewall off) via `https://api.upcloud.com/1.3` Bearer auth (`/v1`→404, `/1.6`→400)
- **SSH (BLOCKED at auth layer):** port 22 open on .169 (banner OpenSSH_10.2p1 Ubuntu-2ubuntu3.6), timeout on .93; historical recovered keypair consistent but NOT authorized (Permission denied publickey); configured key path file absent; no SSH adapter class in codebase; UpCloudConfig defaults stale (kudbee-host-v1/212.147.250.183)
- **Reconciliation:** same-machine NOT_PROVEN (no shell); GPU absence inferred from CPU-only plan, unmeasured
- **Substrate:** current run substrate is Upstash Box; smallest wiring point is `core/providers/upcloud.py` read-only execute → `UpCloudConfig` (API-sourced IP/UUID) → `substrate.bind_think_box` live-server branch (not built)
- **Evidence:** experiment `tb_exp_20260917162855_5eb93b1c`, artifact `data/thinkboxmd/artifacts/upcloud_host_verify_20260917.json` (SHA256 `400f4cc92b300a0553cdc9448d89c4cc7f22157985805af9c36fa9737e7bd20d`); FourState TEST_VERIFIED with LIVE_VERIFIED API inventory, SSH proof FAILED (blocker)

### UpCloud Runtime State Diagnostic (2026-09-17)

- **Server IS running:** API `/1.3/server/<uuid>` → state `started`, host 8388362883, boot_order=disk, firewall off; user report of stopped server contradicted by live API + open port 22 on 209.50.56.169 (209.50.53.93 secondary IP times out — normal)
- **Separate statuses:** API reachable ✅ / server running ✅ / port 22 (.169) ✅ / port 22 (.93) ❌ / SSH key available ❌ / SSH auth successful ❌
- **Substrate boundary:** execution substrate = Upstash Box preview; UpCloud control plane = reachable (GET-only); UpCloud server execution path = NOT WIRED (provider is control-plane REST only; stale defaults; no SSH adapter; no bind_think_box live branch); UpCloud GPU execution path = NOT PRESENT (CPU-only server, 68 GPU plans in catalog unassigned)
- **Evidence:** experiment `tb_exp_20260917164001_073516d8`, artifact `data/thinkboxmd/artifacts/upcloud_runtime_state_20260917.json` (SHA256 `e333faa4d1886d102d808ec3fffc4a1deef3a6af9eb02ee95226c1d10d711ff8`); zero mutation; FourState LIVE_VERIFIED for control-plane state only, machine NOT reached
- **Blocker:** no authorized SSH key on kudbeev3 (single BatchMode attempt denied publickey)

### CLI Integration

- `think_box_ai/cli.py` — Experiment subcommand registered

## Phase 9 — Zero-to-One Innovations

**Status:** Complete (55 innovations across 13 categories)

### Phase 9 Modules

| Module | Category | Features |
|--------|----------|----------|
| `thinkbox/session.py` | Foundation | SessionContext, generate_session_id, create/get/clear_session, UpstashVectorSync |
| `thinkbox/coalition.py` | COAL (1–5) | CRDT shared memory, task bidding market, pub/sub bus, capability registry, governance voting |
| `thinkbox/consensus.py` | CONS (11–15) | Multi-model voting, Bayesian confidence scoring, disagreement resolution, model ranking, audit trail |
| `thinkbox/economy.py` | ECON (16–20) | Token economy, contribution mining, staking mechanism, slash conditions, treasury governance |
| `thinkbox/intelligence.py` | INTEL (36–40, 51–55) | Knowledge graph, self-healing, reputation, federated learning, post-quantum security |
| `thinkbox/benchmark.py` | BENCH (26–30) | Concurrency scaling sweeps (16–512 workers), system metrics, markdown report generation |

### Phase 9 Bug Fixes

| Bug | File | Fix |
|-----|------|-----|
| Missing treasury account | `thinkbox/economy.py` | Added treasury existence check in `AgentTokenEconomy.transfer()` |
| `_threshold` attribute | `thinkbox/consensus.py` | Added validation in `DisagreementResolver.__init__` |

### Test Count

**137 tests** (Phase 1/2 security, Phase 5 features, integration tests, Phase 9 session tracker)

## How to Run Tests

```bash
python3 -m unittest discover tests/
python3 -m unittest tests.unit.test_session_tracker
python3 -m unittest tests.unit.test_phase1_2_security
python3 -m unittest tests.unit.test_whip_protocol
python3 -m unittest tests.integration.test_e2e_engine
```

## Verified Tool Count: 18

| # | Tool | Status |
|---|------|--------|
| 1 | file_read | ✅ |
| 2 | file_write | ✅ |
| 3 | shell_exec | ✅ |
| 4 | http_request | ✅ |
| 5 | memory_query | ✅ |
| 6 | fs_read | ✅ |
| 7 | fs_write | ✅ |
| 8 | fs_list | ✅ |
| 9 | http_get | ✅ |
| 10 | memory_put | ✅ |
| 11 | memory_get | ✅ |
| 12 | memory_search | ✅ |
| 13 | indexer_health | ✅ |
| 14 | doge_tx | ✅ |
| 15 | doginals_inscription | ✅ |
| 16 | compare_inscription | ✅ |
| 17 | parse_drc20 | ✅ |
| 18 | load_fixture | ✅ |

## Source Reachability (2026-08-31)

### Live (returned data)
- **api.doginals.org** — /v1/health OK; inscription endpoints 404 (not public)
- **api.github.com** — OK
- **example.com** — OK

### Blocked (TLS OK, app-layer block)
- **dogechain.info** — HTTP 403 (Cloudflare anti-bot challenge)

### Dead (network-level failure)
- **wonky-ordinals.fly.dev** — DNS resolution failure
- **ordinalswallet.com** — HTTP 522 (connection timeout)
- **api.inception.ai** — TLS alert 112 (CDN SNI reject from AWS IPs)

## Model Provider Status

| Provider | Box | Cloud Local | Notes |
|----------|-----|-------------|-------|
| Ollama | ❌ Not installed | ❌ Not installed | Install locally |
| Inception (Mercury 2) | ✅ **Working** | ✅ **Working** | `https://api.inceptionlabs.ai/v1`, model `mercury-2`. Verified 2026-09-15: live completion, ~0.4–5 s. Reasoning model — give it ≥3500 `max_tokens` or reasoning tokens consume the budget and `content` comes back `null`. |
| OpenAI | ✅ Reachable | ✅ Reachable | Needs key |
| Groq | ✅ Reachable | ✅ Reachable | Needs key |

**Correction (2026-09-15):** earlier status listed Inception as TLS-blocked
(`api.inception.ai`, 525). The working host is **`api.inceptionlabs.ai`** and it
answers normally from the cloud sandbox. `think_box_ai/commands/inception.py`
still only *simulates* calls and does not use this endpoint.

---

## THINKBOXMD-RESEARCH — End-to-End Research Test (2026-09-15)

**Verdict:** 9 PASS / 2 PARTIAL / 0 FAIL.

Ran a real research workflow (`experiments/thinkboxmd_research.py`) with live
Mercury 2 model calls through the existing control fabric: Think Box creation,
five-worker swarm (PHARMA/TOX/VALIDATOR/SAFETY/SYNTH), tiered findings
(EVIDENCE/INFERENCE/HYPOTHESIS/UNVERIFIED), reconciliation, injected-failure
recovery, persistent memory, and hash-chain proof.

- Proof hash: `0723be5ea848a96fa85ad61c7ecf225139dff8efc6d527797fcb1f998c0bd6f5`
- Ledger: 12 entries, chain valid; traces: 9 grounded / 1 ungrounded
- PARTIAL layers: MEMORY (Upstash Vector broken), THINK INTEGRATION (token economy is simulated integers)

Full report: `docs/THINKBOXMD_REPORT.md`.

---

## Swarm Instrumentation Layer (2026-09-15)

**Verdict:** 11/11 checks pass (`python3 experiments/verify_instrumentation.py --live`).

Ten instruments added on SQLite (free, zero-config, always available):
flight recorder, challenge arena, TSSI + learning curve, memory evolution,
proof-carrying decisions, worker reputation, A/B experiments, self-improvement
loop, cost/intelligence efficiency, swarm genome/replay.

- Learning curve observed: **0.6405 → 0.7318 (+0.0913)** across two sessions
- Proof chain + genome both **verify**; tampering is detected
- Dashboard (mobile-first, stdlib, no build step) reads all of it read-only
- Found and fixed a real deadlock in `thinkbox/economy.py::transfer()`
  (`create_account()` called while holding a non-reentrant lock)

Modules: `thinkbox/{metrics,flightrecorder,arena,memory_evolution,reputation,experiments}.py`
Entrypoints: `experiments/{big_swarm,swarm_dashboard,verify_instrumentation,probe_mercury_throughput}.py`
Plan: `docs/DASHBOARD_BUILDOUT.md`

### Measured Mercury 2 throughput (single client, cloud sandbox)

| Concurrency | rps | p50 | errors |
|---|---|---|---|
| 1 | 2.67 | 0.36 s | 0 |
| 4 | 8.98 | 0.39 s | 0 |
| 16 | 17.21 | 0.81 s | 0 |
| 32 | 24.02 | 1.13 s | 0 |
| 64 | 23.67 | 2.01 s | 0 |

Ceiling ≈ **24 rps** from one client (client-bound, not server). 320 workers
complete in ~15 s.

---

## Access Inventory (2026-09-15)

| Service | Env present | Status |
|---------|-------------|--------|
| Inception Mercury 2 | `INCEPTION_API_KEY` | ✅ live and used |
| Upstash Vector | `UPSTASH_VECTOR_REST_URL/TOKEN` | ⚠️ reachable, writes require embedder env |
| Upstash Box | `UPSTASH_BOX_API_KEY`, `UPSTASH_PUBLIC_BOX_URL` | ❌ host reachable, preview `not found` |
| UpCloud `kudbee-host-v1` (212.147.250.183) | `THINKBOX_UPCLOUD_API_TOKEN` | ❌ token 401 invalid; no SSH key; IP behind Cloudflare 1003 |
| Redis | — | ❌ no client, no env |
| MCP | — | ❌ none configured |

**Known defect:** `thinkbox/session.py::UpstashVectorSync.upsert()` cannot write
to a dense index and swallows the error. See
`data/findings/thinkboxmd_upstash_vector_defect.md`.

### Upstash Vector Fix (require embedder env)

`UpstashVectorSync.upsert()` now requires a working embedder. To enable:

```bash
export THINKBOX_OPENAI_COMPAT_API_KEY=sk-your-key       # same key as completion
export THINKBOX_OPENAI_COMPAT_BASE_URL=https://api.inceptionlabs.ai/v1
export THINKBOX_EMBED_MODEL=mercury-2                    # optional, defaults to THINKBOX_DEFAULT_MODEL
```

Post to `{base_url}/embeddings` (OpenAI-compatible endpoint).
If the provider has no `/embeddings` route, set `THINKBOX_OPENAI_COMPAT_API_KEY` to empty
and pass a `DeterministicEmbedder` instance in tests only — never in production.

`DeterministicEmbedder` (hash-based, 1536-dim, stable) is available in `thinkbox/embedder.py`
strictly for unit tests.

---

## How to Run Locally


```bash
git checkout session/agent_79e656bf-37c6-46f2-833e-1eb027b99152
pip install -r backend/requirements.txt

# Option A: Local Ollama
ollama pull llama3.1:8b
python3 -m uvicorn backend.main:app --port 8000 &

# Option B: Groq (free tier)
export THINKBOX_DEFAULT_PROVIDER=openai_compat
export THINKBOX_OPENAI_COMPAT_API_KEY=gsk_your_key
export THINKBOX_OPENAI_COMPAT_BASE_URL=https://api.groq.com/openai/v1
export THINKBOX_DEFAULT_MODEL=llama-3.1-8b-instant
python3 -m uvicorn backend.main:app --port 8000 &

# Run proof
python3 scripts/prove_dogi.py
```

## DOGI Proof Result

**Status:** Partial — tools work, but inscription data inaccessible via public APIs.

See: `data/findings/dogi_indexer_split.md`

## FreeToken Integration

**Status:** Documented, not yet deployed.

See: `data/findings/freetoken_integration.md`

KudbeeZero fork: https://github.com/KudbeeZero/kudbee-freetoken (identical to upstream FlashML).

**Plan:** Run FreeToken on UpCloud GPU spot → point Think Box at its OpenAI-compatible API.

## Key Finding

The indexer-split thesis is **not provable via public APIs alone**. Most inscription
indexers don't expose public endpoints, require auth, or are unreachable. To prove
the thesis, we need a paid API, residential proxy, or local indexer.

## Frontend v1

Landing page, jobs listing, findings browser, job detail, about.
Design system with dark theme, responsive layout, animations.
Pure HTML/CSS/JS — no build step.

Serve: `python3 scripts/serve_frontend.py 8080`
PR: https://github.com/Kudbee-Studio/think-box-ai/pull/58

## Phase 12 — KUDBEE Control Fabric

**Status:** Complete (25 commits, branch `feat/phase12-kudbee-control-fabric`)

New modules in `thinkbox/`:
- `identity.py` — IdentityLedger, capability scopes, policy version
- `governance_token.py` — token issuance, verification, revocation
- `admission.py` — fail-closed AdmissionGate
- `workspace.py` — Think Box registry + SQLite store
- `handoff.py` — cross-substrate handoff with integrity hashing
- `occupancy.py` — OccupancyMonitor, MeshCellManager (horizontal isolation)
- `capacity.py` — elastic CapacityController
- `ledger.py` — append-only tamper-evident ActionLedger
- `thinktrace.py` — ThinkTraceCapture (grounded vs ungrounded)
- `governed.py` — admission-gated GovernedEngine

New tests: identity, token, admission, workspace, workspace store, handoff,
occupancy, mesh, capacity, ledger, thinktrace, governed + control-fabric E2E.

Test count: **266 tests passing**.

## Disruptor + Verifier Evaluation Harness

**Status:** Complete (branch `feat/disruptor-evaluation`)

New modules in `thinkbox/`:
- `disruptor.py` — `DisruptorPass`, `DisruptorSuite` (adversarial pass framework)
- `verifier.py` — `Verifier`, `EvalHarness`, `VerificationReport`

Standard suite: 12 passes covering token forgery/expiry/revocation/mismatch,
capability escalation, cell hopping (blast radius), grounding detection,
contrast pairs, elastic capacity contraction, ledger tamper evidence, and
Think Box handoff integrity.

Measured result (live fabric): **12/12 passes, overall 1.0, verdict STRONG**.

See `docs/disruptor-evaluation.md`.

Test count: **294 tests passing**.

## THINK Burst Protocol

**Status:** Complete (branch `feat/disruptor-evaluation`)

New modules:
- `thinkbox/burst.py` — `BurstRunner`, `BurstBudget` (elastic-cash stub), `LiveVLLMClient`
- `thinkbox/reasoning.py` — `ReasoningNormalizer`, `capture_completion`

Burst runner produces grounded vs disruptor contrast pairs, captures the
`openai/gpt-oss-20b` reasoning channel, records the governance token id,
and hard-stops on calls/spend/time. Refuses to start without a valid token.

Docs: `docs/think-burst-protocol.md`. Offline demo: `examples/think_burst_demo.py`.

Test count: **325 tests passing**.

## Harvest & Replay

**Status:** Complete (branch `feat/disruptor-evaluation`)

New modules:
- `thinkbox/grounding.py` — `GroundingScorer` (deterministic evidence/numeric/reasoning scoring)
- `thinkbox/factcards.py` — `FactCardRegistry` (least-used-first coverage scheduling)
- `thinkbox/harvest.py` — `HarvestReplay`, `HarvestReport` (score jsonl offline; optional Verifier bridge)

`BurstRunner` now writes `evidence_text` and appends every admitted call to
the append-only `ActionLedger` (`ledger_valid` hash-chain check).

Offline: `data/evals/burst/*.jsonl`, `data/evals/harvest_report.{md,json}`.

Test count: **348 tests passing**.

## PR #83 — 10 Additional Governed Scheduler Features (2026-09-18)

**Status:** Complete
**Branch:** `feat/scheduler-10-pr83`
**PR:** https://github.com/Kudbee-Studio/think-box-ai/pull/83

### Features

| # | Feature | Description |
|---|---------|-------------|
| 1 | `WeightedFairQueue` | Weighted fair-queueing via deficit round robin across named queues |
| 2 | `JobLease` | Lease/TTL with expiry reclaim, fail-closed double-ack via LeaseExpiredError |
| 3 | `DedupedDelayedEnqueue` | Schedule-at + dedupe key, no duplicate fire |
| 4 | `CircuitBreaker` | Closed/open/half-open per downstream target, shed when open |
| 5 | `AdmissionLottery` | Probabilistic admit when at cap, audit events for every decision |
| 6 | `PlacementConstraints` | Require/avoid labels (zone, gpu, tenant), refuse if unsatisfiable |
| 7 | `ProgressiveDrain` | Stop new admits, finish in-flight, status API |
| 8 | `ReplayFromLedger` | Rehydrate queue state from ledger events, idempotent |
| 9 | `MultiPriorityAging` | Separate aging curves per priority band (reuses PriorityAging) |
| 10 | `SchedulerCanary` | Synthetic probe jobs on interval, emit health + SLABreachEmitter events |

### Bug Fixes

None in this PR.

### Testing

- 20 new test classes, 82 new tests in `tests/unit/test_scheduler.py`
- All 571 scheduler tests passing
- Full suite: 1275 tests, 6 skipped, 3 pre-existing failures in `test_swarm_instrumentation` (unrelated)

### Files Changed

- `thinkbox/scheduler.py` +1319 lines
- `tests/unit/test_scheduler.py` +433 lines

## PR #84 — 10 Additional Governed Scheduler Features (MERGED)

**Status:** Merged
**Branch:** `feat/scheduler-10-pr84`
**PR:** https://github.com/Kudbee-Studio/think-box-ai/pull/84

### Features

| # | Feature | Description |
|---|---------|-------------|
| 1 | `AdaptiveConcurrency` | Auto-tune concurrency based on latency/throughput |
| 2 | `Preemption` | Preempt low-priority running tasks for high-priority |
| 3 | `TaskCoalescing` | Merge identical pending tasks |
| 4 | `WorkflowTemplate` | Versioned, reusable workflow definitions |
| 5 | `BackpressurePropagation` | Backpressure through dependency graph |
| 6 | `SchedulerClock` | Monotonic clock for deterministic time testing |
| 7 | `AdmissionFilter` | Pluggable admission filter chain |
| 8 | `FairnessIndex` | Jain's fairness index per tenant |
| 9 | `DynamicBudget` | Dynamic budget reallocation across goals |
| 10 | `TaskAffinity` | Data/task locality-aware scheduling |

### Testing
- 10 new test classes, ~60 new tests in tests/unit/test_scheduler.py
- All 620 scheduler tests passing
- Full suite: 1275 tests, 6 skipped

### Files Changed
- `thinkbox/scheduler.py` +760 lines
- `tests/unit/test_scheduler.py` +580 lines

## PR #85 — 10 Hardening Features for Governed Scheduler (MERGED)

**Status:** Merged
**Branch:** `feat/scheduler-10-pr85`
**PR:** https://github.com/Kudbee-Studio/think-box-ai/pull/85

### Features

| # | Feature | Description |
|---|---------|-------------|
| 1 | `DeadLetterQueue` | Dead letter queue for permanently failed jobs |
| 2 | `ConfigValidator` | Centralized configuration validation |
| 3 | `MemoryPressureMonitor` | Memory pressure monitoring with thresholds |
| 4 | `GracefulShutdownCoordinator` | Graceful shutdown coordination |
| 5 | `SchedulerSentinel` | Active auto-recovery agent |
| 6 | `DataIntegrityChecker` | SHA-256 integrity verification |
| 7 | `RetryStormGuard` | Global retry rate limiting |
| 8 | `SchemaVersionTracker` | Schema version tracking for recovery |
| 9 | `AnomalyDetector` | Statistical anomaly detection |
| 10 | `AdmissionRateLimiter` | Sliding-window admission rate limiting |

### Testing
- 10 new test classes, ~89 new tests in tests/unit/test_scheduler.py
- All 689 scheduler tests passing
- Full suite: 1275 tests, 6 skipped

### Files Changed
- `thinkbox/scheduler.py` +600 lines
- `tests/unit/test_scheduler.py` +580 lines

## PR #97 — Agent Control Plane x10 (MERGED)

**Status:** Merged
**Branch:** `feat/agent-control-plane-x10`
**PR:** https://github.com/Kudbee-Studio/think-box-ai/pull/97

## PR #98 — Dashboard Control Plane Bind (MERGED)

**Status:** Merged
**Branch:** `feat/dashboard-control-plane-bind-x10`
**PR:** https://github.com/Kudbee-Studio/think-box-ai/pull/98

## PR #99 — Durable Proof Plane (MERGED)

**Status:** Merged
**Branch:** `feat/agent-durable-proof-plane-x10`
**PR:** https://github.com/Kudbee-Studio/think-box-ai/pull/99

### Features

| # | Feature | Module |
|---|---------|--------|
| 1 | SQLite ActionReceiptStore + hash-chain | `thinkbox/agent/control_plane/store.py` |
| 2 | Kernel hooks (admit/capacity/secret/shutdown) | `thinkbox/agent/control_plane/kernel_hooks.py` |
| 3 | verify_chain() gap/tamper/fork | `thinkbox/agent/control_plane/verify_chain.py` |
| 4 | Export proof bundle (JSONL + sha256) | `thinkbox/agent/control_plane/export.py` |
| 5 | Import + offline verify bundle | `thinkbox/agent/control_plane/import_bundle.py` |
| 6 | Budget-breaker terminal receipt | `thinkbox/agent/control_plane/budget_trip.py` |
| 7 | Kill-switch durable events | `thinkbox/agent/control_plane/kill_events.py` |
| 8 | Lease expiry eviction receipt | `thinkbox/agent/control_plane/lease_evict.py` |
| 9 | Dashboard/API chain status read | `thinkbox/agent/control_plane/api.py` |
| 10 | E2e hermetic crash → verify | `tests/unit/agent/test_durable_e2e.py` |

### Testing
- 71 new tests across 9 files in `tests/unit/agent/`
- Full suite: 1913 tests, 6 skipped, 3 expected failures

### Files Changed
- `thinkbox/agent/control_plane/` (9 modules)
- `tests/unit/agent/` (9 test files)

## PR #100 — Demo-in-10 × Control Plane × Durable Proof (DRAFT)

**Status:** Draft
**Branch:** `feat/demo-in-10-control-plane-proof-x10`
**PR:** https://github.com/Kudbee-Studio/think-box-ai/pull/100

### Features

| # | Feature | Module |
|---|---------|--------|
| 1 | demo_in_10_control_plane.sh (mock→burst→harvest→proof) | `scripts/demo_in_10_control_plane.sh` |
| 2 | Admit + capacity binding (fail-closed) | `thinkbox/agent/control_plane/demo_bind.py` |
| 3 | DemoRunRecord (scores, budget, timestamps) | `thinkbox/agent/control_plane/demo_record.py` |
| 4 | Proof bundle under data/proofs/demo-<id>/ | `thinkbox/agent/control_plane/demo_proof.py` |
| 5 | GET /demo/runs + /demo/runs/{id}/proof | `backend/api/v1/demo_runs.py` |
| 6 | Dashboard panel + copy run cmd + last run metrics | `public/control-plane/demo.html` |
| 7 | Dashboard verify-chain button | `public/control-plane/demo.html` |
| 8 | README Demo in 10 section | `README.md` |
| 9 | Hermetic e2e test | `tests/unit/demo/test_e2e.py` |
| 10 | CONTROL_PLANE_BOUND tag | STATUS.md (this section) |

### Testing
 - 40 new tests across 8 files in `tests/unit/demo/`
 - All hermetic, no network, no GPU
 - Edge cases: duplicate run_id, corrupted JSON, empty token, caching

### Tags
- Demo-in-10 → CONTROL_PLANE_BOUND

## PR #101 — BYOC Mercury-2 + Upstash THINK Stash × Proof Bind (MERGED)

**Status:** Merged
**Branch:** `feat/byoc-think-stash-mercury-upstash-x10`
**PR:** https://github.com/Kudbee-Studio/think-box-ai/pull/101

### Features

| # | Feature | Module |
|---|---------|--------|
| 1 | ByocConfig loader (no secret logging) | `thinkbox/byoc_config.py` |
| 2 | Mercury-2 OpenAI-compat client | `thinkbox/byoc_client.py` |
| 3 | DEMO_MODE mock\|byoc resolver | `thinkbox/byoc_resolve.py` |
| 4 | THINK stash SQLite local store | `thinkbox/byoc_stash_store.py` |
| 5 | THINK stash writer to Upstash Vector | `thinkbox/byoc_stash_writer.py` |
| 6 | THINK stash reader from Upstash | `thinkbox/byoc_stash_reader.py` |
| 7 | Bind stash to ActionReceipt chain | `thinkbox/byoc_proof_bind.py` |
| 8 | GET /think/stash/status + last | `backend/api/v1/think_stash.py` |
| 9 | Dashboard BYOC status chips | `public/control-plane/think_stash.html` |
| 10 | Demo script | `scripts/demo_in_10_byoc.sh` |
| 11 | Hermetic tests | `tests/unit/byoc/test_e2e.py` |

### Tags
- THINK_STASH_BOUND (parity with CONTROL_PLANE_BOUND)

## PR #102 — Upstash Box + Inception Mercury-2 Live Experiment (MERGED)

**Status:** Merged
**Branch:** `feat/byoc-box-mercury-live`
**PR:** https://github.com/Kudbee-Studio/think-box-ai/pull/102

### Features

| # | Feature | Module |
|---|---------|--------|
| 1 | PR plan document | `docs/PR102_BOX_MERCURY_LIVE.md` |
| 2 | Live Box + Mercury-2 throughput experiment | `experiments/box_mercury_live.py` |
| 3 | Substrate report + dashboard emit | `thinkbox/substrate.py` (live usage) |
| 4 | Hermetic tests for experiment | `tests/unit/byoc/test_box_mercury.py` |
| 5 | Demo script | `scripts/demo_in_10_box_mercury.sh` |

### Goal

First live experiment executing on the Upstash Box substrate using Inception Mercury-2: substrate verification, throughput measurement at concurrency 1/4/8/16, proof artifact generation, dashboard state emit.

### Tags
- THINK_BOX_BOUND

## PR #103 — Persistent Box + Mercury-2 Results v2 (DRAFT)

**Status:** Draft
**Branch:** `feat/byoc-box-mercury-live-v2`
**PR:** https://github.com/Kudbee-Studio/think-box-ai/pull/103

### Features

| # | Feature | Module |
|---|---------|--------|
| 1 | PR plan document | `docs/PR103_BOX_MERCURY_PERSISTENT.md` |
| 2 | Enhanced experiment (configurable, multi-iteration, persistent) | `experiments/box_mercury_live.py` v2 |
| 3 | API endpoints | `backend/api/v1/box_mercury.py`, `backend/api/v1/box_status.py` |
| 4 | Dashboard panel | `public/control-plane/box_mercury.html` |
| 5 | Integration tests | `tests/unit/byoc/test_integration.py` |
| 6 | Substrate probe tests | `tests/unit/test_substrate.py` additions |
| 7 | Demo script | `scripts/demo_in_10_box_mercury_v2.sh` |

### Goal

Take PR #102 experiment to next level: persistent results via SQLite, configurable parameters, multiple iterations for statistical significance, results comparison, API + dashboard for visualization.

### Tags
- THINK_BOX_BOUND

## PR #106 — Org-Memory Lifecycle Receipts + CI/PR Event Hooks

**Status:** Merged
**Branch:** `feat/lifecycle-org-memory-ci-hooks`
**PR:** https://github.com/Kudbee-Studio/think-box-ai/pull/106

### Features

| # | Feature | Module |
|---|---------|--------|
| 1 | Append-only org-memory receipt store (sequence + hash chain) | `thinkbox/org_memory_receipts.py` |
| 2 | Query by `pr_number` / `experiment_id` / time range (redacted) | `OrgMemoryReceiptStore.query` |
| 3 | GitHub PR + CI status adapters (hermetic fakes); never auto-merge | `thinkbox/pr_lifecycle_event_hooks.py` |
| 4 | Crash-resume via org-memory checkpoints | `OrgMemoryResilientRunner` |
| 5 | Control-plane API + dashboard stub | `backend/api/v1/lifecycle_receipts.py`, `public/control-plane/lifecycle_receipts.html` |
| 6 | Hermetic tests | `tests/unit/test_org_memory_lifecycle.py` |

### Four-State

| CODE_COMPLETE | TEST_VERIFIED | LIVE_VERIFIED | PRODUCTION_READY |
|---------------|---------------|---------------|------------------|
| Yes | Yes (local unittest) | **BLOCKED** (no external provider) | **BLOCKED** |

### Tags
- PR_LIFECYCLE_ORG_MEMORY

## PR #107 — Signed GitHub Webhook + AdmissionGate

**Status:** Merged
**Branch:** `feat/lifecycle-github-webhook-admission`
**PR:** https://github.com/Kudbee-Studio/think-box-ai/pull/107

### Features

| # | Feature | Module |
|---|---------|--------|
| 1 | `X-Hub-Signature-256` verification (`WEBHOOK_SECRET`); fail-closed | `thinkbox/github_webhook.py` |
| 2 | Map `pull_request` / `check_suite` / `workflow_run` / `status` → coordinator | `parse_github_webhook_payload` |
| 3 | `AdmissionGate` on mutating dispatch; denial → `BLOCKED` org-memory receipt | `GitHubWebhookLifecycleService` |
| 4 | FastAPI receiver (no API key; HMAC only) | `backend/api/v1/github_webhook.py` |
| 5 | Hermetic + optional live signature tests | `tests/unit/test_github_webhook.py` |
| 6 | Operator guide | `docs/guides/github_webhook.md` |

### Four-State

| CODE_COMPLETE | TEST_VERIFIED | LIVE_VERIFIED | PRODUCTION_READY |
|---------------|---------------|---------------|------------------|
| Yes | Yes (local unittest) | **BLOCKED** (no GitHub delivery in CI) | **BLOCKED** |

### Tags
- PR_LIFECYCLE_GITHUB_WEBHOOK

## PR #108 — Pipeline Dashboard + Founder Merge Gate (DRAFT)

**Status:** Draft — hardened (10 checkpoint commits on branch)
**Branch:** `feat/pipeline-dashboard-admission-merge-gate`
**PR:** https://github.com/Kudbee-Studio/think-box-ai/pull/108

### Features

| # | Feature | Module |
|---|---------|--------|
| 1 | Per-PR pipeline rollup (evidence + admission + CI + blocked reasons) | `thinkbox/pipeline_dashboard.py` |
| 2 | Admission denial ledger API (`GET .../admissions/denials`) | `PipelineDashboardAggregator.admission_denial_ledger` |
| 3 | Founder merge: governance token + PR-bound founder proof + deny matrix | `FounderGatedMergeService` |
| 4 | Per-PR receipt integrity + CI timeline + delta poll/SSE | `backend/api/v1/pipeline_dashboard.py` |
| 5 | Pipeline quarantine read/write (governance-gated) | `PipelineQuarantineController` |
| 6 | Ops scorecard on overview (`ops_scorecard`) | `pipeline_ops_scorecard()` |
| 7 | Live refresh UI + denial/quarantine banners | `public/control-plane/pipeline_dashboard.html` |
| 8 | Adversarial + concurrency hermetic tests | `tests/unit/test_pipeline_*.py` |

### Tests (local gate)

```bash
python3 -m unittest \
  tests.unit.test_pipeline_dashboard \
  tests.unit.test_pipeline_delta \
  tests.unit.test_pipeline_adversarial \
  tests.unit.test_pipeline_concurrency \
  tests.unit.test_github_webhook \
  tests.unit.test_org_memory_lifecycle -v
```

### Four-State

| CODE_COMPLETE | TEST_VERIFIED | LIVE_VERIFIED | PRODUCTION_READY |
|---------------|---------------|---------------|------------------|
| Yes | Yes (32 unittest, 1 skipped) | **BLOCKED** (no production GitHub merge exercised) | **BLOCKED** |

### Tags
- PR_PIPELINE_DASHBOARD_MERGE_GATE

### Intelligence layer (v2 — merge readiness + audit + policy + correlation + fleet checkpoint)

| Capability | Endpoint / module |
|------------|-------------------|
| Merge readiness score (0–100, rule-based) | `GET .../pr/{n}/merge-readiness`, `thinkbox/pipeline_readiness.py` |
| Founder audit packet + HMAC | `GET .../pr/{n}/audit-packet`, `thinkbox/pipeline_audit_packet.py` |
| Merge policy gate on request-merge | `thinkbox/pipeline_merge_policy.py` → `merge_policy_denied` receipts |
| Blast-radius correlation | `GET .../correlation/blast-radius` |
| Fleet checkpoint attest/verify | `POST .../checkpoint/attest`, `GET .../checkpoint/verify` |

Extended unittest: **38 run, 37 OK, 1 skipped** (pipeline + webhook + org-memory).

## PR #146 — KILO mercury-hermetic gate (DRAFT)

**Status:** Draft — closes **`mercury-hermetic`** in **#141–#150** arc (bounded Mercury mocks + live-gate stub; no Live proof)  
**Scope:** `thinkbox/kilo_mercury_hermetic.py`, `scripts/verify_kilo_mercury_hermetic.py`, PR #146 hermetic tests  

### Four-State

| CODE_COMPLETE | TEST_VERIFIED | LIVE_VERIFIED | PRODUCTION_READY |
|---------------|---------------|---------------|------------------|
| Yes | Yes (branch gate) | **No** | **No** |

### Tests

```bash
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr146 -v
python3 scripts/verify_kilo_mercury_hermetic.py
python3 scripts/verify_kilo_spine.py
python3 scripts/scan_doc_secrets.py
```

## PR #145 — KILO governance-evidence gate (MERGED)

**Status:** Merged — closes **`governance-evidence`** in **#141–#150** arc (admission token + live-burst evidence shape; no Live proof)  
**Scope:** `thinkbox/kilo_governance_evidence.py`, `scripts/verify_kilo_governance_evidence.py`, PR #145 hermetic tests  
**Note:** PR **#144** was CI/post-merge unittest green only — not governance-evidence.

### Four-State

| CODE_COMPLETE | TEST_VERIFIED | LIVE_VERIFIED | PRODUCTION_READY |
|---------------|---------------|---------------|------------------|
| Yes | Yes (branch gate) | **No** | **No** |

### Tests

```bash
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr145 -v
python3 scripts/verify_kilo_governance_evidence.py
python3 scripts/verify_kilo_spine.py
python3 scripts/scan_doc_secrets.py
```

## PR #143 — KILO substrate-checklist gate (MERGED)

**Status:** Merged — closes **`substrate-checklist`** in **#141–#150** arc (Box URL/token readiness on env-matrix; no Live proof)  
**Scope:** `thinkbox/kilo_substrate_checklist.py`, `scripts/verify_kilo_substrate_checklist.py`, PR #143 hermetic tests

### Four-State

| CODE_COMPLETE | TEST_VERIFIED | LIVE_VERIFIED | PRODUCTION_READY |
|---------------|---------------|---------------|------------------|
| Yes | Yes (branch gate) | **No** | **No** |

### Tests

```bash
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr143 -v
python3 scripts/verify_kilo_substrate_checklist.py
python3 scripts/verify_kilo_spine.py
python3 scripts/scan_doc_secrets.py
```

## PR #142 — KILO env-matrix gate (MERGED)

**Status:** Merged — **`env-matrix`** in **#141–#150** arc  
**Scope:** `thinkbox/kilo_env_matrix.py`, `scripts/verify_kilo_env_matrix.py`

## PR #153 — KILO live-smoke operator path (DRAFT)

**Status:** Draft — gate **`live-smoke-operator`** (hermetic CLI write + audit flip candidate; no live HTTP in CI)  
**Scope:** `thinkbox/kilo_live_smoke_operator.py`, `scripts/kilo_live_smoke_operator.py`, `scripts/verify_kilo_live_smoke_operator.py`

### Tests

```bash
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr153 -v
python3 scripts/verify_kilo_live_smoke_operator.py
python3 scripts/verify_kilo_spine.py
python3 scripts/scan_doc_secrets.py
```

**LIVE VERIFIED** still requires founder ack + Box URL + real recorded smoke after merge.

## PR #152 — KILO bounded live smoke evidence (MERGED)

**Status:** Merged — gate **`live-smoke-evidence`** (evidence binder + audit flip helper; hermetic CI, no live HTTP)  
**Scope:** `thinkbox/kilo_live_smoke_evidence.py`, `scripts/verify_kilo_live_smoke_evidence.py`, `data/kilo_live_smoke_evidence/fixtures/`

### Tests

```bash
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr152 -v
python3 scripts/verify_kilo_live_smoke_evidence.py
```

## PR #151 — KILO post-season harden (MERGED)

**Status:** Merged — ops gate **`post-season-harden`** (CI, branch hygiene, docs sync; not Live proof)  
**Scope:** `thinkbox/kilo_post_season_harden.py`, `scripts/verify_kilo_post_season_harden.py`, `scripts/cleanup_merged_cursor_branches.py`

## PR #150 — KILO live-proof-exec (MERGED, season close)

**Status:** Merged — closes **`live-proof-exec`**; arc #141–#150 season complete at TEST VERIFIED (not LIVE VERIFIED)  
**Scope:** `thinkbox/kilo_live_proof_exec.py`, `scripts/verify_kilo_live_proof_exec.py`  
**Next:** Founder-run bounded smoke per runbook; **PR #153** operator path in flight

## PR #141 — KILO Live-proof readiness spine (MERGED)

**Status:** Merged — start of **#141–#150** arc (docs + hermetic gates; no Live proof)  
**Scope:** Runbook, arc map, `thinkbox/kilo_live_proof_readiness.py`, PR #141 hermetic tests

### Tests

```bash
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr141 -v
```

## PR #140 — Receipt deep-link + shared etag (MERGED)

**Status:** Merged — control-plane deep-link + tab-shared conditional GET cache  
**Scope:** `receipts.html` → `think_job_status.html` receipt watch; `control_plane_etag_store.js` across tabs

### Four-State

| CODE_COMPLETE | TEST_VERIFIED | LIVE_VERIFIED | PRODUCTION_READY |
|---------------|---------------|---------------|------------------|
| Yes | Yes (branch gate) | **No** | **No** |

### Tests

```bash
python3 -m unittest tests.unit.test_control_plane_etag_store \
  tests.unit.test_control_plane_deep_link \
  tests.unit.test_control_plane_think_job_static_pr140 \
  tests.unit.test_think_job_status_ui_pr140 \
  tests.e2e.test_f140_receipt_deep_link_etag -v
```
