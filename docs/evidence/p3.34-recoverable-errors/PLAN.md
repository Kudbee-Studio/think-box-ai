# P3.34 re-test of Think Token learning after two fixes: pre-registration (written BEFORE any live run)

Question: P3.33 left learning UNPROVEN (A 1/20, B 0/20) but showed two defects that could have hidden an effect. Do the tokens help a small local model once both are fixed, on goals nobody has seen?

## The two fixes (merged into this branch before the run; tests only so far)
1. **Recoverable path errors.** In P3.33, 13 of 20 token runs followed the token's advice but searched a folder called `test` instead of `tests`; the repo tool said "path not found: test" and the loop treated any tool failure as terminal. Now a repo "path/file not found" error (a) names what exists in the nearest existing folder (hidden entries, secrets and excluded folders never listed) and (b) goes back to the model, at most twice per run, still counting as tool calls. Other tool errors stay terminal. This applies to BOTH arms.
2. **Token pipeline output cap.** 6 of 10 Mercury extract replies in P3.33 were rejected as "not the expected JSON". Diagnosis (live, 4 runs): replies were cut off mid-JSON, 885 and 866 output tokens against a 900 cap for about 1,300 visible characters (Mercury 2 spends part of the cap on hidden reasoning), and two replies were empty. The caps are now 2500 (extract) and 1200 (challenge), and a reply cut off at the cap is reported as such. A pipeline fix, not a change to what the pipeline accepts.

## Stages
1. **Teacher.** Exactly as P3.33: Mercury (`mercury-2`, governed repo loop) solves the 10 training untested-function goals; each verified success goes through the real `processFinishedRun` (Mercury extract + challenge, local fallback OFF) into a FRESH temporary store. The real `think-tokens.db` is not touched. The pipeline decides what is accepted; nothing is hand-written or edited.
2. **Primary A/B.** `qwen2.5:3b`, local only, engine absence search on, maxSteps 8, `seed = 9000 + goal index`. Per fresh held-out goal two arms in a seeded random order: **A** no tokens; **B** the tokens retrieved by the real recall (`retrieve(goal, 3)`, BM25 + MiniLM cosine) injected with `formatTokensForPrompt`.
3. **Regression check (descriptive only).** The 20 P3.33 held-out goals (already seen) run in both arms with the new tokens and the fixed loop, to show what the fixes did to the exact failure observed there.

## Frozen inputs
- **Primary goals:** 30 untested-function goals (`HELD2_GOALS`, world `startHeld2World`, `tests/helpers/ab-fixture.ts`): 30 new modules, every file and function name new also versus the P3.33 world (a test enforces it; it also caught and removed one module name that the tool's secret-file filter hides), 15 per phrasing. sha256 of `[id, class, goal]` = `9fb7ce053a04baaf70b2bfb11b2c07ecbbbdd209424e21bf4319de014b1818fd`.
- **Teacher goals:** the 10 ids starting `train-untested-` in `TRAIN_GOALS`. **Regression goals:** `HELD_GOALS` (hash `3d83676e521214f8a24fd22c987d8c931e5b002e211dbe60a561f8d509974169`).
- Outcomes as in P3.32/P3.33: **pass** = finished, GROUNDED, finding verified on disk, machine check passes; **false accept** = accepted but the machine check fails. Also recorded: `tool_retries`, whether the production trigger would have escalated, latency.

## Pre-registered decisions (identical to P3.33 so the two are comparable)
0. **Teacher guard:** fewer than 2 tokens accepted from Mercury runs: **UNPROVEN (no tokens produced)**, stage 2 not run.
1. **Testability guard:** fewer than 50% of the 30 primary goals retrieve at least one token: **UNPROVEN (tokens rarely applied)**.
2. **Primary:** "B is better than A" requires ALL of: pass-rate B minus A >= +20 percentage points; paired-bootstrap (10 000 resamples, seed 20261008) 95% interval excludes 0; exact two-sided McNemar on the discordant pairs p < 0.05; false accepts in B <= false accepts in A. Then **PROVEN**.
3. **Negative:** bootstrap upper bound below 0: **NEGATIVE**. Otherwise, if (2) fails, **UNPROVEN**.
4. **Descriptive only, never used to rescue a failed primary:** the teacher's usable-extract rate (P3.33: tokens from 1 of 10 runs); the share of runs ending in `tool_failed` in each arm (P3.33 B: 13 of 20); the regression set; would-escalate rates; the accepted tokens verbatim.
5. **Spend:** teacher runs plus pipeline calls under **$0.50**; the runner stops if the running total would pass it.
6. No trial is dropped, re-run or edited; raw files are created atomically (`wx`). The analysis is computed from them only (`tests/e2e/token-learning2-report.ts`).

## Known limits (stated now)
- Same fixture family for training and held-out (a module with one tested and one untested function): this tests transfer between unseen modules of that family, not to a real repository.
- 30 goals, one local model, one run per goal per arm (fixed seed); the tokens are Mercury-written and Mercury-challenged, no human reviewed them.
- The fixes make the A arm better too; B is judged against that stronger A. A null result still shows only that tokens of this kind did not help this model on these goals.
- The regression set is already seen, so it is a before/after check of the fix, not a held-out result.
