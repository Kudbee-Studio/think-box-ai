# ADR 029 P3.10: live gaps, real-model answer check, learning A/B (2026-10-02)

Mercury spend: about **$0.21** of the $0.75 cap (A/B $0.18, answer-check cases $0.01, live runs and one extraction call the rest). The real token database was backed up first (`think-tokens.db.bak-pre-p310-20261002`, local, gitignored).

## 0. The gaps from the live :3000 run

| Gap | Finding | Fix |
|---|---|---|
| (a) "local-bm25 (vector offline)" | That label is the **memory store's** backend (the Upstash vector service is unreachable, so memory recall falls back to local BM25). It is not the Think Token embeddings and is unchanged: an external service, not in scope. Separately, the real server's first goal after a restart was ranked **lexically** while the MiniLM model was still loading, and the model cache folder never existed there. Reproduced on a copy of the real data: first goal "lexical (embedding model still loading)" retrieved TT-000006 and TT-000005; after the model loaded it ranked by cosine. A fresh server with an empty cache loads the model in under 40 s without error. Why the real server's load never happened could not be determined (no error was logged then). | The model now starts loading at server boot, always; load failures are logged and shown in the thought stream (`lexical (embedding model failed to load: ...)` / `still loading`); the thought names the real ranker (`cosine (...)`, it said `hybrid` before). |
| (b) TT-000007 not retrieved | At that moment ranking was lexical: the goal "WHAT PR ARE WE WORKING ON?" shares the word `PR` with TT-000005/6 ("PRs" there) but TT-000007 says "PRs"/"stale memory", and it had no stored vector. With the model loaded, cosine ranks it into the top 3. Not a lesson-text or ranker-weight problem; nothing was tuned. | Same fix as (a). Confirmed live below. |
| (c) superseded memory recalled | It was recalled by title and body; recall had no notion of "superseded". The two "WHAT PR ARE WE WORKING ON?" episodes are two distinct files. | `MemoryStore.search` drops memories tagged `superseded` or titled `[SUPERSEDED...` (they stay on disk) and collapses duplicates: same text, or, for task episodes, the same goal (newest kept). Tests in `tests/memory.test.ts` and `tests/evidence.test.ts`. |
| (d) TT-000008 rejected | The lesson ("Inspect the status code (200) and content-type before attempting to parse. Prevents crashes when the endpoint returns an error page or non-JSON payload.") came from a run that fetched two pages and parsed nothing. The challenge said "not true to the run, not supported by evidence: lesson not demonstrated in run". **The rejection was correct**: the run shows no parsing and no crash prevented; the status and content-type were visible in the output but the lesson's claim was not demonstrated. (The wording "not true" is stronger than the substance, "unsupported", but the verdict stands.) | none |

## 1. Live check on :3000 (restarted on this branch's code)

