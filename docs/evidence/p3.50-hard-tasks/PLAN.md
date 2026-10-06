# P3.50 experiment plan: do the cloud models still score 15/15 on harder SIMULATE tasks?

Written and committed BEFORE any run on this task set. Cloud models only (founder's instruction); no local model is run.

## Question
Mercury-2 and DeepSeek both verified 15 of 15 on the P3.48 task set (one-line fixes). That is a ceiling: it cannot tell the models apart or show where the patch worker breaks. On a harder, frozen set, do they still succeed, and where do they fail?

## Materials
- 12 new tasks, `apps/web/tests/helpers/hard-sim-tasks.ts`, written before any run and not tuned afterwards (the sha256 is recorded in the results). Kinds: symptom-only goals, a bug in a different file than the symptom, multi-line fixes, new behaviour (validation), async, regex, and **one task needing four edits across two files (H07, a rename)**.
- Pre-flight (V0), checked offline by `tests/hard-sim-tasks.test.ts`: every task fails as written and passes with its reference fix.
- Models: `mercury-2` and `deepseek-chat` (served by `deepseek-flash`), 2 trials each = 24 rows per model, through the same convoy SIMULATE path and real sandbox as P3.48. Runner: `P348_TASKSET=hard`.
- Success = convoy verdict `verified` with no flags AND the independent unsandboxed `node --test` agrees (V1 as in P3.48). Wilson 95% intervals.
- Cost cap: the script's existing $0.20 cloud cap (Mercury rates); token counts are the honest measure for DeepSeek.

## Validity criteria (a run that fails one is reported invalid, not as a result)
V0 pre-flight; V1 the independent test agrees with every sandbox verdict; V2 the real repo is untouched; V3 every convoy reaches a terminal state; V4 the task-set hash matches the committed file; V5 no key in the output and spend under the cap.

## What each outcome would mean (stated now)
- Both models ≥ 22/24 pooled-per-model: the set is still at the ceiling; harder tasks (multi-file, longer code) are the next step. No claim about difficulty beyond these tasks.
- A model below 18/24: there is separation or a patch-worker limit; I read every failing row before saying why.
- H07 is reported separately. The patch tool's advertised schema is a single edit (a nested edits list is accepted but not advertised), so H07 may fail for an interface reason, not a model reason. Either result is informative; neither is hidden by pooling (the pooled figures are given with and without H07).
- No local-model decision rule applies to this run.

## Not claimed
Anything about local models, about real repositories, or about held-out performance beyond these 12 tasks. Sampling is unseeded, so a repeat can differ.
