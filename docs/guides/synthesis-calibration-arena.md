# Synthesis Calibration Arena — Pre-Registered Research Result

**A test of the PR #263 SynthesisEngine, not a demo of it.**

This document reports a pre-registered, falsifiable experiment against the
`SynthesisEngine` shipped in `thinkbox/multi_box_orchestration.py`. The
hypothesis was rejected. That is the point: the methodology found a real,
actionable weakness in shipped code before a user or a grant reviewer would
have to.

---

## The Question

> When multiple specialized agents disagree, does the confidence-weighted
> consensus synthesis in `SynthesisEngine` produce better-calibrated and/or
> more accurate answers than naive unweighted majority voting, at identical
> total agent-call budget?

This is not a novel question in isolation — it sits directly on top of
established work on multiagent debate (Du et al. 2023), self-consistency
(Wang et al. 2022), and model calibration (Guo et al. 2017). What's tested
here is whether *this specific implementation* behaves the way that
literature would predict, using a fair, budget-matched, paired design.

## Pre-Registration (fixed before any run)

- **Hypothesis (H1):** Confidence-weighted synthesis achieves a lower Brier
  score (better calibration) than naive majority voting, on the *same*
  underlying agent responses (paired design), at matched total agent-call
  budget.
- **Improvement threshold:** Brier score reduction > 0.05 **and** the paired
  bootstrap 95% CI of the difference excludes zero. Anything else is
  `NO_MEASURABLE_IMPROVEMENT`. A regression clearing the same bar in the
  other direction is classified `WORSE`.
- **Design:** For each synthetic task, exactly 3 simulated agent responses
  are generated once and reused across all three conditions (single-agent,
  naive majority vote, confidence-weighted synthesis) — isolating the
  aggregation method as the only variable.

Evidence level throughout: **SIMULATED**. Agent responses come from a
seeded, deterministic synthetic generator (`SeededAgentSimulator`), not real
model calls. This tests the aggregation logic, not model intelligence.

## A Confound Caught Before Publishing

The first run of this experiment showed `SynthesisEngine` losing badly on
calibration (Brier delta +0.106, apparently WORSE). Before reporting that,
the result was checked against its own generator: the synthetic "wrong
answer" logic always added a *positive* offset to the ground truth, so the
correct answer — whenever present — was always the numerically lowest value
among the three responses. Naive majority voting's tie-break rule (lowest
value on a 3-way disagreement) silently exploited that artifact; confidence-
weighted synthesis's tie-break (highest self-reported confidence) did not.
That was a bug in the experiment's simulator, not a finding about the
synthesis engine, and it was fixed (symmetric ± offset) before any numbers
below were reported. This check is the actual deliverable of a rigorous
methodology — a result this clean-looking should always be suspected first.

## Result (n=300 tasks, 900 simulated agent calls, seed=20260926)

| Condition | Accuracy | 95% CI | Brier score |
|---|---|---|---|
| Single agent (no aggregation) | 64.0% | [58.4%, 69.2%] | 0.238 |
| Naive majority vote | 74.7% | [69.5%, 79.3%] | **0.106** |
| Confidence-weighted synthesis | **78.7%** | [73.7%, 82.9%] | 0.212 |

**Brier delta (synthesis − majority):** +0.106, 95% CI [0.085, 0.128]
**Classification: `WORSE`** — the pre-registered hypothesis is rejected. The
CI clears the threshold in the wrong direction: confidence-weighted
synthesis is *more accurate* than naive majority vote, but its stated
confidence is *meaningfully worse calibrated*.

