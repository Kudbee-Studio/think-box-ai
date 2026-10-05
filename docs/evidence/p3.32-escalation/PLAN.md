# P3.32 escalation lane: pre-registration (written BEFORE any live run)

Question: when a local model fails a repository goal, does retrying that goal ONCE on Mercury, through the same governed repo tools, grounding validator, absence engine and disk re-read, raise the number of verified-correct results, without more wrong answers being accepted, and inside the spend cap?

## What is built (tests only so far)
`mercury-chat.ts` (Mercury behind the loop's chat interface), `escalation.ts` (`attemptRepo`, `accepted`, `repoEscalationReason`), the convoy runner's second worker `escalation-1`, the Mayor plan naming the escalation up front (so the human approval covers it). Same loop for both models; only the model differs.

## Trigger (fixed before the run; `repoEscalationReason`)
Retry on Mercury when the local attempt (a) failed, (b) was not GROUNDED, (c) reported a finding whose quote is not on disk, or (d) reported "no finding" for a goal shaped "untested function in a named file" or "which file defines CONSTANT". Never after a denial or an operator stop. A grounded "no finding" for "find a function named X" is kept. **Honest caveat:** (d) was chosen because "found nothing" was the dominant local failure seen in P3.24 to P3.26 on these very fixtures, so these goal sets are not a blind test of the trigger; they test whether Mercury, once triggered, produces verified results.

## Frozen inputs
- **Primary set:** the 15 repository goals of `AB_GOALS` (`tests/helpers/ab-fixture.ts`, fixture world `startAbWorld`): 5 untested-function, 5 constant, 5 missing-function. sha256 of `[id, class, goal]` for those 15 = `5549e075ffed09b5d0d3c22411fe24bc57b930f2dc87b1b9a67c562a94fd200a`.
- **Secondary set:** the 20 repository goals of `TRAIN_GOALS` (world `startTrainWorld`): 10 untested-function, 5 constant, 5 missing-function. sha256 = `8db936784996284d9a91064e3728043de1a1064dd9b5e36d05dedfa4ba22c783`.
- **Local model:** `qwen2.5:3b` (the measured repo-class route), temperature as in the local loop defaults, `seed = 1000 + goal index` (primary) / `5000 + goal index` (secondary), maxSteps 8 (the convoy value).
- **Escalation model:** `mercury-2`, temperature 0, maxSteps 8, same tools. Mercury is not seedable; one run per goal, no repeats.
- **World:** the deterministic fixture, no network except the Mercury API, 127.0.0.1 for everything else.
- Goals are not edited after this file is committed. Tools are the read-only repo tools; nothing is written.

## Arms (paired by goal)
- **L:** the local attempt alone.
- **E:** the local attempt; when the trigger fires, Mercury's attempt REPLACES it (as in the convoy). A Mercury error counts as a failed escalation.
Pairing is by construction: E equals L on every goal where the trigger does not fire.

## Outcomes (`scoreTrial` + disk check)
- **pass:** the loop finished, the result is GROUNDED, a found finding's quote is verified on disk (`accepted`), and the fixture's machine check of the fact passes.
- **false accept:** `accepted` is true but the machine check fails (a verified-looking wrong answer).
- Per goal also recorded: trigger reason, tokens, Mercury cost (from the provider's reported usage at the listed price), latency.

## Pre-registered decisions
1. **Primary (n=15):** the lane is called **better** only if ALL hold: pass-rate E minus L >= +30 percentage points; paired-bootstrap (10 000 resamples, seed 20261006) 95% interval for E minus L excludes 0; false accepts in E <= false accepts in L; every Mercury result that passed was also verified on disk (by construction of `pass`).
2. **Testability guard:** if the trigger fires on fewer than 5 of the 15 primary goals, the primary result is **UNPROVEN** whatever the numbers.
3. **Spend:** total Mercury spend across both sets must stay under **$0.50**; the runner stops escalating when the running total would pass it and records every goal it did not escalate for that reason (those count as L). Per goal, Mercury is bounded by maxSteps 8.
4. **Secondary (n=20):** reported with the same statistics as a replication. The lane is called **PROVEN** only if the primary is met AND the secondary rescued at least one goal and lost none. If the primary is met and the secondary is not, the report says **MIXED**. If the primary is not met: **UNPROVEN**, or **NEGATIVE** when E minus L < 0 or false accepts rose.
5. No trial is dropped, re-run or edited. Raw per-goal rows are appended to `raw-primary.jsonl` and `raw-secondary.jsonl`; the analysis is computed from them only (`tests/e2e/repo-escalation-report.ts`).
6. The "missing" goals are a guard: the trigger is expected NOT to fire on them (a grounded "does not exist" is kept); their escalation count and cost are reported.

## Known limits (stated now)
- 15 and 20 goals: intervals are wide; only a large effect can clear the bar.
- Synthetic fixtures, one local model, one stronger model, one run per goal for Mercury.
- The trigger rule was written after seeing the local failures on these fixtures (caveat above); a result here says Mercury solves the triggered goals, not that the trigger generalises to other repositories.
- Mercury cost is computed from reported token counts and the price table in `agent.ts`; the provider's invoice is the authority.
- Nothing here shows learning, only escalation.
