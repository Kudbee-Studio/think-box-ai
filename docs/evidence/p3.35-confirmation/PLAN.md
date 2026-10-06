# P3.35 confirmation of the Think Token effect: pre-registration (written BEFORE any live run)

Question: P3.34 found tokens raised the local pass rate from 3/30 to 11/30 (+26.7 pts, bootstrap CI [3.3, 46.7]) but missed one pre-registered bar (exact McNemar p = 0.0574), so learning stayed UNPROVEN. Is the effect real? This is a full, independent replication of the whole procedure, not a re-analysis.

## Why a full replication, not "the same tokens again"
The temporary token store from P3.34 was deleted when the run ended, and `tokens.json` records title and content but not each token's retrieval text, so the P3.34 tokens cannot be rebuilt exactly. The honest design is therefore to repeat the entire procedure: a fresh teacher stage and the real pipeline produce a new token set (Mercury is not deterministic, so it will differ), then a new A/B on goals nobody has seen. A positive result then supports "tokens written by this pipeline help", not "this particular token set helps". This run records the full token rows and their retrieval text so the set can be rebuilt next time.

## Procedure (unchanged from P3.34; no code changes since the fixes merged in #373)
1. **Teacher.** Mercury (`mercury-2`, governed repo loop) solves the 10 training untested-function goals (`train-untested-*`); each verified success goes through the real `processFinishedRun` (Mercury extract + challenge, local fallback OFF, caps 2500/1200) into a FRESH temporary store; the real `think-tokens.db` is untouched. The pipeline decides what is accepted; nothing is written or edited by hand.
2. **A/B.** `qwen2.5:3b`, local only, engine absence search on, maxSteps 8, recoverable path errors on in both arms, `seed = 11000 + goal index`. Per goal two arms in a seeded random order: **A** no tokens; **B** the tokens retrieved by the real recall (`retrieve(goal, 3)`, BM25 + MiniLM cosine) injected with `formatTokensForPrompt`.

## Frozen inputs
- **Goals:** 60 untested-function goals (`HELD3_GOALS`, world `startHeld3World`, `tests/helpers/ab-fixture.ts`): 60 modules generated from fixed word lists, every file and function name distinct and new versus all four earlier worlds, none that the repo tools hide (a test enforces all three), 30 per phrasing. sha256 of `[id, class, goal]` = `79f5ca0f9e0cf96edc71076b9fbd7b8e0621cbc3efc2fa8c046f151f0403c307`.
- Outcome definitions, `would_escalate`, `tool_retries`: as in P3.34.

## Pre-registered decisions (identical to P3.34, applied to this set alone)
0. **Teacher guard:** fewer than 2 tokens accepted from Mercury runs: **UNPROVEN (no tokens produced)**, stage 2 not run.
1. **Testability guard:** fewer than 50% of the 60 goals retrieve at least one token: **UNPROVEN (tokens rarely applied)**.
2. **Primary:** all of: pass-rate B minus A >= +20 percentage points; paired-bootstrap (10 000 resamples, seed 20261009) 95% interval excludes 0; exact two-sided McNemar p < 0.05; false accepts B <= A. Then **replicated: PROVEN**.
3. **Negative:** bootstrap upper bound below 0: **NEGATIVE**. Otherwise **UNPROVEN**.
4. **Descriptive, never used to rescue a failed primary:** teacher usable-extract rate and token count; `tool_failed` and retry counts per arm; would-escalate per arm; latency; a **pooled** view of P3.34 and this run (90 goals, two independent token sets) reported as descriptive only, since it was not pre-registered as a test.
5. **Spend:** teacher runs plus pipeline calls under **$0.50**; the runner stops if the total would pass it. The A/B stage uses no paid model.
6. No trial is dropped, re-run or edited; raw files are created atomically (`wx`). The analysis is computed from them only (`tests/e2e/token-learning3-report.ts`).

## Known limits (stated now)
- Same fixture family for training and held-out (a module with one tested and one untested function): at best this confirms transfer between unseen modules of that family, not to a real repository.
- One local model; tokens Mercury-written and Mercury-challenged, no human review.
- A "replicated" result still says nothing about whether the live convoy path benefits; tokens are not yet injected there.
- Fixtures were designed after seeing local failures; the model's dominant failure ("reported nothing") remains common in both arms and is what the P3.32 escalation lane handles.
