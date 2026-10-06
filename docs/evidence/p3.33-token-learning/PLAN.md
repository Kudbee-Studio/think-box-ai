# P3.33 Think Token learning test: pre-registration (written BEFORE any live run)

Question: does a Think Token that the real pipeline wrote from a SUCCESSFUL Mercury run make a small local model better at the same kind of repository goal on code it has never seen? This is the first fair test: P3.24 used tokens about unrelated work (learning benefit UNPROVEN, B minus A -3.3 points) and P3.25 showed the local model cannot bootstrap tokens from its own successes (untested-function 0/10). The teacher is now Mercury, which the P3.32 lane measured at 15/15 on untested-function goals.

## Stages
1. **Teacher.** Mercury (`mercury-2`, through the governed repo loop, `attemptRepo`) runs the 10 untested-function goals of `TRAIN_GOALS` in the training world. Each run that is `accepted` AND passes the fixture's machine check is handed, as a finished run (its real tool events and final finding), to the real `processFinishedRun` (extract with Mercury via `INCEPTION_API_KEY_2`, deterministic checks, challenge with Mercury, auto-accept only on a model-written lesson that passed a model challenge; the local fallback model is switched OFF so every token is Mercury-written) into a FRESH temporary token store. The real `think-tokens.db` is never read or written. Which tokens end up accepted is whatever the pipeline decides; none is written by hand and none is edited.
2. **A/B.** `qwen2.5:3b`, local only (no escalation), engine absence search on (production config), maxSteps 8, temperature as the local loop sets it, `seed = 7000 + goal index`. Per held-out goal, two arms in a seeded random order:
   - **A:** no tokens.
   - **B:** the tokens retrieved from the temporary store by the real recall (`retrieve(goal, 3)`: BM25 + MiniLM cosine, the server's path), injected with the server's `formatTokensForPrompt` into the system prompt.

## Frozen inputs
- **Held-out goals:** 20 untested-function goals (`HELD_GOALS`, `tests/helpers/ab-fixture.ts`, world `startHeldWorld`): 20 new modules whose file and function names share nothing with the training or A/B worlds (a test enforces this), 10 per phrasing. sha256 of `[id, class, goal]` = `3d83676e521214f8a24fd22c987d8c931e5b002e211dbe60a561f8d509974169`.
- **Teacher goals:** the 10 untested-function goals of `TRAIN_GOALS` (hash `8db936784996284d9a91064e3728043de1a1064dd9b5e36d05dedfa4ba22c783` for all 20 training repo goals; the 10 used are the ids starting `train-untested-`).
- Outcome definitions as in P3.32: **pass** = finished, GROUNDED, finding verified on disk, machine check passes; **false accept** = accepted but the machine check fails. Also recorded per run: whether the production trigger (`repoEscalationReason`) would have escalated it, tool calls, latency.

## Pre-registered decisions
0. **Teacher guard.** If fewer than 2 tokens are accepted by the pipeline from Mercury runs (extract model `mercury-2`), there is nothing to test: result **UNPROVEN (no tokens produced)**; stage 2 is not run.
1. **Testability guard.** If fewer than 50% of the 20 held-out goals retrieve at least one token, the result is **UNPROVEN (tokens rarely applied)** whatever the numbers.
2. **Primary.** "B is better than A" requires ALL of: pass-rate B minus A >= +20 percentage points (4 of 20 goals); paired-bootstrap (10 000 resamples, seed 20261007) 95% interval for B minus A excludes 0; exact two-sided McNemar test on the discordant pairs p < 0.05; false accepts in B <= false accepts in A. Called **PROVEN** only if all hold.
3. **Negative.** If the bootstrap upper bound for B minus A is below 0, the result is **NEGATIVE** (the tokens hurt). Otherwise, if (2) fails, **UNPROVEN**.
4. **Descriptive only, never used to rescue a failed primary:** the would-escalate rate in A vs B (a lower rate with tokens would mean fewer paid retries), by phrasing; each accepted token's text; per-goal outcomes.
5. **Spend.** Mercury (teacher runs plus pipeline calls) must stay under **$0.50**: lane runs are costed from the provider-reported tokens at the `agent.ts` price table, pipeline calls from the store's recorded model usage. The runner stops if the running total would pass it.
6. No trial is dropped, re-run or edited; the raw files are created atomically (`wx`) and never overwritten. The analysis is computed from them only (`tests/e2e/token-learning-report.ts`).

## Known limits (stated now)
- The held-out world has the same shape as the training world (a module with one tested and one untested function). This tests transfer between unseen modules of that family, not transfer to a real repository.
- 20 goals, one local model, one run per goal per arm (temperature 0, fixed seed): only a large effect can clear the bar.
- The tokens are written by Mercury and accepted by Mercury's own challenge; no human reviewed them. The accepted tokens are saved in the evidence directory for the founder to read; nothing is added to the real store.
- A null result shows only that tokens of this kind, retrieved this way, did not help this model on these goals.
