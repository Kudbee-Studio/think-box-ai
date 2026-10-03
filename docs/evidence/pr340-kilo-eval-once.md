# PR #340: the KILO gate chain, evaluated once per call, and what the timeouts were hiding

Code head tested by the gates below: `1e4690c8`. The commits after it change only documentation (this file, the files it links, `AGENTS.md`, `docs/INDEX.md`) and add the `act` log.

#339 left the KILO spine tests failing on `main`: 51 timed out and 61 failed in the 106 files that mention KILO. This PR finds why, in the order the evidence arrived, and fixes each cause. Nothing here changes what a gate decides except where a gate was wrong; `summary-equality.txt` proves that, value by value.

## What was wrong

| Cause | Evidence | Fix | Commit |
|---|---|---|---|
| **The same pure evaluation repeated.** Each KILO gate re-runs the gates beneath it, and each of those summaries runs them again. One `spine_contract_summary()` executed 376,591 gate functions for 176 distinct ones (`evaluate_env_matrix` alone 54,426 times) and took 120 s on a quiet machine (up to 200 s when busy). Every spine test hit its timeout; that is also what crashed pytest in #338's and #339's first full runs | the profile below | `@evaluated_once`: a gate function is evaluated once per distinct (arguments, environment) inside the outermost decorated call, and the cache dies with that call. Applied to all 220 gate functions in 78 modules | `4ed7ccf3` (the mechanism), `19a8f2d0` (the 220 decorators) |
| **One root cause behind the chain.** With the gates fast enough to run, 19 of the summary's blocks fail and exactly one is the cause: PR #172's CI manifest (which PR #151 delegates to) demands six Python steps of `.github/workflows/test.yml`, and #308 removed those steps and then the whole Python job. The other 18 report "prior layer failed" | `summary-equality.txt` | the required steps apply only to a workflow that runs Python (`ci_runs_python`); the forbidden patterns (default `--e2e`, redundant verify scripts) always apply; both summaries report whether the manifest applied. A Python job that returns without the steps fails the gate again | `cc999189` |
| **The beyond-KILO lint lane was red and nobody could see it.** `ruff check` 21 findings, `ruff format --check` 31 of 38 modules, `bandit` 10 issues, `mypy` clean. It went red when #280 widened the ruff rule set; nothing re-ran it once #308 took the KILO steps out of CI, and its tests sat behind the timeouts | `lint-lane-before-after.txt` | 21 ruff findings rewritten with the same behavior (the false positives, S104 and S105, carry a reason, `noqa` and `nosec`), 10 bandit issues removed or justified, 31 files formatted (AST identical, `ast-equivalence.txt`) | `5b1389c4`, `70110f01` |
| **PR #173 required four phrases in the README** that came from the KILO-era process ("one implementation PR at a time", "single-theme", "fast-by-default", "--e2e"). #316 rewrote the README for the product and AGENTS.md 0.2 replaced that process, so requiring the first phrase would make the README contradict current policy | `test_kilo_pr173_readme_scope.py` (3 of 5 failed before) | the marker requirement is removed; the four pointers (roadmap, `verify_kilo_spine.py`, `verify_kilo_beyond_kilo_lint.py`, "TEST VERIFIED") and the scans for forbidden and affirmative live claims stay | `6ee66722` |
| **A process-wide memo that served stale verdicts.** `kilo_hermetic_gate_memo.py` (2026-09-23) kept one module-level dict keyed by gate id and environment "unless cleared"; only one test file cleared it. It was wired into 6 of the 220 gates, so it only partly cut the recursion, and it had no invalidation boundary: evaluate the PR #169 gate, point its `REPO_ROOT` at an empty directory, and the second call still answered `ok=True` | `test_kilo_gate_staleness.py` (failed before: "the checklist and audit files are gone; a cached verdict hid that") | the module is deleted, its six call sites call their `evaluate_*` directly, and a test bans process-wide gate caches by name | `1e4690c8` |

## Where the time went (`kilo-profile-by-category.txt`)

One `spine_contract_summary()` on `main` under cProfile: 197.7 s of self-time, 224,540,958 function calls. Self-time is the time in a function's own code, so the categories add up.

| Category | Self-time | Share |
|---|---|---|
| gate logic (`thinkbox/kilo_*.py` own code) | 38.2 s | 19.3% |
| filesystem (open, read, stat, path handling) | 35.6 s | 18.0% |
| SQLite (the `_migrate` of five `:memory:` stores, 69,552 times) | 34.6 s | 17.5% |
| interpreter and builtins | 27.3 s | 13.8% |
| JSON encode and decode | 21.8 s | 11.0% |
| documentation scanning (704,559 regex searches) | 15.1 s | 7.6% |
| `os.environ` lookups | 12.3 s | 6.2% |
| support modules (`thinkbox/*`, not gates) | 11.8 s | 6.0% |
| network | 1.1 s | 0.6% |
| subprocesses | 0.0 s | 0.0% |

The "network" is `urllib.parse.urlparse` re-parsing the same URL strings 188,688 times; no socket function was called. Nothing was spawned: the nested-e2e gate only asks whether it is enabled. There is no hot spot. The top five single contributors (`executescript` 18.8 s, `re.search` 12.8 s, `execute` 11.5 s, `json.iterencode` 8.0 s, `io.open` 5.4 s) are each cheap per call and were called 10^5 to 10^6 times.

**Necessary versus redundant.** One pass over the 176 distinct gate functions is the necessary work. 319 of the 376,591 executions are the first for their inputs; the other 99.92% are repeats of a pure evaluation. The same call was 197.7 s of self-time under the profiler and is now 1.1 s of wall time under it (99.4% less).

## One gate, traced (`mid-chain-gate-trace.txt`)

`evaluate_live_smoke_evidence` (PR #152): it reads only its arguments directly (the repository comes through helpers), calls one gate (`hermetic_post_season_harden_operator_check`, the root of the chain), is called by two (the operator check and the gate-closed check), mutates nothing, and the gate call graph (220 nodes) has no cycle. It ran **7,525 times** in one summary on `main` (7,524 of them from the operator check), and **3 times** now. The explosion is not fan-out; it is depth times repetition, because each of about 176 layers re-runs everything beneath it.

## Purity, inspected before the cache was designed (`purity-inventory.txt`)

- Of 605 functions in `thinkbox/kilo_*.py`, nine contain a statement with an effect outside the function, and none is a gate: four are the live-smoke operator's file helpers (two write an artifact, two delete what was written before returning), one starts a bounded subprocess, one sets `KILO_SPINE_FAST` and restores it in `try/finally`, two read the clock, one sets an environment variable and no gate reaches it.
- The SQLite behind 17.5% of the time is not shared state: every store the hermetic checks build is `:memory:`.
- The tests that exist patch module attributes (`detect_lint_tool`, one gate function) and `REPO_ROOT` around a single outermost call; none reloads a module or writes a file for a gate to read.

So a gate's verdict depends on the repository files and the environment and nothing a sibling leaves behind. What that decided: the cache lives **inside one outermost call** and dies with it (no process-wide cache: a test, or an operator editing a file between two runs, must see fresh evaluations), per thread; the key is the function, its arguments and the **whole environment** (`KILO_SPINE_FAST` is set and restored inside a call, and helpers read `os.environ` directly); results are **deep-copied** on the way out; an exception is never cached; an argument that cannot be keyed makes the call run directly.

## Is the cached evaluation the same evaluation? (`summary-equality.txt`)

The whole `spine_contract_summary()` dictionary, flattened to leaf values, in three trees:

| Comparison | Result |
|---|---|
| `main` against **main plus the two cache commits only** | **byte-identical**: 53,341 bytes, 1,274 leaf values, 0 differ |
| `main` against this branch | 202 differ, all one direction: 72 `gate_closed_default` / `hermetic_operator_ok` flip False to True, 13 prior-layer flags flip False to True, 103 violation codes disappear, 12 dashboard slots go `stale` to `bound`, plus the new `ci_manifest_applies` field and one renamed module path. **Nothing goes from True to False**; 19 blocks that failed on `main` pass; no block fails here |

The two mechanical commits are proven meaning-preserving separately: `ruff format` changed 31 files and the decorators 78, and in every one the AST (docstring text aside, decorator and import removed) is identical before and after (`ast-equivalence.txt`).

## Before and after

One `spine_contract_summary()` (`gate-executions-before-after.txt`):

| | `main` `253e7154` | this branch `1e4690c8` |
|---|---|---|
| gate-function executions | 376,591 | **319** |
| most executions of one gate function | 54,426 (`evaluate_env_matrix`) | **8** |
| function calls | 224,540,958 | 1,957,154 |
| SQLite store migrations | 69,552 | 48 |
| wall time, no profiler | **120.6 s** | **0.5 s** (five runs, byte-identical summaries) |

The KILO test group (the 106 files that mention KILO, plus the 5 new ones; `kilo-group-final.txt`):

| | `main` (one process per file, 20 s each) | this branch (one process) |
|---|---|---|
| tests | 839 | 868 (839 + 29 new) |
| passed | 727 | **868** |
| failed | 61 | 0 |
| timed out | 51 | 0 |
| wall time | the 51 timeouts alone are 17 minutes | 65 s; the slowest test 3.0 s |

`scripts/verify_kilo_spine.py` exits 0 in 0.65 s; `KILO_BEYOND_KILO_LINT_EXECUTE=1 scripts/verify_kilo_beyond_kilo_lint.py` exits 0 in 3.0 s.

## Gates (AGENTS.md 0.1)

1. **Local checks.** `apps/web` is unchanged: its `npm test` 549/549 is the `act` run below. Python: the **whole `tests/unit` suite as one process** passes except the Power of 10 ratchet (4,680 passed, 1 failed, 117 s, no `INTERNALERROR`; `main` could not be run as one process, `full-unit-suite.txt`), the KILO group 868/868 above, the lane's own ruff, `ruff format --check`, mypy (38 files) and bandit all clean on the 38-module scope, 29 new tests with 10 mutations caught (`mutation-checks.txt`; the earlier sets are in the commit messages).
2. **Local CI (`act`).** `test` / `web-typecheck` (the only workflow): green at `1e4690c8`, tests 549/549, skipped none (act 0.2.89, real clone with `origin` on GitHub). Log: `docs/evidence/ci-local/feat-pr340-p3.12-kilo-eval-once-act.log`. There is no workflow for the Python tests.
3. **CodeQL against `main`.** Python, `python-code-scanning.qls` (CodeQL 2.27.1), one database per tree: `main` 17 alerts, this PR 17, **0 new, 0 gone** (`codeql-compare.txt`; SARIF `pr340-kilo-eval-once/codeql-pr340-python.sarif`). JavaScript: no file under `apps/web` changed, so the #337 scan stands.
4. **Evidence.** This file, the folder `pr340-kilo-eval-once/`, and the PR body.
5. **Diff review.** No secrets, no `.db`/`.env` files; 0.4 guardrails intact; no route, workflow or `apps/web` file changed. 91 files: 81 `thinkbox/kilo_*.py` modules (79 changed, `kilo_eval_scope.py` new, `kilo_hermetic_gate_memo.py` deleted; 78 carry the decorator and its import, 31 were formatted), `thinkbox/beyond_kilo_lint.py` (the scope-list path and three ruff rewrites), the two scope manifests (one path swapped), `docs/guides/kilo_enterprise_editing.md` (commitment 24), `tests/unit/test_kilo_beyond_kilo_lint.py` (7 lines removed: it cleared the deleted memo), and five new test files. Beyond the decorator the logic changes are the two CI-manifest modules, `kilo_pr173_chronicle_honesty.py`, the lint fixes in 10 modules and the six call sites that used the deleted memo.

## Four-state table

| Item | CODE | TEST | LIVE | PROD |
|---|---|---|---|---|
| Gates evaluated once per call | complete | verified (29 tests; 10 mutations caught; 1,274 values identical to `main` with the cache alone) | n/a (no live call involved) | UNPROVEN (no Python job in CI; these tests run only locally) |
| CI manifest applies to a Python workflow only | complete | verified (8 tests; mutations) | n/a | the six steps are not required of the web-only workflow by the founder's #308 decision; restoring them needs a token with the `workflow` scope |
| Beyond-KILO lint lane clean | complete | verified with the lane's own code on both trees | n/a | UNPROVEN (CI does not run it) |
| PR #173 README check | complete | verified (5 tests; mutations) | n/a | n/a |
| Power of 10 ratchet, load time | not changed here | the ratchet test still fails (6 functions) | n/a | next PRs |
| GitHub CI | | | | UNPROVEN (Actions billing-locked; no Python workflow exists) |

## Notes

- `ci_runs_python` is a text match (`setup-python`, `python`, `pip` anywhere in the workflow, a comment included). A comment that says "python" in a web-only workflow turns the six requirements back on; that errs towards enforcing.
- The cache removes repetition, not layering: each gate still calls the gates beneath it. After this PR that costs 319 executions rather than 376,591; a gate evaluated from two threads runs twice (the scopes are per thread).
- The cache key builds a sorted tuple of the environment on every wrapper call (574 calls per summary, about 137,000 `os.environ` reads). That is part of the 0.5 s, and measured to be small.
- The gates write transient files under `data/thinkboxmd/artifacts/` (the live-smoke operator's round trip), then delete them. An interrupted run on `main` could have left one; none was found in any tree here. The cache makes the round trip happen once per distinct input instead of thousands of times.
- Not in this PR: the six functions over 60 lines that the Power of 10 ratchet reports (`SSHCloudExecutionProvider.run` 81, `with_recovery` 92 and its `decorator` 72, `execute_governed_job_command` 64, `UpCloudSSHExecutionAdapter.execute` 125, `resume_queued_think_job` 74), and the dashboard load time; both are separate PRs.
- Commit count: 7 commits change code or tests, plus the evidence commits; the founder asked for about 20 per PR. The mechanical ones (decorators, formatting) are each one commit because each is one change, and I did not split them to make a number.
