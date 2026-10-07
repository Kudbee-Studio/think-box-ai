# P3.57 experiment plan: what each cloud model really costs per SIMULATE task

Written and committed BEFORE any run. P3.56 fixed the cost accounting (reasoning tokens counted; the provider's billed cost used when it reports one), so for the first time the per-task cost of the xAI models can be measured. The routing table (P3.54) ranks by an estimated cost; this replaces the estimate with a measured one where possible. Cloud only.

## Runs
Five models, one invocation each (each has its own spend cap): mercury-2, deepseek-flash, grok-4.3, grok-4.7, grok-build-0.1. For each: the easy set (15 frozen tasks) and the hard set (12 frozen tasks), 1 trial each = 27 rows per model, 135 rows. Same convoy SIMULATE path, real sandbox and independent test as P3.48 to P3.56. The runner is unchanged except it already reads `P348_DEEPSEEK_MODEL` and `P348_XAI_MODEL`; deepseek is run under its registry name `deepseek-flash` so its tokens are priced.

## What is recorded and how cost is defined
- Per row: the convoy's `cost_usd`. For xAI this is the provider's billed cost (`cost_in_usd_ticks`) summed over the run's calls; for mercury-2 it is tokens at Inception's price list; for deepseek-flash it is tokens at a stated ESTIMATE (DeepSeek reports no billed cost). Each model's cost basis is stated in the results.
- Reported per model: verified count, median and mean USD per task, median seconds, median tokens (reasoning included for xAI).

## Criteria and reading (stated now)
- Validity V0 to V5 as before; a run that fails one is reported invalid.
- Routing eligibility is unchanged: at least 20 measured tasks and at least 90% verified. A model below that is reported, not ranked.
- The measured median USD per task replaces the estimated cost in the ranking only for models measured here; the success counts in the table keep their earlier pooled evidence where they exist.
- A different cost order than the P3.54 estimate is a finding, reported as is.

## Not claimed
Anything about goals other than SIMULATE patches; real repositories; DeepSeek's true price (estimate); unseeded sampling; one trial per task.
