# P3.55 results: grok-4.7 and grok-build-0.1 on the frozen SIMULATE task sets

Written after reading every row of the four result files. The criteria in `PLAN.md` were not changed. Cloud only.

| Model | Easy set (15, 1 trial) | Hard set (12 x 2 = 24) | Median time (easy / hard) | Median tokens per row (easy / hard) |
|---|---|---|---|---|
| mercury-2 (earlier) | 15/15 | 24/24 | n/a / 2.6 s | n/a / 7,121 |
| deepseek-flash (earlier) | 15/15 | 24/24 | n/a / 5.1 s | n/a / 8,324 |
| grok-4.3 (P3.52) | 15/15 | 22/24 | 6.6 s / 6.7 s | 6,863 / 7,278 |
| **grok-4.7** | **15/15** | **22/24** (Wilson 95%: 74-98%) | 7.2 s / 7.5 s | 11,535 / 12,140 |
| **grok-build-0.1** | **15/15** | **22/24** (74-98%) | 11.0 s / 16.2 s (max 66 s) | 7,213 / 11,749 |

All validity criteria held in all four runs (V0 to V5); the independent unsandboxed test agreed with the sandbox on all 78 verdicts; no row was flagged; both task-set hashes matched.

## The misses
Every miss, for both models, is **H10 in both trials**, the same task xAI's grok-4.3 missed: the patches throw `RangeError('invalid age')` for non-numbers, negatives and values over 150, which is what the goal says, but the fixture's test also requires the empty string to be rejected (the goal never says so; `Number('')` is 0). Mercury and DeepSeek added that check on their own. So the three xAI models behave the same on this task: they follow the literal wording. It is one underspecified task, not three independent failures, and the frozen set was not edited. On the other 11 hard tasks every xAI model scored 22/22.

## Reading against the pre-registered rule
Both models reach 15/15 easy and 22/24 hard, the same level as grok-4.3: **as capable as the others on these tasks** (still a ceiling; no limit found).

## Speed and cost
- grok-build-0.1 is the slowest by far (median 16 s on the hard set, one task 66 s). grok-4.7 is about as fast as grok-4.3 but uses roughly 1.7x the tokens.
- **The token counts above exclude reasoning tokens.** The experiment ran on code that did not count them (xAI bills reasoning as output and reports it apart from `completion_tokens`; found while preparing this experiment and fixed in P3.56). So the xAI token and cost figures here are LOWER than the truth, and these results are NOT put into the routing table: a cost ranking built on them would favour the xAI models unfairly. The true cost per task needs a re-run on the fixed code, which records the provider's billed cost.

## Not shown
Real repositories, local models, other xAI models; unseeded sampling; one run; dollar cost.
