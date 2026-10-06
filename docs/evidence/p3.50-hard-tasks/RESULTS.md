# P3.50 results: both cloud models still score 100% on the harder set

Written after reading every row of `run1-results.json`. The criteria in `PLAN.md` were not changed. Cloud models only; no local model was run.

| Model | Rows | Verified, no flags | Independent test agrees | Median time | Max time | Median tokens/row | Median tool calls |
|---|---|---|---|---|---|---|---|
| mercury-2 | 24 (12 tasks x 2) | **24 / 24** (Wilson 95%: 86-100%) | 24 / 24 | 2.6 s | 3.9 s | 7,121 | 4 |
| deepseek-chat (served by `deepseek-flash`) | 24 | **24 / 24** (86-100%) | 24 / 24 | 5.1 s | 9.4 s | 8,324 | 4.5 |

- All validity criteria held (V0 to V5; the independent unsandboxed `node --test` agreed with the sandbox on all 48 verdicts; no row flagged; task-set sha256 matched `0001b611...fa08`). Spend at Mercury's rates: $0.056 (DeepSeek's real spend is not computed here; its token total was 219,714).
- **H07, the four-edit rename across two files** (the one I expected could fail on the interface): verified by both models in both trials, with both files changed. The interface limit I worried about did not bite.
- By the pre-registered reading: both models are at or above 22/24, so **the set is still at the ceiling** and does not separate them.

## What this does and does not show
- Shown: on 12 harder tasks (symptom-only goals, bug in another file, multi-line fixes, new validation behaviour, async, regex, a cross-file rename), two trials each, the SIMULATE patch worker produced a verified fix 48 times out of 48 with two different cloud models, and the independent check agreed every time. The previous 15/15 was not just easy one-line fixes.
- DeepSeek was about twice as slow per row as Mercury (5.1 s vs 2.6 s median) and used about 17% more tokens at the median.
- Not shown: anything about harder, real repositories (these are small hand-written fixtures I wrote, then froze; the models may have seen similar code in training); anything about local models; that the patches are good beyond passing the fixture's tests. A ceiling means this task set cannot find the limit, not that there is none.
- Next step if wanted: tasks built from real bugs in a real repository, with bigger files and tests that do not point at the answer.

## Disclosures
- Sampling unseeded; two trials per task; one run.
- The script approves the sandbox run on the founder's instruction; no browser.
- DeepSeek was reached as `deepseek-chat`, an alias the API serves as `deepseek-flash`.
