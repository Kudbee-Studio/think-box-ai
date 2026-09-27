# Flight Readiness

Ten verification practices from flight-software engineering (NASA/JPL), mapped
to this repository. Each one answers a question a flight-software reviewer
would ask before trusting the system. Status is kept honest: an item is only
marked done when it exists as code with tests.

| # | Practice | Question it answers | Status |
|---|----------|--------------------|--------|
| 1 | **Mutation testing (IV&V)** | Do the tests actually catch bugs? | **Done (PR #266)** — see below |
| 2 | JPL "Power of 10" audit | Does the code follow flight coding rules (no swallowed exceptions, bounded loops, short functions, no recursion)? | Planned |
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
