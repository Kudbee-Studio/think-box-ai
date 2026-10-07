# P3.57 results: what each cloud model really costs per SIMULATE task

Written after reading every row of the ten result files. The criteria in `PLAN.md` were not changed. Cloud only; one trial per task; this run is on the code that counts reasoning tokens and uses the provider's billed cost (P3.56).

| Model | Verified (easy 15 + hard 12) | Median USD per task | Mean | Run total | Median time | Median tokens | Cost basis |
|---|---|---|---|---|---|---|---|
| mercury-2 | 25 / 27 | **$0.0021** | $0.0023 | $0.061 | 2.6 s | 6,654 | tokens at Inception's price list |
| deepseek-flash | 27 / 27 | **$0.0028** | $0.0032 | $0.086 | 5.4 s | 7,989 | tokens at an ESTIMATED price (DeepSeek reports no billed cost) |
| grok-build-0.1 | 27 / 27 | **$0.0060** | $0.0068 | $0.184 | 9.5 s | 9,675 | xAI billed |
| grok-4.3 | 26 / 27 | **$0.0064** | $0.0068 | $0.183 | 6.2 s | 7,339 | xAI billed |
| grok-4.7 | 26 / 27 | **$0.0127** | $0.0135 | $0.364 | 5.9 s | 11,943 | xAI billed |

All validity criteria held in all ten runs (V0 to V5); the independent unsandboxed test agreed with the sandbox on all 135 verdicts; no row was flagged; task hashes matched.

## What it shows
- **The cost order is Mercury < DeepSeek < grok-build-0.1 < grok-4.3 < grok-4.7**, at roughly 1 : 1.3 : 2.9 : 3.1 : 6.2. grok-4.3 costs about $0.0064 per task, about 5x lower than the earlier $0.035 estimate and about 3x Mercury.
- **Mercury is not perfect.** It missed two tasks this time though it had gone 39 for 39 before: T05 (a wrong patch that put `return sum;` inside the loop, caught by the sandbox and the independent test) and H10 (the empty-string requirement the goal never states, which every model but DeepSeek missed in at least one run). Pooled over all runs Mercury is 64 of 66, DeepSeek 66 of 66, grok-4.3 63 of 66, grok-4.7 63 of 66, grok-build-0.1 64 of 66. Single runs are noisy and sampling is unseeded; I would not rank the models by one miss.
- Every model clears the routing rule (at least 20 tasks, at least 90% verified), so routing is decided by measured cost, then speed.

## Not shown
DeepSeek's real price (its dollar figure uses an estimated rate); goals other than SIMULATE patches; real repositories; one trial per task, so cost medians have sampling noise; reasoning-token cost for Mercury and DeepSeek if they ever report it separately (neither did in these runs).
