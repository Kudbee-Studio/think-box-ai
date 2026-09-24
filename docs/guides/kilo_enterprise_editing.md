# KILO enterprise editing

**Enterprise editing** is how this repository treats changes to **canonical narrative and
contract surfaces** — not casual copy edits, but governed updates to the spine agents and
operators rely on (`AGENTS.md`, `docs/CONTINUITY.md`, runbooks, audit passes, hermetic gate
modules). Each edit is **evidence-shaped**: four-state capped, audit-json tagged, test-backed,
and sequenced through single-theme PRs. It is the editorial layer of the KILO control fabric:
admission before merge, chronicle after merge, linters on the modules that encode truth.

Think Box AI applies the same discipline to **code contracts** in PR **#174** lint scope wave 1:
spine and hermetic-helper modules run under ruff, mypy (`--follow-imports=skip`),
and bandit — the mechanical enforcement behind honest editing. PR **#174** wave 1
(25 modules) and PR **#175** wave 2 (+12 live-proof readiness modules, 37 total).

---

## Twenty-five major commitments (wave 1)

These commitments apply to enterprise editing and to the **#174** lint scope wave. They are
not Live proof; hermetic work stays **TEST VERIFIED** max (`live_verified: false` on audits).

| # | Commitment |
|---|------------|
| 1 | **Single-theme PRs** — one implementation lane per PR; no combined post-#N A–D umbrellas by default. |
| 2 | **One open implementation PR** at a time unless the founder batches explicitly. |
| 3 | **Four-state honesty** — never claim KILO LIVE VERIFIED or PRODUCTION READY without founder artifacts. |
| 4 | **Chronicle sync** — `CONTINUITY`, `AGENTS`, `STATUS`, and roadmap agree on merged vs draft PRs. |
| 5 | **Audit passes** — every spine milestone ships JSON under `docs/audit/passes/` with `live_verified: false` until earned. |
| 6 | **Spine fast-by-default** — `verify_kilo_spine.py` without `--e2e` on every PR CI run. |
| 7 | **Explicit lint execute** — CI runs `KILO_BEYOND_KILO_LINT_EXECUTE=1` on the scoped path set. |
| 8 | **Gradual lint widen** — expand `LINT_SCOPE_REL_PATHS` in waves (#174, #175), not whole-tree at once. |
| 9 | **Mypy bounded** — `--follow-imports=skip` on gate modules until types stabilize. |
| 10 | **No secrets in docs** — `scan_doc_secrets.py` stays green; redact operator examples. |
| 11 | **Operator scripts remain** — slim CI does not delete `scripts/verify_kilo_*`; spine aggregates contracts. |
| 12 | **Evidence labels** — simulated / inferred / verified / physically_measured on capability claims. |
| 13 | **Provider independence** — no provider SDKs at runtime layer; configuration swaps providers. |
| 14 | **Governance by default** — tools and side effects require permission; RESTRICTED without explicit level. |
| 15 | **Memory discipline** — no transient UI state or speculative claims in organizational memory. |
| 16 | **Layer discipline** — imports only from layers beneath; cross-layer imports are bugs. |
| 17 | **Hermetic gates first** — readiness PRs prove contracts before Live operator paths. |
| 18 | **Doc-contract tests** — chronicle and lint waves ship `test_kilo_live_proof_readiness_prNNN` modules. |
| 19 | **Roadmap as source of slots** — `docs/roadmaps/kilo-post-170-pr-roadmap.md` sequences #172+. |
| 20 | **README for new readers** — root README states post-#170 status and verify commands (real script names). |
| 21 | **Runbook H-family** — hermetic prerequisites H1–H32 stay aligned with merged PR numbers. |
| 22 | **No fake Box smoke** — Live proof requires founder Box URL, token, and `THINKBOX_SWARM_LIVE_ACK`. |
| 23 | **Bounded subprocess** — hermetic lint and spine helpers use `kilo_hermetic_subprocess` timeouts. |
| 24 | **Memoized hermetic checks** — nested gate evaluators use `kilo_hermetic_gate_memo` to avoid CI hangs. |
| 25 | **Wave manifest frozen** — `data/kilo_beyond_kilo_lint/wave1_scope.json` lists exactly 25 paths; gate tests enforce parity. |

---

## Wave 1 scope (25 modules)

See `data/kilo_beyond_kilo_lint/wave1_scope.json`. Verify:

```bash
pip install -e ".[lint]"
KILO_BEYOND_KILO_LINT_EXECUTE=1 python3 scripts/verify_kilo_beyond_kilo_lint.py
python3 scripts/verify_kilo_pr174_lint_scope_wave1.py
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr174 -v
```

**Four-state:** CODE COMPLETE / TEST VERIFIED only on this wave.
