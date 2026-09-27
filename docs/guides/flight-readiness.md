# Flight Readiness

Ten verification practices from flight-software engineering (NASA/JPL), mapped
to this repository. Each one answers a question a flight-software reviewer
would ask before trusting the system. Status is kept honest: an item is only
marked done when it exists as code with tests.

| # | Practice | Question it answers | Status |
|---|----------|--------------------|--------|
| 1 | **Mutation testing (IV&V)** | Do the tests actually catch bugs? | **Done (PR #266)** — see below |
| 2 | **JPL "Power of 10" audit** | Does the code follow flight coding rules (no swallowed exceptions, bounded loops, short functions, no recursion)? | **Audit + ratchet (PR #267)**: 184 existing findings recorded, new ones blocked. Burn-down pending |
| 3 | Fault-injection campaign | Under timeouts, garbage and crashes, does anything report false success? | Planned |
| 4 | 2-of-3 majority voting (TMR) | Are critical decisions voted, with disagreement reported? | Partial: CONSENSUS strategy (#264) |
| 5 | FMEA from code | What are the failure modes, how is each detected, which test proves it? | Planned |
| 6 | Requirements traceability | Which test enforces each AGENTS.md standing rule? | Planned |
| 7 | Watchdog + safe mode | Does a stalled component trip a safe mode instead of hanging? | Planned |
| 8 | Checksummed telemetry frames | Is a dropped or corrupted event detected? | Planned |
| 9 | Deterministic replay | Can any decision be reproduced byte-for-byte? | Partial: ReplayDriver, proof hashes |
| 10 | Graceful degradation ladder | Are nominal → degraded → safe-mode transitions explicit and tested? | Planned |

---

## 1. Mutation Testing

A passing test suite only shows the code agrees with the tests. Mutation
testing measures the tests: it makes many copies of a module, each with one
small realistic bug, and counts how many the suite catches ("kills").

```bash
python3 scripts/mutation_test.py thinkbox/multi_model_orchestrator.py \
    tests.unit.test_multi_model_orchestrator \
    --out data/thinkboxmd/artifacts/mutation_multi_model_orchestrator.json
```

`thinkbox/mutation_testing.py` is standard-library only. Mutations: boundary
comparisons (`>`↔`>=`, `<`↔`<=`, `==`↔`!=`, `is`/`in` flips), arithmetic
(`+`↔`-`, `*`↔`/`), `and`↔`or`, removing `not`, and flipping `True`/`False`.
Each mutant runs in its own subprocess with a timeout; a mutant that hangs
counts as killed. The harness refuses to score a module whose unmutated code
fails its own tests, since that score would mean nothing.

### First campaign: `thinkbox/multi_model_orchestrator.py`

| Run | Killed | Score | Artifact |
|-----|--------|-------|----------|
| Baseline (code on `main` at `5c7f8ed`, 41 passing tests) | 48 / 87 | **55.2%** | `mutation_multi_model_orchestrator_baseline.json` |
| After this PR (56 tests) | 80 / 87 | **92.0%** | `mutation_multi_model_orchestrator.json` |

The baseline artifact's `module_sha256` matches the file on `main`, so the
55.2% is provably the state of the code before this PR.

**What the survivors exposed.** Most were missing tests for real behavior:
consensus with exactly two providers, a 1-to-1 split being wrongly counted as
a majority, the budget never being checked to shrink as money is spent,
`failed_executions` only ever tested with zero successes, a provider that
raises inside PARALLEL/CONSENSUS, exact-boundary constraint values, and the
cost and latency formulas. Each now has a test that kills the mutant.

**A bug, not just a gap.** The success-rate update was
`0.99 + 0.01 * rate`, which resets any rate to at least 0.99 after a single
success. A provider that failed 50 times and then succeeded once looked 99.5%
healthy. It is now a moving average, `0.99 * rate + 0.01`, mirroring the
failure path's decay; a test proves one success no longer erases the history.

**The 7 remaining survivors, each with a verdict:**

| Line | Mutant | Verdict |
|------|--------|---------|
| 473 (×3) | latency jitter arithmetic in `_simulate_latency` | Simulation-only: random noise in the stand-in provider, not product behavior |
| 354, 400 | `zip(..., strict=True)` → `False` | Equivalent: both lists come from the same candidates, so lengths always match |
| 194, 195 | latency/cost score scaling | Unspecified design: each flip keeps that factor's ordering but changes the latency-vs-cost tradeoff, which no requirement specifies. Open question, not pinned |

Excluding the 2 provably equivalent mutants, the effective score is 80/85
(94.1%). The raw 92.0% is the reported number.

---

## 2. JPL "Power of 10" Audit

Gerard Holzmann's ten rules (JPL, 2006) were written for safety-critical C.
Four translate directly to Python and are enforced; the rest are mapped
honestly rather than claimed.

| JPL rule | Here |
|----------|------|
| 1. Simple control flow, no recursion | **P1**: no direct recursion (a function or `self.`/`cls.` method calling itself). Mutual recursion is not detected |
| 2. Fixed upper bound on loops | **P2**: `while True:` must contain a `break` (of that loop), `return` or `raise`. Loops that are bounded only by task cancellation are flagged |
| 3. No dynamic allocation after init | N/A: Python manages memory |
| 4. Functions fit on one page | **P4**: at most 60 lines, docstring included |
| 5. Two assertions per function | N/A: asserts vanish under `python -O`; this repo raises typed errors instead |
| 6. Smallest data scope | N/A: not statically decidable here |
| 7. Check every return value | **P7**: no bare `except:`, and no `except Exception`/`BaseException` whose body is only `pass`/`continue`/`...` (AGENTS.md §2.5) |
| 8. Limited preprocessor | N/A |
| 9. Restricted pointers | N/A |
| 10. All warnings, static analysis clean | Covered by the ruff/mypy/bandit lint step in CI |

```bash
python3 scripts/power_of_ten_audit.py                  # exit 1 on any new violation
python3 scripts/power_of_ten_audit.py --write-baseline # after fixing some, lock the gain in
```

`thinkbox/power_of_ten.py` is standard-library AST analysis over `thinkbox/`,
`core/` and `backend/` (about 1100 files, about 3 s).

### First audit (on `main` at `d940160`)

| Rule | Findings | What they are |
|------|----------|---------------|
| P1 recursion | 20 | Mostly tree walkers (`redact_mapping`, `validate_json`, DFS cycle detection), several copy-pasted across SDK packages |
| P2 unbounded loops | 5 | SSE/WebSocket streams and a stress-test sampler that end only on client disconnect or task cancellation |
| P4 long functions | 128 | Longest: `validate_slot_registry_document` (382 lines), `ThinkBoxEngine.execute_goal` (229), `PRLifecycleOrchestrator.step` (221) |
| P7 swallowed exceptions | 31 | 10 in `thinkbox/engine.py` alone, plus `core/runtime/loop.py` `AgentLoop.run` and the dashboard/telemetry emitters. Each is a direct AGENTS.md §2.5 violation |
| **Total** | **184** | `data/thinkboxmd/artifacts/power_of_ten_baseline.json` |

**The ratchet.** Existing findings are recorded in the baseline, keyed by
rule, file and function name rather than line number, so unrelated edits do
not churn it. `tests/unit/test_power_of_ten.py::TestRepoRatchet` runs in the
normal test suite and fails on any finding beyond the baseline, including a
second violation added to a function that already has one. The count can
only go down.

**What this PR does not do.** It fixes none of the 184. The 31 P7 findings
are the priority: a swallowed exception is how a failure turns into a
silent success, which AGENTS.md §4.4 forbids. They are the next burn-down.

**The auditor, checked by item 1.** Mutation testing the auditor's own tests
first scored 31/40; the survivors showed untested pycache skipping, the
`fixed` count, parse-error line numbers and baseline round-tripping. After
adding tests: **39/40 (97.5%)**. The survivor is `sort_keys=True` →
`False` when writing the baseline, which only reorders keys in the JSON
summary. It is effectively equivalent.
Artifact: `data/thinkboxmd/artifacts/mutation_power_of_ten.json`. The
auditor also passes its own audit (a test asserts it).