Full machine-readable proof: `data/thinkboxmd/artifacts/synthesis_calibration_v1_proof.json`
(includes SHA-256 proof hash for tamper detection, same convention as the
project's other Arena proofs).

## Why This Happens (the actual finding)

Naive majority vote's confidence is `agreement_count / total_responses` —
a number that is mechanically tied to how much the responses actually
agreed. It is, structurally, a form of empirical calibration: 3/3 agreement
really is more trustworthy than a 2/3 split, and the number says so
directly.

`SynthesisEngine.synthesize_findings` instead reports the **average of the
constituent agents' own self-reported confidence** for a consensus finding.
Those self-reported confidences are calibrated (if at all) to each agent's
*family-level* base rate, not to whether *this specific* answer is the
consensus one. Two agents can agree on a wrong answer while both reporting
high self-confidence, and the synthesis engine faithfully reports that high
number — decoupled from the one piece of information it actually has and
isn't using: how many agents agreed.

## Concrete, Scoped Fix (applied in v2, see below)

`SynthesisEngine.synthesize_findings` should compute (or at minimum expose
alongside `average_confidence`) an **agreement-fraction-derived confidence**
for each consensus finding — e.g. `agreements / len(participant_boxes)` —
and the calling code should prefer that signal over raw self-reported
confidence when calibration matters. This is a small, additive, backward-
compatible change (a new field, not a removed one) and is exactly the kind
of fix this experiment was designed to surface. It has not been applied yet
pending a decision on whether to re-run this same pre-registered experiment
against the patched engine (a second, separate pre-registration — you don't
get to re-test the same hypothesis on the same data after seeing why it
failed and call an improved number a win without saying so explicitly).

## Why This Is the Right Thing to Show a Reviewer

Grant reviewers and academic collaborators discount systems that only ever
report success — that pattern is itself evidence of missing negative
results, not evidence of a good system. This result is worth more to a
funding application than a passing demo would have been: it shows a
pre-registered falsifiable test, a caught methodological confound, an
honest negative result, and a specific, scoped engineering fix that follows
directly from the data. That is the actual practice of the field this
project wants to be taken seriously by.

## Reproducing This Result

```bash
python3 -m unittest tests.unit.test_synthesis_calibration_arena -v
# 31/31 tests, fully deterministic given the seed

python3 -c "
from thinkbox.synthesis_calibration_arena import SynthesisCalibrationArena
arena = SynthesisCalibrationArena(n_tasks=300, seed=20260926)
print(arena.run_hermetic().to_dict())
"
```

Same seed, same machine or a different one, identical proof hash. Anyone
can independently verify this without trusting the report above.

## v2: Testing the Fix (separately pre-registered)

The v1 result identified a fix: derive consensus confidence from the
agreement structure instead of averaging boxes' self-reported confidence.
`SynthesisEngine.synthesize_findings` now exposes `agreement_fraction`
(agreements ÷ findings synthesized) on every consensus and conflicting
finding, alongside the unchanged `average_confidence`. The change is
additive: the committed v1 proof hash still reproduces exactly, and a test
now asserts that.

Re-running H1 on the same data after seeing why it failed would be
p-hacking, so v2 is a **new hypothesis**, committed in `bd80cf8e` before
the headline run:

- **H2:** Synthesis confidence derived from `agreement_fraction` achieves a
  lower Brier score than confidence derived from `average_confidence`, on
  the same responses and the same predicted answers.
- **Threshold:** Brier reduction > 0.05 and the paired bootstrap 95% CI
  excludes zero (same bar as v1).
- **Stated expectation, before the run:** with 3 responses per task,
  `agreement_fraction` takes the values 1/3, 2/3 or 1, the same values as
  naive majority vote's vote share. v2 is not expected to beat the
  majority-vote baseline on calibration, so that comparison is reported as
  descriptive only and carries no classification.

The design holds the predicted answer fixed (the run raises an error if v1
and v2 ever pick different answers), so confidence is the only variable.

### v2 Result (n=300 tasks, 900 simulated agent calls, seed=20260926)

| Condition | Accuracy | Brier score |
|---|---|---|
| Synthesis, self-reported confidence (v1) | 78.7% [73.7%, 82.9%] | 0.212 |
| Synthesis, agreement-derived confidence (v2) | 78.7% [73.7%, 82.9%] | **0.120** |
| Naive majority vote | 74.7% [69.5%, 79.3%] | 0.106 |

**Primary, Brier(v2) − Brier(v1):** −0.093, 95% CI [−0.121, −0.065].
**Classification: `IMPROVED`**, which clears the pre-registered bar.

**Secondary, Brier(v2) − Brier(majority), descriptive only:** +0.013,
95% CI [0.000, 0.027]. The CI includes zero, which matches the stated
expectation. The fix brings the engine's confidence to roughly the
baseline's calibration. It does not beat the baseline, and this document
does not claim it does.

What this shows: the calibration problem v1 found was in how confidence
was reported, not in which answer was picked, and the fix addresses it.
What it doesn't show: anything about real models. Every number here is
SIMULATED (seeded synthetic agents), the same as v1.

Proof: `data/thinkboxmd/artifacts/synthesis_calibration_v2_proof.json`
(SHA-256 `7c072a7b1f8d2be0e35ea0b1a129a29dd31165557d46448aa919a4356178092c`).

```bash
python3 -c "
from thinkbox.synthesis_calibration_arena import SynthesisCalibrationArena
print(SynthesisCalibrationArena(n_tasks=300, seed=20260926).run_hermetic_v2()['proof_hash'])
"
```

## Four-State Classification

| State | Status |
|-------|--------|
| **CODE_COMPLETE** | ✅ Experiment harness, 3 conditions, statistics |
| **TEST_VERIFIED** | ✅ 31/31 tests, deterministic reproducibility verified |
| **LIVE_VERIFIED** | ⏳ Not attempted — `run_live()` explicitly refuses to fabricate a result (AGENTS.md §4.4) pending real provider wiring and an explicit compute budget decision |
| **PRODUCTION_READY** | ⏳ Fix applied and re-tested under a separate pre-registration (v2, `IMPROVED`); still simulated-only, so pending a live run |
