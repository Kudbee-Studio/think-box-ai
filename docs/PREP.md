# PREP — Handoff & Readiness Brief

**Date:** 2026-09-15

> ## ADDENDUM — 2026-09-25 (PR #202 merged; PR #203 memory layers)
>
> **#202 merged** at `75a36c5` — Trait Lab (seeded local game). Not LIVE VERIFIED.
> **#203 merged** at `3976930` — fail-closed four-layer ingest.
> **#204 merged** at `0b3fc87` — read / query / retention.
> **#205 merged** at `01f46c6` — organizational versioning + portable snapshot.
> **#206 merged** at `1c8294f` — Trait Lab proof → four-layer ledger.
> **#207 merged** at `d989255` — replay rematch.
> **#208 merged** at `b9074c6` — list/compare stored Trait Lab proofs.
> **#209 merged** at `abdf325` — local board from stored proofs.
> **#210 merged** at `7b0e0df` — best stored XP per seed.
> **#211 merged** at `8536fa4` — seed history (all stored runs, highest XP first). `live_verified` false.
> **#212 merged** at `413c28a` — seed index (count + best XP per stored seed). `live_verified` false.
> **#213 next:** wait for 1800s cadence timer. At most one open PR.
> **Test gate:** memory + trait-lab suites → 62 OK.
> **Four-state:** CODE COMPLETE / TEST VERIFIED on main — not LIVE VERIFIED.
>
> ## ADDENDUM — 2026-09-24 (PR #201 draft, Upstash Box access)
>
> **Scope:** Bounded access test via existing `UpstashBoxExecutionAdapter`. Official vars `UPSTASH_PUBLIC_BOX_URL` and `UPSTASH_PUBLIC_BOX_TOKEN` were **absent** in the agent process. Classification **A**. No HTTP. No live receipt. `UPSTASH_BOX_API_KEY` present and unused.
> **Test gate:** `python3 -m unittest tests.unit.test_upstash_box_access tests.unit.test_kilo_live_proof_readiness_pr201 -v` + `verify_kilo_pr201_upstash_box_access.py`.
> **Four-state:** CODE COMPLETE / TEST VERIFIED on branch only — not LIVE VERIFIED.
>
> ## ADDENDUM — 2026-09-23 (PR #151 draft, post-season harden)
>
> **Scope:** Ops gate **`post-season-harden`**: CI spine alignment, `cleanup_merged_cursor_branches.py`, docs/STATUS sync — **not** Live proof, **not** arc gate #141–#150 extension.  
> **Test gate:** `python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr151 -v` + `verify_kilo_post_season_harden.py`; `verify_kilo_spine.py` OK.  
> **Four-state:** CODE COMPLETE / TEST VERIFIED on branch only — not LIVE VERIFIED.
>
> ## ADDENDUM — 2026-09-23 (PR #150 merged, arc season close)
>
> **Scope:** KILO **`live-proof-exec`** gate merged — hermetic execution plan only.  
> **Four-state:** TEST VERIFIED; audit `live_verified: false`.
>
> ## ADDENDUM — 2026-09-23 (PR #145 draft)
>
> **Scope:** KILO **`governance-evidence`** gate: `thinkbox/kilo_governance_evidence.py`, `verify_kilo_governance_evidence.py`, layered on env-matrix + substrate-checklist — **no Live proof, no Mercury/GPU**.  
> **Test gate:** `python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr145 -v` + `verify_kilo_governance_evidence.py`; `verify_kilo_spine.py` OK.  
> **Four-state:** CODE COMPLETE / TEST VERIFIED on branch only — not LIVE VERIFIED.
>
> ## ADDENDUM — 2026-09-23 (PR #144 merged, CI only)
>
> **Scope:** Post-merge CI / unittest discover green — **not** governance-evidence gate closure.
>
> ## ADDENDUM — 2026-09-23 (PR #143 merged)
>
> **Scope:** KILO **`substrate-checklist`** gate: `thinkbox/kilo_substrate_checklist.py`, `verify_kilo_substrate_checklist.py`, layered on env-matrix — **no Live proof, no live build**.  
> **Test gate:** `python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr143 -v` + `verify_kilo_spine.py` / `verify_kilo_substrate_checklist.py`; `scripts/scan_doc_secrets.py` OK.  
> **Four-state:** CODE COMPLETE / TEST VERIFIED on branch only — not LIVE VERIFIED.
>
> ## ADDENDUM — 2026-09-23 (PR #142 merged)
>
> **Scope:** KILO **`env-matrix`** gate: `thinkbox/kilo_env_matrix.py`, `verify_kilo_env_matrix.py`, hermetic contract tests.
>
> ## ADDENDUM — 2026-09-23 (PR #141 merged)
>
> **Scope:** KILO Live-proof readiness **spine** (#141–#150 arc start): runbook, arc doc, `thinkbox/kilo_live_proof_readiness.py`, hermetic gates — **no Live proof**.  
> **Test gate:** `python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr141 -v`.
>
> ## ADDENDUM — 2026-09-23 (PR #140 merged)
>
> **Branch:** `cursor/pr140-receipt-deeplink-shared-etag-17e7` (draft milestone).  
> **Scope:** `receipts.html` deep-link → receipt-keyed Think Job watch (#139); shared `sessionStorage` etag across control-plane tabs.  
> **Test gate:** `python3 -m unittest discover -s tests -t .` → **2498 OK**, 8 skipped, 3 expected failures; F140 e2e.  
> **Four-state:** CODE COMPLETE / TEST VERIFIED on branch only — not LIVE VERIFIED.
>
> ## ADDENDUM — 2026-09-22 (PR #126 audit close-out)
>
> **Branch:** `feat/pr126-f010-token-redact-and-p1` (draft PR #126).  
> **Test gate:** `python3 -m unittest discover tests/` (run after merge candidate; see pass JSON for last counts).  
> **Doc secrets:** `python3 scripts/scan_doc_secrets.py` must exit 0 (F010).  
> **Audit artifacts:** `docs/audit/passes/2026-09-22-pr126.json`, prior pass `2026-09-22-pr125.json`.  
> Canonical narrative: `docs/CONTINUITY.md` + `docs/STATUS.md`.
>
> ## ADDENDUM — 2026-09-22 (PR #125 audit)
>
> **Branch:** `feat/pr125-audit-ledger-and-25-fixes` (merged PR #125).  
> **Test gate:** `python3 -m unittest discover tests/` → **2235 OK**, 8 skipped, 3 expected failures.  
> **Audit artifacts:** `docs/audit/README.md`, `docs/audit/passes/2026-09-22-pr125.json`, `scripts/audit_ledger.py`.  
> **Deploy:** Vercel preview blocked in agent env — see `docs/audit/checklists/deploy-vercel.md` (finding F018).  
**Repo:** `Kudbee-Studio/think-box-ai`
**Main:** `2cec2ce` — working tree clean, **302 tests OK** (1 skipped: optional `fastapi`/`uvicorn` absent in the sandbox)

> ## ADDENDUM — 2026-09-17 (supersedes the numbers above; 09-15 body preserved below)
>
> **Branch:** `kilo/cherry-circuit-zdv`, **664 tests OK** (6 skipped).
> Canonical state lives in `docs/CONTINUITY.md` / `STATUS.md` / `AGENTS.md` §Chronicle.
>
> - **PR #83 merged** (10 scheduler features: WeightedFairQueue, JobLease, DedupedDelayedEnqueue, CircuitBreaker, AdmissionLottery, PlacementConstraints, ProgressiveDrain, ReplayFromLedger, MultiPriorityAging, SchedulerCanary)
>
> - **Verified execution chain now spans the full DAG lifecycle AND concurrent multi-goal budgets:** `ThinkBoxEngine.execute_goal` task nodes route through `GovernedEngine.execute_verified_task` → `VerifiedRetrySession.run_async` via an injected runner; `GovernedEngine.execute_verified_goal` aggregates DAG totals; new `thinkbox/concurrent_goals.py` (`ConcurrentGoalsRunner`) runs multiple goals concurrently, each on its own fresh `GovernedEngine` (avoiding the shared `_verified_task_runner` race) with independent per-goal budgets or a shared global budget (atomic synchronous `_spend_call`). Live-proven on 2 concurrent goals (1 single-task + 1 fan-in DAG) with 4 real Mercury-2 calls; cross-goal accounting exact (global 4 = 1+3). Proof `data/thinkboxmd/artifacts/concurrent_goals_live_proof_20260917.json` SHA256 `0d740895…489a`.
> - **Access inventory update:** Upstash Box is now the primary execution substrate (usable); UpCloud `kudbeev3` is LIVE_VERIFIED via API as control-plane ONLY (no SSH, no compute — removed from roadmap). Inception Mercury 2 usable. Upstash Vector writes fixed (fail-closed `EmbeddingError`).
> - **Pipeline dbs are reconstructable:** a workspace re-materialization wiped the gitignored SQLite dbs; `experiments/recover_pipeline_db.py` rebuilds experiments.db + memory.db from git-tracked artifacts (ledger hash chain NOT reconstructable — documented).
> - **Test gate:** `python3 -m unittest discover tests/` → 664 OK (6 skipped). Defects #2/#3/#5 from §3 below still open; defect #1 (Upstash Vector) FIXED; defect #4 partially (Box is now the execution substrate).
> - **Next larger improvement:** N>2 goals with cross-goal budget contention policy (fair-share vs priority) + a concurrency stress test — accounting-first, not speed-first.

This is the "pick it up cold" document. Everything below is verified or
explicitly marked as not-verified.

---

## 1. What is shipped and verified

| Capability | Evidence | Status |
|---|---|---|
| Mock vLLM transport (loopback `:8001`) | `thinkbox/mock_vllm.py`, burst smoke run | ✅ verified |
| THINK burst runner (offline + live) | `thinkbox/burst.py`, `data/evals/burst-smoke/` | ✅ verified |
| Disruptor + verifier harness | 15/15 passes, **STRONG** | ✅ verified |
| Harvest replay | groundedness 0.900, bind-failure 1.000 | ✅ verified |
| Interrupt/resume with checkpoints | `experiments/test_interrupt_resume.py` | ✅ verified |
| THINKBOXMD-RESEARCH workflow | `docs/THINKBOXMD_REPORT.md` — 9 PASS / 2 PARTIAL | ✅ verified |
| Swarm instrumentation (10 instruments) | `experiments/verify_instrumentation.py` — **11/11** | ✅ verified |
| Strength index + learning curve | `0.6405 → 0.7318 (+0.0913)` | ✅ verified |
| Dashboard (mobile-first) | stdlib server, tunnels via `cloudflared` | ✅ verified |
| Mercury 2 live provider | `api.inceptionlabs.ai/v1`, ~24 rps ceiling | ✅ verified |

**Run everything:**

```bash
python3 -m unittest discover tests/                    # 302 OK
python3 experiments/verify_instrumentation.py --live   # 11/11
python3 experiments/big_swarm.py --primary 224 --validators 32 --concurrency 32 --fresh-ledger
python3 experiments/verify_swarm_proof.py data/thinkboxmd/big_swarm_*.json
python3 experiments/swarm_dashboard.py --port 8787
cloudflared tunnel --url http://127.0.0.1:8787
```

---

## 2. Repo / CI state

- `origin/main` is up to date; branch and main in sync (0 ahead / 0 behind).
- **CI is not trusted right now.** GitHub billing is restricted per the operator;
  the workflow in `.github/workflows/test.yml` runs `python3 -m unittest discover tests/ -v`.
  Treat local `302 OK` as the gate.
- One pre-existing environmental skip: optional `fastapi`/`uvicorn` are absent
  from the sandbox interpreter (no `pip`/`apt` network). The test skips rather
  than fails, so the suite is honest rather than red.
- PR **#62 MERGED**, PR **#60 MERGED**, PR **#61 still OPEN**
  (`feat/disruptor-evaluation` — superseded by work already on `main`; safe to close).

---

## 3. Known defects (open, not hidden)

| # | Defect | Impact | File |
|---|--------|--------|------|
| 1 | Upstash Vector writes rejected (`HTTP 422`, dense index needs a vector); no embedding provider exists | distributed/vector memory silently fails; local SQLite unaffected | `thinkbox/session.py`, `data/findings/thinkboxmd_upstash_vector_defect.md` |
| 2 | THINK token economy is integer simulation, no settlement | "minting" is conceptual | `thinkbox/economy.py`, `think_box_ai/token.py` |
| 3 | `core/solana/*` shells out to `solana`/`anchor` CLIs that are **not installed** | wallet/token ops return `CLI not installed` | `core/solana/__init__.py` |
| 4 | No MCP client/server; no Redis client; Upstash Box is metadata-only | no external tool bridge, no distributed queue | repo-wide |
| 5 | `tests/e2e/` is empty; `benchmarks/` has no artifacts | `AGENTS.md` §1.5 evidence requirement unmet | — |

**Fixed this cycle:** `thinkbox/economy.py::transfer()` deadlocked on any new
recipient (called `create_account()` while holding the same non-reentrant lock).
Fixed + regression test.

---

## 4. Access inventory (from the cloud sandbox)

| Service | Env present | Usable | Blocker |
|---|---|---|---|
| Inception Mercury 2 | `INCEPTION_API_KEY` | ✅ **yes** | — |
| Upstash Vector | `UPSTASH_VECTOR_REST_URL/TOKEN` | ⚠️ partial | dense index + no embedder |
| Upstash Box | `UPSTASH_BOX_API_KEY`, `UPSTASH_PUBLIC_BOX_URL` | ❌ | preview returns `preview not found` |
| UpCloud `kudbee-host-v1` (212.147.250.183) | `THINKBOX_UPCLOUD_API_TOKEN` | ❌ | token **401 invalid**; `~/.ssh/kilo-upcloud` absent; IP behind Cloudflare (1003) |
| Redis | — | ❌ | no client configured |
| MCP | — | ❌ | none configured |

**To unblock UpCloud:** mint a fresh API token from the panel and/or place the
SSH private key at the configured `UPCLOUD_SSH_KEY_PATH`. No code change needed.

---

## 5. Next, in priority order

1. **Embedding provider** → then fix `UpstashVectorSync.upsert()` to send a
   vector and to surface HTTP errors instead of returning bare `False`.
   *Unblocks distributed Commons.*
2. **Wire `SelfImprovementLoop` into the run** so the retest is automatic
   (today it is callable and verified, but the swarm does not yet drive it).
3. **`--replay <session_id>`** — reload a genome and re-run identically.
   Genome save/verify already works; only the replay driver is missing.
4. **Reputation-weighted worker sampling** in wave 2.
5. **Deduplication of path constants** (`data/thinkboxmd/db/…` is hardcoded in
   four places) — extract `thinkbox/paths.py`.
6. **`DASHBOARD_BUILDOUT.md` Phase 1–4** — harden middleware, optional Cloudflare
   Access, mount dashboard API under `backend/main.py`, ETag caching.

---

## 6. Guardrails to preserve

- **No fake success.** Every claim in the docs points at an artifact, a test
  result, or a run. Keep it that way; if a number is unknown, write `—`.
- **Signals are not failures.** Challenge activity and validator tier inflation
  are *reported*, never penalised in the strength index.
- **Files over servers.** Do not add a broker/framework for the dashboard until a
  measured number demands it (see `docs/DASHBOARD_BUILDOUT.md` §5).
- **Synthetic only, not clinical.** All THINKBOXMD scenarios are
  `SYNTHETIC=true`; never real patient data.
- **Never print secrets.** Env values were only ever probed for presence.
