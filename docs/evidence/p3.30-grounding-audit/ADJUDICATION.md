# Grounding audit: adjudication (hand-labelled by Claude, 2026-10-05; the founder has not reviewed these labels)

**What was run.** 12 live-data questions x 3 models (mercury-2 through the worker agent; gemma3:4b and qwen2.5:3b through the local tool loop), against the real GitHub repo `Kudbee-Studio/think-box-ai`, twice:
- `runs-v1-compact-old-validator.jsonl`: first sample, OLD validator, compact evidence (36 rows).
- `runs.jsonl`: second, fresh sample, full evidence stored so verdicts can be replayed (`npm run test:live-grounding-audit-replay`), 36 rows.

A **false alarm** is a correct answer the validator rejected. A **false pass** is a wrong answer it accepted. Labels below are my reading of each answer against the raw evidence and, for totals, against GitHub itself (`gh api`: the repo has 10 open issues that are not PRs, and 100+ branches; the lookups fetch 10 entries per page and keep at most 5 issues).

## v1 (old validator): 36 rows = 21 grounded, 11 rejected, 4 runs with no answer
| Row | Verdict | My label | Why |
|---|---|---|---|
| mercury "Is PR 367 merged?" | rejected | **false alarm** | correct answer; rule "must name the newest PR (#368)" applied to a question about #367 |
| mercury "Which PRs are drafts?" | rejected | **false alarm** | "no draft PRs" is correct; `"draft": false` and the word `false` read as claims |
| mercury "What branches exist?" | rejected | **false alarm** | "branches currently present" read "currently" as a branch name |
| mercury "Are there any open issues?" | rejected | **false alarm** | correct table; items named by bare number `\| 59 \|`, not `#59` |
| mercury "How many issues are open?" | rejected | true positive (wrong reason) | said "5"; the truth is 10 |
| mercury "How many branches...is main protected?" | rejected | true positive (wrong reason) | said main is not listed so not protected; main exists |
| gemma "Which PRs are drafts?" | rejected | **false alarm** | "no draft PRs" is correct |
| gemma "Did the last CI run pass?" | rejected | **false alarm** | "the `main` branch failed" read "failed" as a branch name |
| gemma "How many branches..." | rejected | true positive (wrong reason) | said ten; there are 100+ |
| qwen "Which PRs are drafts?" | rejected | mostly false alarm | "none are in draft state" is correct; "all are either open or merged" is vague |
| qwen "Did the last CI run pass?" | rejected | **false alarm** | same "branch failed" |
| gemma x2, qwen x2 "issues" questions (said 5 / five) | **accepted** | **false pass** | totals taken from a list that is only the first page |

v1: 8 false alarms, 3 true positives (all for the wrong reason), 4 false passes.

## v2 (fresh sample), final validator, replayed: 36 rows = 5 no answer, 31 validated: 25 grounded, 6 rejected
All 6 rejections are, in my reading, correct: gemma "ten branches" and "five issues"/"5" (x2), qwen "5" (x2) are totals taken from a first page; qwen "all of them are either open or have been merged" asserts an open state the evidence does not support. **No false alarm remains in this sample; no false pass that I found.** The 25 grounded answers were not each re-read against GitHub; they were checked by the validator against the tool evidence only.

## Limits
One repo, 12 questions, 3 models, two samples; labels are mine. The validator is still a pattern checker, and a different phrasing will find new false alarms. 5 of 36 v2 runs produced no answer (Mercury hit its 4-step limit or a timeout once each; qwen made no tool call three times).
