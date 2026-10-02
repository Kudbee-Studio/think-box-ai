# ADR 029 P3.8: choosing the ranker on an untouched set (2026-10-02)

Mercury spend: **$0.067** (the A/B; the ranker comparison is offline).

## Decision set (set 4) and rule, fixed before the run

12 goals over real lessons in styles unlike sets 1 to 3 (terse, long and rambling, typos), expected lessons committed in `e4a838d7` before any ranker ran on them; `p37-seed.db` (21 lessons with `when_to_use`); frozen clock; run exactly once (`scripts/think-token-ranker-eval.mjs`, raw `p38-ranker-eval-set4.json`).
Rule, stated in that commit: the ranker with the best hit@3 becomes the default; a tie goes to the simpler one (cosine < cosine-tiebreak < lexical < hybrid); the A/B runs only if the winner reaches 9/12. Rankers: lexical (P3.2), hybrid (P3.6), cosine (cosine only, floor 0.15), cosine-tiebreak (cosine in buckets of 0.02, BM25 breaks ties inside a bucket).

| Ranker | hit@1 | hit@3 |
|---|---|---|
| lexical | 2 / 12 | 5 / 12 |
| hybrid (the previous default) | 4 / 12 | 8 / 12 |
| **cosine** | **7 / 12** | **9 / 12** |
| cosine-tiebreak | 7 / 12 | 9 / 12 |

Cosine and cosine-tiebreak tie on hit@3 (and hit@1, same ranks on every goal), so under the rule the simpler one, **plain cosine, is now the default**. The other three stay behind `THINKBOX_RETRIEVER`. Without a goal vector (model not loaded, embeddings off) ranking falls back to lexical.
Misses for cosine: `rambling-quarter-recap` (missing-no-invent), `terse-memo-above` (dotdot-path) in no ranker's top 3; `typos-replace-letter` (replace-not-append) found only by lexical and hybrid (rank 3).

What cosine drops compared with hybrid: the near-duplicate diversity filter, the genericness factor and the lesson's own score. They did not help on any of the four sets, but production behavior with many near-duplicate lessons is unmeasured.
Sample size: 12 goals, one author, one run; a difference of one goal (cosine 9 vs hybrid 8) is within what rewording could change. The decision followed the pre-set rule; it is not strong evidence that cosine is better than hybrid, only that it is not worse and is simpler. It does reach 9/12 where lexical reaches 5/12.

## A/B with the new default (precondition met: 9/12)

Real Mercury 2, real server, p37 seed (21 lessons), the 8 P3.3 goals with objective checks, frozen clock (`THINKBOX_TOKEN_CLOCK`), the "on" server waited 25 s for the model to load, 4 reps per arm = 64 runs. Raw: `p38-ab-cosine-result.json`. Every "on" run was injected with 3 lessons (ranker: cosine).

| Arm | Completed | Objective checks passed | Tool calls (mean) | Steps (mean) | Tokens (mean) | Cost per run |
|---|---|---|---|---|---|---|
| off | 32 / 32 | 19 | 1.44 | 3.88 | 3,733 | $0.00101 |
| on | 29 / 32 (3 timeouts) | 20 | 1.41 | 3.72 | 3,969 | $0.00107 |

Passes among completed runs: on 20 / 29 vs off 19 / 32, **Fisher exact p = 0.59: not significant**. Per goal (off / on of 4): zero-byte 4/4, size-match 4/4, replace-not-append 4/4, json-line 4/4, emoji-utf8 3/4 vs 4/4, and deep-mkdir, path-normalize, recursive-list **0/4 in both arms**. Three of the 8 goals fail in both arms regardless of lessons, which suggests their objective checks are too strict or the task is beyond the model; they were not tuned after seeing results. The three "on" non-completions were timeouts on path-normalize and recursive-list.
**Reading it, no spin:** with the right lessons now being retrieved, there is still no measurable benefit. The five goals the baseline already passes cannot show one, and the three it fails are failed with lessons too. Tokens are not shown to help; the test is also too easy to show it.

## Four-state

| Item | CODE | TEST | LIVE | PROD |
|---|---|---|---|---|
| Four rankers, `THINKBOX_RETRIEVER`, cosine default | yes | yes (13 tests in the semantic file, incl. ranker choice and tie-break) | yes (set 4 eval; the A/B ran on cosine) | no |
| Ranker comparison on an untouched set | | | cosine 9/12 > hybrid 8/12 > lexical 5/12 (hit@3) | UNPROVEN as a general result |
| A/B (cosine default) | driver yes | n/a | 20/29 vs 19/32, p = 0.59 | **no benefit shown** |

**UNPROVEN:** that cosine beats hybrid beyond one goal; behavior with a large store and many near-duplicates; any learning benefit.
