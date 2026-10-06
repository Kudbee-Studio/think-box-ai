# P3.49 run 2: the local patch worker after fixing its interface. Pre-registration (written BEFORE any run)

Question: P3.48 run 1 (docs/evidence/p3.48-local-simulate/) found 0 of 15 verified for every local model, but read RESULTS.md: the zeros mixed capability with problems in my implementation (and, for gemma3:4b, with hardware). **After fixing the interface problems that run exposed, how often does each local model produce a change the sandbox verifies?** Same tasks, same models, same sandbox, same rule; only the implementation differs.

## What changed (all from run 1 failures, each with a unit test that fails when reverted; PR #389)
1. Keys that do not belong to a tool call are dropped, not rejected (smollm2 sent `start`/`end` on `repo_search`: 6 of its 15 failures).
2. `propose_change` takes FLAT arguments from the model (`path`, `find`, `replace`, `summary`; `path` + `create` for a new file) instead of a nested `edits` array (qwen2.5:3b returned empty replies: a plausible but untested cause); the governed tool still receives one edit, and the nested form is still accepted.
3. The constrained (JSON) prompt describes the keys in words with no example values to copy (smollm2 echoed `"optional folder"` and `"..."` back).
4. The system prompt says never to guess a path and to start with `repo_search` for a word from the goal; the worker may be handed back 4 recoverable errors (was 2), has 10 tool calls (was 8) and waits up to 300 s per call (was 120 s).
5. An empty reply or plain text before any tool call gets ONE nudge to call a tool (qwen2.5:1.5b answered in text 15 of 15 times, qwen2.5:3b returned empty replies 5 times).

## Setup (frozen)
- **Tasks:** the same 15 frozen tasks; the tasks file's sha256 must equal run 1's (`6eadb56a071161892691e87beec22b40dcfe23371c5014d28bb5ca3ebe9b41af`), checked by the script (V4).
- **Models, in this order:** `smollm2:360m`, `qwen2.5:1.5b`, `qwen2.5:3b` (**2 trials each**, to see sampling noise), then `gemma3:4b` (**1 trial**: on this machine's 2 GB GPU it runs on the CPU and takes minutes per task). Default sampling, one round, checks = `test` only, the real executeConvoy / governed tools / sandbox, approvals granted by the script on the founder's instruction. Per-convoy timeout 900 s (was 400 s) so a slow-but-working CPU model is not cut off.
- **Mercury is NOT re-run:** its path is untouched by these changes (only the local-model branch of the runner and the local patch spec changed). Its run 1 result (15 of 15, 2.5 s median, $0.03) is the reference.
- Evidence goes to this folder; run 1's files are unchanged.

## Measured (per model, pooled over its trials)
`success` = verified AND no flag (as in run 1). Also valid-but-wrong, no proposal by reason, flags, time, tokens, tool calls. **Interface effect:** for each model, the change in `success` and in each failure reason versus run 1, and per task whether it flipped. Wilson 95% intervals.

## Validity (same as run 1, plus one)
V0 every task fails as written and passes with its reference fix; V1 the unsandboxed `node --test` agrees with the sandbox's verdict for every convoy that reached the sandbox (100%); V2 task repos and this repo unchanged; V3 every convoy terminal; **V4 the tasks hash equals run 1's**; V5 no key in the results, no scratch dir left.

## Decision rule (applied to the best local model's POOLED success rate)
- **>= 60%**: recommend building the "local first, Mercury as the fallback" lane (a separate PR needing the founder's go-ahead).
- **33% to 59%**: local models can patch the easy kinds only: offer the local patch worker as an opt-in privacy mode, list which task kinds each model handles; no fallback without a repeat.
- **below 33%**: do not pursue local patching now. Because this run removes the interface problems found in run 1, a result below 33% is a much stronger statement about capability than run 1's was: I will say so, and I will name which failure reasons remain.
- Any local `verified_flagged` or cheat found by reading the patches is reported and counts against that model's trust, whatever its rate.
- gemma3:4b: if timeouts (`model_error`) still account for a large share of its failures, its rate is reported as hardware-limited and is NOT used to decide anything; it still counts in the table.

## Known limits (stated now)
- 15 tiny tasks, one-line fixes; 2 trials for three models and 1 for gemma: the intervals stay wide. A rate within 5 points of a threshold needs a repeat before it drives a decision.
- I chose these five fixes after reading run 1's failures, on the same tasks. That makes run 2 an experiment about the fixed implementation, not an untouched held-out test; there is no new task set. A held-out set (fresh tasks, same rule) would be the next step before relying on any number here.
- Default sampling, unseeded; no browser; the script approves the sandbox run.
- If the result surprises me or any criterion fails, I report it as it is, keep every run, and disclose amendments in this file; I will not tune the tasks or the rule to the outcome.
