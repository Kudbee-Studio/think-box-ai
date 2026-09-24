# KILO post-#170 PR roadmap (implementation slots)

**GitHub #171** (draft) is **this planning PR** only. The table below uses **implementation slots**; the next coding PR is expected as **GitHub #172** (CI spine-trust).

**Status:** Planning artifact (not an implementation gate).  
**Baseline:** `main` after GitHub **#170** (beyond-KILO lint readiness, merged).  
**Four-state cap:** Hermetic work stays **CODE COMPLETE / TEST VERIFIED** only until founder-run Live proof + artifacts (`#152`/`#153` path).

**Founder constraints (summary):**

- One open **implementation** PR at a time; sequence below accordingly.
- No new combined post-#N **A–D umbrella** lanes (cost: nested evaluators, multi-minute CI hangs seen in #165–#169).
- Spine **fast-by-default** (`verify_kilo_spine.py`; nested e2e opt-in via `--e2e`, from #168).
- Lint: widen `LINT_SCOPE_REL_PATHS` in **single-theme** follow-ons (#170 operator guide).
- Live proof: optional later lane; requires Box URL + token + `THINKBOX_SWARM_LIVE_ACK` — never fake `live_verified: true`.

---

## Current snapshot (post-#170)

| Area | State |
|------|--------|
| Beyond-KILO lint | Gate `beyond-kilo-lint-readiness`; ruff/mypy/bandit on **two** modules only (`thinkbox/beyond_kilo_lint.py`, `thinkbox/kilo_beyond_kilo_lint.py`) |
| Spine | `verify_kilo_spine.py` aggregates 28 blocks including #169 umbrella + #170 lint (static lint in spine unless `KILO_BEYOND_KILO_LINT_EXECUTE=1`) |
| CI | `.github/workflows/test.yml` runs **unittest discover** + **spine** + **~35 duplicate** `verify_kilo_*` scripts + `verify_kilo_beyond_kilo_lint.py` after `pip install -e ".[lint]"` |
| Chronicle gap | `docs/CONTINUITY.md`, `AGENTS.md` KILO table still label **#170 draft** (should read **merged**) |
| Live proof | Season #141–#150 closed hermetically; `live_verified: false` on all spine audit passes including `docs/audit/passes/2026-09-23-pr170.json` |
| Deferred product lanes | KUDBEECLI Phase 2 (**#129** draft), control-plane x10 (**#97**), PR **#103** Box Mercury v2 draft — **out of this spine sequence** unless founder reprioritizes |

---

## Sequenced PR roadmap

| Slot | Theme (one line) | Why now | Size | Out of scope | Risks |
|------|------------------|---------|------|--------------|-------|
| **Slot 1 (→ GH #172)** | CI spine-trust slimming (dedupe workflow verify scripts) | CI runs spine **and** nearly every gate script twice; wall-clock + flake surface; aligns with (a) spine health | ~8–15 commits; `test.yml`, `kilo_post_season_harden` checklist/docs, `test_kilo_live_proof_readiness_pr172` | Removing gate modules; combined umbrellas; live smoke | Must keep `verify_kilo_beyond_kilo_lint.py` with `EXECUTE=1` in CI; post_season checklist drift |
| **Slot 2 (→ GH #173)** | Chronicle honesty sync (#170 merged + post-170 era) | AGENTS/CONTINUITY/runbook H30 vs “draft”; audit index; (c) docs honesty | ~5–10 commits; docs + hermetic spine-doc tests only | Production code except test fixtures for doc paths | Low; avoid affirmative LIVE claims |
| **Slot 3 (→ GH #174)** | Lint scope wave 1 (spine + hermetic subprocess helpers) | #170 explicitly deferred widening; (b) gradual lint | ~6–12 commits; `LINT_SCOPE_REL_PATHS` + ruff/mypy fixes on new files | Whole `thinkbox/` tree; `core/` runtime | Mypy time; keep `--follow-imports=skip` |
| **Slot 4 (→ GH #175)** | Lint scope wave 2 (live-proof readiness spine modules) | Next bounded slice: `kilo_live_proof_readiness`, `kilo_env_matrix`, `kilo_hermetic_gate_memo` | ~8–15 commits | Combined lanes; importing provider SDKs | Same as #173 |
| **Slot 5 (→ GH #176)** | Control-plane receipt-chain single deepen (412/precondition only) | Mature receipt/ETag stack (#155–#161); one HTTP edge theme | ~10–18 commits; `receipt_chain_query` / conditional GET tests | END_LINK UX; dashboard bind; api_ops combined | No live Mercury; hermetic e2e only if scoped |
| **Slot 6 (→ GH #177)** | Control-plane ops harden slice (rate-limit / error shape only) | Thin follow-on after #157/#161 without post-NNN combined pattern | ~8–14 commits | New dashboard pages; swarm/gov themes | Duplicating #169 ops deepen |
| **Slot 7 (→ GH #178)** | Think Job hermetic e2e deepen (F023+ control-plane poll/SSE) | CONTINUITY: F023 on main; live API path still uncovered | ~12–20 commits; `tests/e2e/` only + minimal route stubs | Live `POST /run` Mercury; GPU | Nested e2e — **not** in default spine; document `--e2e` |
| **Slot 8 (→ GH #179)** | KUDBEECLI Phase 2 merge prep (single theme: persist + trace list) | #128 merged; #129 draft ages; isolate persist/trace before REPL/live gate | ~15–25 commits | `swarm live` HTTP; agent register | Scope creep into Phase 3 |
| **Slot 9 (→ GH #180)** | Nightly / manual `spine --e2e` workflow | Keeps deep control-plane e2e without blocking every PR | ~4–8 commits; new workflow `workflow_dispatch` + schedule | Making `--e2e` default on PR CI | Runner cost if scheduled too often |
| **Slot 10 (→ GH #181)** | Founder optional: bounded live-smoke **runbook + operator dry-run** only | When Box URL/token/LIVE_ACK exist; documents #153 path | ~6–10 commits; runbook + hermetic operator tests | Executing live proof in CI; `live_verified: true` in repo | Credential leakage in docs; cost |

**Not in default sequence (founder pull):** GitHub **#97** control-plane x10, **#103** Box Mercury v2, **#111** demo dry-run, retiring #165–#169 combined modules from spine imports (large refactor — park until CI slimmed).

---

## Recommended default next **implementation** PR: **GitHub #172** (slot 1)

See launch brief below (coordinator handoff).

---

## Launch brief — GitHub #172 / slot 1: CI spine-trust slimming

**Branch:** `cursor/pr172-ci-spine-trust-slim-8f6c`  
**Title:** `chore(ci): dedupe KILO gate invocations; trust fast spine verify`

**Goal:** Make PR CI match the intended operator model: full unittest suite + **one** fast spine pass + explicit lint execute + secret scan. Remove redundant per-gate `python3 scripts/verify_kilo_*` lines that only repeat `spine_contract_summary` / `hermetic_operator_ok` already enforced by `verify_kilo_spine.py`.

**In scope:**

1. Edit `.github/workflows/test.yml` KILO step to approximately:
   - `PYTHONUNBUFFERED=1 python3 -u scripts/verify_kilo_spine.py` (default fast)
   - `pip install -e ".[lint]"` + `KILO_BEYOND_KILO_LINT_EXECUTE=1` + `python3 scripts/verify_kilo_beyond_kilo_lint.py`
   - Keep `python3 -m unittest discover -s tests -t .` and `scan_doc_secrets.py`
2. Update `data/kilo_post_season_harden/checklist.json` + `thinkbox/kilo_post_season_harden.py` **only if** checklist asserts per-script CI lines (today validates spine + unittest + secrets; extend with `beyond_kilo_lint` snippet if needed).
3. Add `tests/unit/test_kilo_live_proof_readiness_pr172.py` asserting CI manifest contract (no combined umbrella).
4. Audit pass `docs/audit/passes/2026-09-24-pr172.json` with `live_verified: false`.
5. Touch `docs/runbooks/kilo-live-proof-readiness.md` § Hermetic prerequisites with **H31** CI-trust note (optional one paragraph).

**Out of scope:** Deleting `scripts/verify_kilo_*.py` (operators still run them locally). Changing spine block list. Lint scope widen (slot 3). Live proof. Chronicle honesty (slot 2) unless founder batches.

**Verification:**

```bash
python3 -m unittest discover -s tests -t .
PYTHONUNBUFFERED=1 python3 -u scripts/verify_kilo_spine.py
pip install -e ".[lint]"
KILO_BEYOND_KILO_LINT_EXECUTE=1 python3 scripts/verify_kilo_beyond_kilo_lint.py
python3 scripts/scan_doc_secrets.py
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr172 -v
```

**Four-state:** CODE COMPLETE / TEST VERIFIED only.

**Risk notes:** Prove equivalence — before merge, run old and new CI step lists once on branch and compare spine JSON `hermetic_operator_ok` fields. Watch PR170 lint job still executes tools in CI.

---

## CONTINUITY pointer

When **GitHub #172** (slot 1) merges, update `docs/CONTINUITY.md` CURRENT STATE and CI notes in this roadmap.
