# P3.48 experiment: can a local model be SIMULATE's patch worker? Pre-registration (written BEFORE any model run)

Question: SIMULATE has so far used only Mercury-2 to propose a change. The founder asked why the other models cannot. They can now be the patch worker when the operator picks one (the feature is built and unit-tested with scripted models). **How often does each real model produce a change that the sandbox verifies?** Nothing has ever been measured for patching: local models were measured only for lookups and read-only investigation.

## Setup (frozen)
- **Models, in this order, one at a time (no GPU contention):** `smollm2:360m`, `qwen2.5:1.5b`, `qwen2.5:3b`, `gemma3:4b` (all installed locally; nothing is pulled), then `mercury-2` as the reference (real Inception API, key from the repo `.env`, never printed or written). `qwen2.5:*` use native tool calls; `gemma3:4b` and `smollm2:360m` have no native tools and use the constrained JSON route.
- **Tasks:** 15 tiny git repositories, one per task, each with ONE genuinely failing test and a plain-English goal (`tests/helpers/local-sim-tasks.ts`; kinds: typo, off-by-one, wrong operator, boundary, missing return, wrong default, case sensitivity, index bug, swapped arguments, search among several files, a bug in the file the goal does not name, an edge case, adding a function, a missing export, only-the-first-match). Frozen: the file's sha256 is recorded in the results; it is not edited after the first run.
- **One trial per (model, task), one round (`max_rounds` 1, so a failed proposal is not revised), the checks = `test` only** (the fixtures have no typecheck). Default sampling for every model, exactly as the product runs them. 75 convoys.
- **Path:** the real `executeConvoy`, the real governed tools (`repo_search`, `repo_read`, `propose_change`), the real sandbox (bubblewrap, no network), a convoy planned by the real Mayor with the model chosen as the operator would (`routing.source = operator` for local models; the default, Mercury, for `mercury-2`). Not the dashboard: no browser. **The sandbox-run approval is granted by the script acting on the founder's instruction to run this experiment, not by a person at each prompt.** Each convoy has a 400 s timeout (a timeout is a result: `no_proposal`, reason `timeout`).
- **Spend:** local runs are free; Mercury at most about $0.1; abort if total Mercury spend would exceed $0.20.

## What is measured (per model)
`success` = the sandbox verified the proposal AND the patch carries no flag (a verified patch that edits tests or looks like it detects the harness is **not** a success: it is reported separately as `verified_flagged`). Also: `proposal_wrong` (a valid proposal the sandbox rejects), `no_proposal` split by reason (`no_tool_call`, `malformed_tool_request`, `tool_failed`, `step_limit`, `model_error`, `timeout`, `agent_failed`), flags, wall time, tokens, tool calls, cost. Intervals: Wilson 95% on `success`.

## Validity criteria (each decided from sources independent of the convoy's own verdict)
- **V0 pre-flight:** every task's test fails on the baseline and passes with its reference fix, before any model runs (else the script aborts: NOT RUN).
- **V1 independent agreement:** for every convoy that reached the sandbox, `report.verified` equals an unsandboxed `node --test` on a fresh `git archive` of the pinned commit with the recorded patch applied. Required 100%; otherwise no `verified` count is trusted.
- **V2 integrity:** each task repository's working tree is clean afterwards, and this (the founder's) repository hashes identically before and after.
- **V3 termination:** every convoy ends COMPLETED, PARTIAL or FAILED within the timeout; none is dropped from the table.
- **V4 same input:** every model got identical goal strings from the same frozen file (hash recorded).
- **V5 hygiene:** Mercury spend within the cap, the key appears nowhere in the results, no sandbox scratch directory is left.

## Decision rule (fixed now, applied to the best LOCAL model's `success` count out of 15)
- **>= 9 (60%)**: recommend building a "local first, Mercury as the fallback" lane for SIMULATE (a separate PR needing the founder's go-ahead).
- **5 to 8**: local models can patch the easy kinds only: offer the local patch worker as an opt-in privacy mode, list which task kinds each model handles, and do not build a fallback without a repeat run.
- **<= 4**: do not pursue local patching now; record why (which failure reasons dominate).
- **Sanity:** Mercury must reach >= 13/15. If not, the harness or the tasks are suspect and the local numbers are not interpreted until that is explained.
- **Any local `verified_flagged` or unflagged cheat found by reading the patches** is reported and counts against that model's trust, whatever its score.

## Known limits (stated now)
- One trial per cell, 15 tiny tasks: the intervals are wide (about +-25 points). The rule is coarse on purpose; a result within 2 of a threshold needs a repeat before it drives a decision.
- Tiny fixtures with one-line fixes: this shows what each model can do on easy, well-specified bugs, not on real code. "Verified" means only that the fixture's own test passed in the sandbox.
- Default sampling is not seeded: a rerun can differ.
- No browser and no human at the approval gate; the dashboard path is covered by the unit and server tests, not by this run.
- If any criterion fails or the result surprises me, I report it as it is, keep every run, and disclose amendments in this file; I will not tune the tasks or the rule to the outcome.
