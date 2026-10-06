# P3.48 results (run 1) and what they do and do not show

Written after reading every row of `run1-results.json`, the failure texts, and the raw replies of three failing cases. The pre-registered criteria are in `PLAN.md` and were not changed.

## The table (75 convoys: 5 models x 15 frozen tasks, one trial each, one round, default sampling)

| Model | Verified (no flags) | Valid but wrong | No proposal | Why there was no proposal | Median time | Cost |
|---|---|---|---|---|---|---|
| smollm2:360m | **0 / 15** | 0 | 15 | `malformed_tool_request` 6, `tool_failed` 6, `step_limit` 3 | 6 s | $0 |
| qwen2.5:1.5b | **0 / 15** | 0 | 15 | `no_tool_call` 15 (answered in plain text, or empty, never called a tool) | 12 s | $0 |
| qwen2.5:3b | **0 / 15** | 2 | 13 | `tool_failed` 6, `no_tool_call` 6 (5 of them an empty reply), `malformed_tool_request` 1 | 30 s | $0 |
| gemma3:4b | **0 / 15** | 1 | 14 | `tool_failed` 7, **`model_error` 6 (Ollama call timed out)**, `malformed_tool_request` 1 | 140 s | $0 |
| **mercury-2** (reference) | **15 / 15** | 0 | 0 | | 2.5 s | $0.030 |

Wilson 95% intervals: 0 of 15 is 0% to 20%; 15 of 15 is 80% to 100%. No patch from any model was flagged (`touches_tests`, `harness_detection`): none verified flagged, none cheated.

## Validity (all hold)
V0 every task fails as written and passes with its reference fix; V1 the unsandboxed `node --test` on a fresh export agreed with the sandbox's verdict for **all 18** convoys that reached the sandbox (15 Mercury, 3 wrong local proposals); V2 task repositories and this repository unchanged; V3 every convoy ended terminal; V4 same frozen tasks (sha256 in the results); V5 Mercury spend $0.030 of the $0.20 cap, key not in the results, no scratch directory left. Mercury sanity (>= 13 of 15): **ok**.

## The pre-registered decision rule
Best local model: 0 of 15 (<= 4), so the rule says **do not pursue local patching now**.

## Why that conclusion is weaker than it looks (read this before using it)
The rule measured the feature **as built**. Reading the failures shows that not all of them are the models' ability:
1. **gemma3:4b is confounded by this machine.** The GPU has 2 GB; the 4.8 GB model runs 98% on the CPU, so 6 of its 15 convoys died on the 120 s per-call timeout. Those say nothing about whether it can patch. The other 9: 7 guessed paths that do not exist, 1 malformed request, plus 1 valid-but-wrong patch.
2. **Prompt and interface weaknesses in my implementation depressed the scores.** smollm2 copied the example JSON in my constrained prompt verbatim (`"path":"optional folder"`, `"query":"..."`) and then sent `start`/`end` keys on a search call, which my validation rejects as unknown arguments (6 of its 15 failures). Several models never looked before guessing a path (`src/price.js`, `lib/utils.js`, `utils/add.py`): the loop allows two corrections and then stops. qwen2.5:3b returned an empty reply (no tool call) in 5 cases; a nested `edits: [{path, find, replace}]` schema is a plausible cause (Ollama returns an empty message when it cannot parse a small model's tool call), but **I did not test that**.
3. **Some of it is plainly capability.** qwen2.5:1.5b never called a tool in 15 tries and wrote generic advice ("the `total` function is not defined in the provided code snippet"). The three valid-but-wrong proposals were syntactically broken code (for example `function isAdult(age) { return age >= 18; }(age) {`), which the sandbox correctly rejected.
4. **One trial per cell, tiny one-line tasks.** Two cells flipped between the smoke run and run 1 for the same model and task (qwen2.5:3b solved T01 in the smoke run and failed it in run 1), so single trials are noisy.

## What this supports
- **Supported:** with the current prompts and tools, no installed local model produced a verified change on these 15 easy tasks, while Mercury produced 15 of 15 at about $0.002 each; the sandbox and the independent test agree on every verdict; the sandbox caught every wrong local patch.
- **Not supported:** that local models *cannot* patch. The failures mix model limits with fixable interface problems, and one model was hardware-limited.

## Disclosures
- A smoke run (`smoke-results.json`, qwen2.5:3b on T01 only, which verified) was done to check the harness; its first attempt crashed on a `tar` pipe in my pre-flight (fixed). A first launch of the full run stopped as NOT RUN because the worktree has no `.env` (the key was then passed through the process environment, never printed).
- The harness approves the sandbox run itself, acting on the founder's instruction; no browser; sampling is unseeded.
