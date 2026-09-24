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

## Current snapshot (post-#175)

| Area | State |
|------|--------|
| Beyond-KILO lint | Gate `beyond-kilo-lint-readiness`; **38** scoped modules (v3) — **#174** + **#175** merged |
| Spine | `verify_kilo_spine.py` aggregates 28 blocks including #169 umbrella + #170 lint (static lint in spine unless `KILO_BEYOND_KILO_LINT_EXECUTE=1`) |
| CI | **#172** (merged): unittest + fast spine + beyond-KILO lint execute + secret scan |
| Chronicle | **#173–#175** merged; lint waves 1–2 complete |
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
| **Slot 6 (→ GH #177)** | Control-plane ops harden slice (rate-limit / error shape only) | Thin follow-on after #157/#161 without post-NNN combined pattern | ~8–14 commits | New dashboard pages; swarm/gov themes | Duplicating #169 ops deepen |
| **Slot 7 (→ GH #178)** | Think Job hermetic e2e deepen (F023+ control-plane poll/SSE) | CONTINUITY: F023 on main; live API path still uncovered | ~12–20 commits; `tests/e2e/` only + minimal route stubs | Live `POST /run` Mercury; GPU | Nested e2e — **not** in default spine; document `--e2e` |
| **Slot 8 (→ GH #179)** | KUDBEECLI Phase 2 merge prep (single theme: persist + trace list) | #128 merged; #129 draft ages; isolate persist/trace before REPL/live gate | ~15–25 commits | `swarm live` HTTP; agent register | Scope creep into Phase 3 |
| **Slot 9 (→ GH #180)** | Nightly / manual `spine --e2e` workflow | Keeps deep control-plane e2e without blocking every PR | ~4–8 commits; new workflow `workflow_dispatch` + schedule | Making `--e2e` default on PR CI | Runner cost if scheduled too often |
| **Slot 10 (→ GH #181)** | Founder optional: bounded live-smoke **runbook + operator dry-run** only | When Box URL/token/LIVE_ACK exist; documents #153 path | ~6–10 commits; runbook + hermetic operator tests | Executing live proof in CI; `live_verified: true` in repo | Credential leakage in docs; cost |

**Not in default sequence (founder pull):** GitHub **#97** control-plane x10, **#103** Box Mercury v2, **#111** demo dry-run, retiring #165–#169 combined modules from spine imports (large refactor — park until CI slimmed).

---

## Recommended default next **implementation** PR: **GitHub #176** (slot 5)

Control-plane receipt-chain single deepen (412/precondition only). Lint waves **#174–#175** merged on main.

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
