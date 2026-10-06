# P3.49 run 2: results, and what they do and do not show

Written after reading every row of `run2-results.json`, the failure texts, the flips per task for qwen2.5:3b, and the kernel log. The pre-registered criteria in `PLAN.md` were not changed.

## The table (same 15 frozen tasks as run 1; the tasks hash matches; real models, real tools, real sandbox)

| Model | Trials | Verified (no flags) | Valid but wrong | No proposal | Main reasons for no proposal | Run 1 for comparison |
|---|---|---|---|---|---|---|
| smollm2:360m | 2 | **0 / 30** (CI 0-11%) | 0 | 30 | `malformed_tool_request` 28: a query shorter than 2 characters (17) or a path that is not relative (11) | 0 / 15 |
| qwen2.5:1.5b | 2 | **0 / 30** (CI 0-11%) | 3 | 27 | `malformed_tool_request` 26: it keeps answering in prose after the nudge instead of calling `propose_change`; `no_tool_call` 1 | 0 / 15, all 15 `no_tool_call` |
| **qwen2.5:3b** | 2 | **3 / 30 = 10%** (CI 3-26%) | 13 | 14 | `step_limit` 5, `tool_failed` 4 (a guessed file that does not exist), `malformed_tool_request` 4, `no_tool_call` 1 | 0 / 15 (2 wrong) |
| gemma3:4b | 1 | **incomplete**: see below | 2 | | valid rows T01-T04 only | 0 / 15 |
| mercury-2 | (run 1) | 15 / 15 | 0 | 0 | | reference, not re-run |

All validity criteria held: V0, V1 (the unsandboxed `node --test` agreed with the sandbox on **all 21** sandbox verdicts: 3 verified, 18 wrong), V2, V3, V4 (tasks hash equal to run 1's), V5. No patch was flagged for tampering.

## gemma3:4b did not get a fair run (hardware, not model)
The kernel's out-of-memory killer killed Ollama's `llama-server` (about 6 GB resident, on a 7.9 GB machine) at 16:42 local time, during gemma's task T06. T06 to T15 then failed instantly with `model_error: fetch failed` (10 rows). T05 ran into the 900 s convoy cap. The rows that are real are T01 to T04: two valid-but-wrong patches (T02, T04), one `step_limit`, one `malformed_tool_request`. Per the pre-registration, gemma's rate is hardware-limited and **is not used to decide anything**. I did not rerun it: the same machine would likely be killed the same way, and it would take Ollama down again. A fair gemma run needs more RAM or a GPU that fits the model.

## The pre-registered decision rule
Best local model, pooled: qwen2.5:3b at 10% (3 of 30). Below 33%, so the rule says **do not pursue local patching now**.

## How much weight that carries
- **Stronger than run 1's zero.** Run 1's failures included problems in my implementation. Those were fixed (irrelevant keys, the copied example, guessed paths, empty replies). qwen2.5:3b went from 0 to 3 verified and from 2 to 13 valid proposals; qwen2.5:1.5b went from never calling a tool to making 3 valid proposals. What remains is mostly the models: invalid tool values (smollm2), prose instead of a tool call (1.5b), and wrong edits (3b: `rate * rate`, `divide(y, x) / 2.5`, a mangled test file).
- **Still noisy.** qwen2.5:3b verified 3 tasks in trial 1 and **none** in trial 2 (T03, T07 and T15 flipped from success to no/wrong proposal). Single-digit counts, wide intervals, unseeded sampling.
- **Not an untouched test.** I chose the five fixes after reading run 1's failures on these same tasks, so run 2 measures the fixed implementation, not held-out performance. A fresh task set would be the next step before trusting any number here.
- **Tiny tasks.** One-line fixes. 10% on those says nothing good about real code.

## What this supports
- Supported: with the fixed implementation, the best installed local model verifies about one in ten of these easy tasks, against Mercury's 15 of 15; the sandbox caught every wrong patch and the independent test agrees with every verdict.
- Not supported: anything about gemma3:4b; anything about larger local models; that no local approach could work (for example one where the engine finds the file and shows it, so the model only writes the edit).

## Disclosures
- A two-task smoke run of the runner changes (`smoke-results.json`) was done first; smollm2 failed it for its own invalid values, not for a defect in the fixes.
- The script approves the sandbox run on the founder's instruction; no browser; sampling unseeded.
- The first gemma failures after the OOM kill are kept in `run2-results.json`, unedited.
