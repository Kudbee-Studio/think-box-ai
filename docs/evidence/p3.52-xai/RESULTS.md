# P3.52 results: xAI grok-4.3 as a third cloud reference

Written after reading every row of `easy-results.json` and `hard-results.json`. The criteria in `PLAN.md` were not changed. Mercury and DeepSeek are the earlier runs (P3.49 and P3.50), not re-run.

| Model | Easy set (15 tasks, 1 trial) | Hard set (12 tasks, 2 trials) | Median time (easy / hard) | Median tokens per row (easy / hard) |
|---|---|---|---|---|
| mercury-2 (earlier) | 15 / 15 | 24 / 24 | 2.6 s hard | 7,121 hard |
| deepseek-chat = deepseek-flash (earlier) | 15 / 15 | 24 / 24 | 5.1 s hard | 8,324 hard |
| **grok-4.3 (xAI)** | **15 / 15** | **22 / 24** (Wilson 95%: 74-98%) | 6.6 s / 6.7 s | 6,863 / 7,278 |

All validity criteria held in both runs (V0 to V5); the independent unsandboxed test agreed with the sandbox on all 39 verdicts; no row was flagged; both task-set hashes matched. xAI's cost is not computed (the script's pricing is Mercury's).

## The two misses, read row by row
Both are **H10, in both trials**: `proposal_wrong`, the patch applied and a real test failed. The patch throws `RangeError('invalid age')` when the number is not finite, below 0 or above 150, which matches the goal as written. The fixture's test also requires that the **empty string** be rejected (`Number('')` is 0, so it passes the guard). The goal never mentions the empty string. Mercury and DeepSeek passed H10 by adding an explicit empty-string check on their own initiative.

So: H10's goal is underspecified for a hidden test case, and that is a flaw in my task, not only a model difference. I did not edit the frozen set. Read it as: grok-4.3 follows the literal wording of the goal more closely and the other two anticipated an unstated edge case; two trials with identical misses is one task, not a distribution. On the 11 other hard tasks it was 22 of 22.

## What this shows and does not
- Shown: a third provider (xAI) works through the same worker-agent path with no product code, and verifies 15 of 15 easy and 22 of 24 hard tasks, every verdict confirmed independently. By the pre-registered reading (at least 22/24 hard and at least 14/15 easy) it is as capable as the other two on these tasks.
- Speed: Mercury is fastest (2.6 s median), then DeepSeek (5.1 s), then grok-4.3 (6.7 s).
- Not shown: anything about real repositories, local models or other grok models; the set is still near the ceiling, so it shows no limit; one run, unseeded sampling.

## Disclosures
- The script approves the sandbox run on the founder's instruction; no browser.
- `grok-4.3` was chosen after a 1-token tool-call check of it and of `grok-4.20-0309-non-reasoning` (both returned a proper tool call); only grok-4.3 was run.
