# KILO post-#170 PR roadmap (implementation slots)

**GitHub #171** (merged) was the **planning PR** for this table. Implementation slots map to GitHub PR numbers from **#172** onward.

**Status:** Planning artifact (not an implementation gate).  
**Baseline:** `main` after GitHub **#170** (beyond-KILO lint readiness, merged), **#172** (CI spine-trust, merged).  
**Four-state cap:** Hermetic work stays **CODE COMPLETE / TEST VERIFIED** only until founder-run Live proof + artifacts (`#152`/`#153` path).

**Founder constraints (summary):**

- One open **implementation** PR at a time; sequence below accordingly.
- No new combined post-#N **A–D umbrella** lanes (cost: nested evaluators, multi-minute CI hangs seen in #165–#169).
- Spine **fast-by-default** (`verify_kilo_spine.py`; nested e2e opt-in via `--e2e`, from #168).
- Lint: widen `LINT_SCOPE_REL_PATHS` in **single-theme** follow-ons (#170 operator guide; slots #174–#175).
- Live proof: optional later lane; requires Box URL + token + `THINKBOX_SWARM_LIVE_ACK` — never fake `live_verified: true`.

---

## Current snapshot (post-#176)

| Area | State |
|------|--------|
| Beyond-KILO lint | Gate `beyond-kilo-lint-readiness`; **38** scoped modules (v3) — **#174** + **#175** merged |
| Spine | `verify_kilo_spine.py` aggregates 28 blocks including #169 umbrella + #170 lint (static lint in spine unless `KILO_BEYOND_KILO_LINT_EXECUTE=1`) |
| CI | **#172** (merged): unittest + fast spine + beyond-KILO lint execute + secret scan |
| Chronicle | **#173–#176** merged; lint waves 1–2 complete |
| Kudbee SDK app | **#177** (merged) — `thinkbox/kudbee_sdk` + `apps/web/sdk` (~25 features) |
| KUDBEECLI Phase 2 | **#178** (merged) — `thinkbox/cli_phase2` + `thinkbox cli` deepen (~25 features) |
| Kudbee SDK follow-up | **#179** (merged) — `thinkbox/kudbee_sdk_followup` + `apps/web/sdk/followup.ts` (~25 features) |
| KUDBEECLI Phase 3 | **#180** (merged) — `thinkbox/cli_phase3` + `thinkbox cli` deepen (~25 features) |
| Kudbee SDK follow-up wave 2 | **#181** (merged) — `thinkbox/kudbee_sdk_followup_w2` + `apps/web/sdk/followup_w2.ts` (~25 features) |
| Receipt-chain deepen | **#182** (merged) — `thinkbox/receipt_chain_deepen` (~25 features) |
| Think Job hermetic e2e deepen | **#183** (merged) — `thinkbox/think_job_e2e_deepen` (~25 features) |
| Think Job POST /run contract deepen | **#184** (merged) — `thinkbox/think_job_post_run_deepen` (~25 features) |
| Think Job lifecycle integration fix pack | **#185** (merged) — `thinkbox/think_job_lifecycle_fixes` (25 fixes) |
| Think Job governed run receipt deepen | **#186** (merged) — `thinkbox/think_job_run_receipt_deepen` (~25 features) |
| Think Job receipt major fixes | **#187** (merged) — `thinkbox/think_job_run_receipt_deepen/fixes` (25 fixes) |
| Think Job governed run major fixes | **#188** (merged) — `thinkbox/think_job_governed_run_fixes` (25 fixes) |
| Think Job lifecycle major fixes | **#189** (merged) — `thinkbox/think_job_lifecycle_major_fixes` (25 fixes) |
| Think Job POST /run major fixes | **#190** (merged) — `thinkbox/think_job_post_run_major_fixes` (25 fixes) |
| Kudbee SDK follow-up wave 3 | **#191** (merged) — `thinkbox/kudbee_sdk_followup_w3` + `apps/web/sdk/followup_w3.ts` (~25 features) |
| Kudbee SDK follow-up wave 3 major fixes | **#192** (merged) — `thinkbox/kudbee_sdk_followup_w3_major_fixes` (35 fixes) + expansion packs |
| Kudbee SDK long-range + energy loops | **#193** (merged) — `thinkbox/kudbee_sdk_longrange_energy` (~25 features + 30 deepen packs) |
| Kudbee SDK long-range energy major fixes | **#194** (merged) — `thinkbox/kudbee_sdk_longrange_energy_major_fixes` (25 fixes) |
| Kudbee SDK enterprise lr-energy lanes | **#195** (merged) — `thinkbox/kudbee_sdk_enterprise_lr_energy` (25 enterprise lanes) |
| KUDBEECLI enterprise upgrade (Phase 4) | **#196** (merged) — `thinkbox/cli_phase4` + `thinkbox cli enterprise` (~25 features) |
| Cloud execution substrate Phase 1 | **#197** (merged) — `thinkbox/cloud_execution` (10 foundation features) |
| Cloud execution durable queue Phase 2 | **#198** (merged) — SQLite queue + `DurableCloudExecutionEngine` |
| Cloud execution worker orchestrator Phase 3 | **#199** (merged) — `CloudExecutionWorker` + governed loop |
| Environmental variables pack | **#200** (merged) — `thinkbox/env_vars` (~25 features) |
| Upstash Box access verification | **#201** (merged on main as of later merge train) — this-run class **A** `ENV_NOT_CONFIGURED`; not LIVE VERIFIED |
| Trait Lab (seeded game) | **#202** (merged `75a36c5`) — U01–U50 + harden; not LIVE VERIFIED |
| Memory layers ingest | **#203** (merged `3976930`) — fail-closed Session / Task / Organizational / Verified Knowledge; not LIVE VERIFIED |
| Memory query + retention | **#204** (merged `0b3fc87`) — read/query/decay/retention; not LIVE VERIFIED |
| Memory org version + snapshot | **#205** (merged `01f46c6`) — versioned org + export/import; not LIVE VERIFIED |
| Trait Lab memory ledger | **#206** (merged `1c8294f`) — proof → four layers; not LIVE VERIFIED |
| Trait Lab replay verify | **#207** (merged `d989255`) — replay rematch; not LIVE VERIFIED |
| Trait Lab run compare | **#208** (merged `b9074c6`) — list/compare proofs; not LIVE VERIFIED |
| Trait Lab local board | **#209** (merged `abdf325`) — rank_board over memory; not LIVE VERIFIED |
| Trait Lab best per seed | **#210** (merged `7b0e0df`) — highest XP per seed; not LIVE VERIFIED |
| Trait Lab seed history | **#211** (merged `8536fa4`) — all runs for one seed; not LIVE VERIFIED |
| Trait Lab seed index | **#212** (merged `413c28a`) — count + best XP per seed; not LIVE VERIFIED |
| Trait Lab seed grade filter | **#213** (merged `690979c`) — history by S/A/B/C/D; not LIVE VERIFIED |
| Trait Lab seed difficulty filter | **#214** (merged `77eb188`) — history by survey/lab/thesis; not LIVE VERIFIED |
| Trait Lab seed operator filter | **#215** (merged `88d9c45`) — history by operator name; not LIVE VERIFIED |
| Trait Lab seed daily filter | **#216** (merged `f99af45`) — history by daily flag; not LIVE VERIFIED |
| Trait Lab seed XP floor | **#217** (merged `50c5a9d`) — history at or above XP; not LIVE VERIFIED |
| Trait Lab seed XP ceiling | **#218** (merged `528ac80`) — history at or below XP; not LIVE VERIFIED |
| Trait Lab seed XP band | **#219** (merged `e0d400c`) — history between XP floor and ceiling; not LIVE VERIFIED |
| Trait Lab seed pack export | **#220** (merged `d66cc4a`) — portable snapshot of one seed; not LIVE VERIFIED |
| Trait Lab seed pack import | **#221** (merged `a05b31d`) — verify `pack_sha256` and write import fact; not LIVE VERIFIED |
| Trait Lab seed pack apply | **#222** (merged `2cfa121`) — write rematched pack runs into a destination store; not LIVE VERIFIED |
| Trait Lab seed pack diff | **#223** (merged `29e4ff9`) — compare two rematched packs for one seed; not LIVE VERIFIED |
| Trait Lab seed pack catalog | **#224** (merged `5db0c37`) — index imported/applied packs by `pack_sha256`; not LIVE VERIFIED |
| Trait Lab catalog operator pack | **GitHub #203** (merged `595dbb5`) — 25 catalog operators C01–C25; not LIVE VERIFIED |
| Trait Lab catalog compose | **GitHub #204** (merged `388fde8`) — merge / intersect / subtract rematched catalogs; not LIVE VERIFIED |
| Trait Lab catalog pin | **GitHub #205** (merged `8367f5a`) — pin / get / list / unpin rematched catalog snapshots; not LIVE VERIFIED |
| Trait Lab catalog pin operators | **GitHub #206** (merged `50211b4`) — 25 pin-index operators P01–P25; not LIVE VERIFIED |
| Trait Lab catalog pin compose | **GitHub #207** (merged `8a120d2`) — merge / intersect / subtract rematched pin indexes; not LIVE VERIFIED |
| Trait Lab catalog pin follow-through | **GitHub #208** (merged `eb622d5`) — xor + retain-best + fact_id/id-set harden; not LIVE VERIFIED |
| Trait Lab catalog follow-through | **GitHub #209 draft** — xor + retain-best on rematched pack catalogs; not LIVE VERIFIED |
| Live proof | Season #141–#150 closed hermetically; `live_verified: false` on all spine audit passes including `docs/audit/passes/2026-09-23-pr170.json` |
| Deferred product lanes | KUDBEECLI Phase 2 (**#129** draft), control-plane x10 (**#97**), PR **#103** Box Mercury v2 draft — **out of this spine sequence** unless founder reprioritizes |

---

## Sequenced PR roadmap

| Slot | Theme (one line) | Why now | Size | Out of scope | Risks |
|------|------------------|---------|------|--------------|-------|
| **Slot 1 (→ GH #172)** | CI spine-trust slimming (dedupe workflow verify scripts) | CI runs spine **and** nearly every gate script twice; wall-clock + flake surface; aligns with (a) spine health | ~8–15 commits; `test.yml`, `kilo_post_season_harden` checklist/docs, `test_kilo_live_proof_readiness_pr172` | Removing gate modules; combined umbrellas; live smoke | Must keep `verify_kilo_beyond_kilo_lint.py` with `EXECUTE=1` in CI; post_season checklist drift |
| **Slot 2 (→ GH #173)** | Chronicle honesty sync (#170 merged + post-170 era) | AGENTS/CONTINUITY/runbook H30–H32 vs stale “draft”; README for new readers; audit index | ~5–10 commits; docs + hermetic spine-doc tests only | Production code except test fixtures for doc paths | Low; avoid affirmative LIVE claims |
| **Slot 3 (→ GH #174)** | Lint scope wave 1 (spine + hermetic subprocess helpers) | #170 explicitly deferred widening; (b) gradual lint | ~6–12 commits; `LINT_SCOPE_REL_PATHS` + ruff/mypy fixes on new files | Whole `thinkbox/` tree; `core/` runtime | Mypy time; keep `--follow-imports=skip` |
| **Slot 4 (→ GH #175)** | Lint scope wave 2 (live-proof readiness spine modules) | Next bounded slice: `kilo_live_proof_readiness`, `kilo_env_matrix`, `kilo_hermetic_gate_memo` | ~8–15 commits | Combined lanes; importing provider SDKs | Same as slot 3 |
| **Slot 5 (→ GH #176)** | Control-plane receipt-chain single deepen (412/precondition only) | Mature receipt/ETag stack (#155–#161); one HTTP edge theme | ~10–18 commits; `receipt_chain_query` / conditional GET tests | END_LINK UX; dashboard bind; api_ops combined | No live Mercury; hermetic e2e only if scoped |
| **Slot 6 (→ GH #177)** | Kudbee SDK app (~25 features) | Primary surface: `thinkbox/kudbee_sdk` + `apps/web/sdk` for kudbEE web shell | ~20–30 commits; hermetic dry-run + gate `kudbee-sdk-app` | Combined umbrellas; live Box/Mercury | Scope creep into control-plane x10 |
| **Slot 7 (→ GH #178)** | KUDBEECLI Phase 2 deepen (~25 hermetic CLI features) | **Merged** after #177; Phase 1 inspect on main; gate `kudbee-cli-phase2` | ~20–30 commits; `thinkbox/cli_phase2` + verify script | Live Mercury/Box; combined umbrellas | Scope creep into control-plane x10 |
| **Slot 8 (→ GH #179)** | Kudbee SDK follow-up (~25 hermetic deepen features) | **Merged** after #178; gate `kudbee-sdk-followup` | ~20–30 commits; `thinkbox/kudbee_sdk_followup` + TS followup | Live Mercury/Box; combined umbrellas | Scope creep into control-plane x10 |
| **Slot 9 (→ GH #180)** | KUDBEECLI Phase 3 deepen (~25 hermetic CLI features) | **Merged** after #179; gate `kudbee-cli-phase3` | ~20–30 commits; `thinkbox/cli_phase3` + verify script | Live Mercury/Box; combined umbrellas | Scope creep into control-plane x10 |
| **Slot 10 (→ GH #181)** | Kudbee SDK follow-up wave 2 (~25 hermetic deepen features) | **Merged** after #180; gate `kudbee-sdk-followup-w2` | ~20–30 commits; `thinkbox/kudbee_sdk_followup_w2` + TS `followup_w2.ts` | Live Mercury/Box; KUDBEECLI Phase 4; combined umbrellas | Scope creep into control-plane x10 |
| **Slot 11 (→ GH #182)** | Receipt-chain deepen (~25 hermetic features) | **Merged** after #181; gate `receipt-chain-deepen` | ~20–30 commits; `thinkbox/receipt_chain_deepen` | Kudbee SDK/CLI lanes; combined umbrellas; live Mercury/Box | Scope creep beyond receipt-chain theme |
| **Slot 12 (→ GH #183)** | Think Job hermetic e2e deepen (~25 hermetic features) | **Merged** after #182; gate `think-job-hermetic-e2e` | ~20–30 commits; `thinkbox/think_job_e2e_deepen` | SDK/CLI/receipt-chain lanes; combined umbrellas; live Mercury/Box | Scope creep beyond Think Job theme |
| **Slot 13 (→ GH #184)** | Think Job POST /run contract deepen (~25 hermetic features) | **In flight (draft)** after #183; gate `think-job-post-run-deepen` | ~20–30 commits; `thinkbox/think_job_post_run_deepen` | SDK/CLI/receipt-chain; live Mercury/Box | Scope creep beyond POST /run theme |
| **Slot 14+** | Founder-directed | Next implementation PR after #184 merge is **not** fixed in this doc | — | Auto-sequencing without founder sign-off | — |
| **Slot 11 (optional)** | Nightly / manual `spine --e2e` workflow | Keeps deep control-plane e2e without blocking every PR | ~4–8 commits; new workflow `workflow_dispatch` + schedule | Making `--e2e` default on PR CI | Runner cost if scheduled too often |
| **Slot 11 (optional)** | Founder optional: bounded live-smoke **runbook + operator dry-run** only | When Box URL/token/LIVE_ACK exist; documents #153 path | ~6–10 commits; runbook + hermetic operator tests | Executing live proof in CI; `live_verified: true` in repo | Credential leakage in docs; cost |

**Not in default sequence (founder pull):** GitHub **#97** control-plane x10, **#103** Box Mercury v2, **#111** demo dry-run, retiring #165–#169 combined modules from spine imports (large refactor — park until CI slimmed).

---

## Recommended default next **implementation** PR: **GitHub #181** (slot 10)

Kudbee SDK follow-up wave 2 (~25 features) for `thinkbox/kudbee_sdk_followup_w2` and `apps/web/sdk/followup_w2.ts`. **#180** KUDBEECLI Phase 3 merged on main.

**After #181 merge:** founder-directed — update this roadmap snapshot before opening the next single-theme PR.

---

## Launch brief — GitHub #173 / slot 2: chronicle honesty

**Branch:** `cursor/pr173-chronicle-honesty-0660`  
**Title:** `docs(kilo): chronicle honesty after #170–#172 merge`

**Goal:** New readers and agents see one truthful story: #170 beyond-KILO lint merged, #171 roadmap docs merged, #172 CI trusts fast spine; hermetic work caps at **TEST VERIFIED**; no combined A–D umbrellas as default next work.

**In scope:**

1. Refresh root `README.md` (what Think Box AI is, post-#170 status, verify commands).
2. Align `AGENTS.md`, `docs/CONTINUITY.md`, `docs/STATUS.md`, runbook H30–H32, operator guides.
3. `thinkbox/kilo_pr173_chronicle_honesty.py` + `scripts/verify_kilo_pr173_chronicle_honesty.py` + `test_kilo_live_proof_readiness_pr173.py`.
4. Audit pass `docs/audit/passes/2026-09-24-pr173.json` with `live_verified: false`.

**Out of scope:** Lint widen (#174), CI redesign, live smoke, combined umbrellas.

**Verification:**

```bash
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr173 -v
python3 scripts/verify_kilo_pr173_chronicle_honesty.py
PYTHONUNBUFFERED=1 python3 -u scripts/verify_kilo_spine.py
python3 scripts/scan_doc_secrets.py
```

**Four-state:** CODE COMPLETE / TEST VERIFIED only.

---

## Launch brief — GitHub #172 / slot 1: CI spine-trust slimming (merged)

See git history / `docs/audit/passes/2026-09-24-pr172.json`. PR CI = unittest + fast spine + explicit beyond-KILO lint execute + secret scan.

---

## CONTINUITY pointer

When **GitHub #173** (slot 2) merges, update this roadmap snapshot and root README “Project status” date.