Full trace: [`p310-live-3000-trace.txt`](./p310-live-3000-trace.txt). Goal "WHAT PR ARE WE WORKING ON?", real Mercury, real data.
- `Recalled 2 memories ...: WHAT PR ARE WE WORKING ON? · WHAT PR ARE WE WORKING ON?` (two task episodes; the superseded note is **not** recalled. The two identical-goal episodes still show here because this server's process started before the dedupe fix was written; the fix is covered by tests.)
- `Think Token ranking: cosine (Xenova/all-MiniLM-L6-v2), 81 ms, 3 found` and `Using 3 Think Tokens: TT-000006, TT-000005, TT-000007`: **TT-000007 retrieved, embeddings on.**
- fetch of the pulls API returned `[]`; the final answer: "currently has **no open pull requests** (the GitHub API returned an empty list)". Cost $0.0036.
- Network approvals were auto-approved by the test driver, not a human.

## 2. Real-model answer check (no scripted model)

`scripts/live-answer-check.mjs`, raw `p310-live-answer-check.json`. Six cases, strongly worded "verified, current" memories against tool results that were empty, failed, or non-empty and contradicting; each run once with the check OFF and once ON; the correctness tests were committed before any run.

| Case | Tool result | OFF | ON |
|---|---|---|---|
| open PRs | `[]` | correct | correct (check fired: see below) |
| CI | zero workflow runs | correct | correct |
| server | HTTP 503 | correct | correct |
| wallet | 404 | correct | correct |
| open PR, contradicted | list with #322 only | correct | correct |
| CI, contradicted | latest run `failure` | correct | correct |

**With the system rule and the memory labels in place, real Mercury answered all six correctly even with the check OFF, so there was no wrong answer for the check to fix: it caught-and-fixed 0 of 0 wrong answers.** The check fired once (open PRs, ON): the first answer mentioned "#304" only to deny it, so this was a **false flag** (one retry, final answer still correct). I made the gate ignore a PR number mentioned in a negated context and told the judge that absence is not a conflict (test added); the false flag was not re-run. So: false flags 1 of 6 before that fix, 0 observed wrong answers prevented. The check remains unproven on a real wrong answer; the cases were not hard enough to make the model fail.

## 3. Non-empty conflicts

`evidence.ts` `unsupportedClaims`: an answer that names a PR number (`#N`), a status word (green/passing, failing/red, running/up, down/offline, merged, draft, closed) or a count of PRs/files/items/results that appears nowhere in this run's tool output (list lengths count) becomes a candidate; a model still confirms before anything changes. Numbers and statuses mentioned after a negation are not claims. Tests: wrong #304 vs a list holding #322, supported #322, counts via list length, "CI is green" vs a failing run, negated status, ordinary answers not triggering, denial of a PR number.

## 4. Live-state classifier

20 hand-labeled memories (`apps/web/tests/fixtures/live-state-labeled.json`) and the example sentences were committed before any run; the decision rule (embedding classifier only if its accuracy >= the keyword list's) was fixed in the script header. Result (`p310-live-state-classifier.json`): **keyword list 12/20, embedding classifier 15/20**, so the embedding classifier is used when the model is loaded (keyword list otherwise). It still misses 5: it called 4 static texts live (for example "write_file reports bytes", "The dashboard binds to 127.0.0.1") and missed "The build on main is red...". 20 items, one author: direction only.

## 5. Learning A/B (P3.8 cosine default), set 4 goals with objective checks

Checks committed before the run (`think-token-ab-goals-p310-decision4-checks.mjs`; lenient, since the goals are vague). Real Mercury, frozen clock, p37 seed, "on" server waited 25 s for the model, 4 reps per arm, 96 runs, `p310-ab-set4-result.json`.

| Arm | Completed | Passed | Tool calls | Steps | Tokens | Cost/run |
|---|---|---|---|---|---|---|
| off | 47 / 48 | 29 | 2.19 | 5.35 | 6,404 | $0.00188 |
| on | 48 / 48 | 32 | 2.29 | 5.58 | 6,771 | $0.00195 |

Fisher exact p = **0.67**. Pooled with the earlier A/B that used the same cosine ranker (P3.8: on 20/29, off 19/32): on 52/77 vs off 48/79, **p = 0.41**: not significant. Per goal: `rambling-quarter-recap` (the missing-file lesson) 2/4 -> 4/4 with lessons; `typos-replace-letter` 3/4 -> 4/4; five goals pass in both arms; **four fail in both arms** (`terse-deep-folders`, `terse-rocket-icon`, `terse-tack-on-line`, `rambling-three-labelled`), where the checks may be too strict or the model fails regardless. Direction is positive again, still within noise; **no learning benefit is proven**.

## Four-state

| Item | CODE | TEST | LIVE | PROD |
|---|---|---|---|---|
| Embedding load at boot, failure reason in the thought stream, ranker named | yes | covered by existing semantic tests | yes (:3000 trace) | no |
| Superseded exclusion, duplicate collapse | yes | yes | partly (superseded gone from the live trace; duplicate collapse not seen live) | no |
| Non-empty conflict gate | yes | yes | not triggered live | no |
| Final-answer check vs real model | yes | yes (scripted) | 1 false flag, 0 wrong answers to fix in 6 cases | **UNPROVEN** |
| Live-state classifier | yes | yes | n/a | 15/20 vs 12/20 on a small labeled set |
| Learning A/B | driver yes | n/a | 32/48 vs 29/47, pooled p = 0.41 | **not proven** |
