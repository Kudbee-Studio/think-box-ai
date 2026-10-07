# P3.55 experiment plan: grok-4.7 and grok-build-0.1 on the frozen SIMULATE task sets

Written and committed BEFORE any call to these two models on these tasks. The founder pasted xAI's model cards and prices and asked to keep testing. Cloud only.

## Models and path
- `grok-4.7` (xAI: "flagship, long-horizon agentic coding"; listed price $2 in / $6 out per 1M tokens) and `grok-build-0.1` (xAI: "coding model for agentic software engineering"; $1 in / $2 out per 1M, $0.20 cached input). Prices are as the founder pasted them; I have not checked them elsewhere.
- Same endpoint, key and path as P3.52 (`https://api.x.ai/v1`, `XAI_API_KEY`, the convoy SIMULATE patch worker, real sandbox, independent unsandboxed test). The runner already supports `P348_XAI_MODEL`; one model per invocation.
- A 1-token check before this plan (math prompt, no tools) showed all three grok models answer and bill reasoning tokens that `usage.completion_tokens` does not include (e.g. 1 completion token plus 125 to 330 reasoning tokens); that is a separate cost-accounting finding, not part of this experiment.

## Runs (per model)
1. Easy set (15 frozen tasks, hash 6eadb56a...), 1 trial.
2. Hard set (12 frozen tasks, hash 0001b611...), 2 trials = 24 rows.
References not re-run: mercury-2 39/39, deepseek-flash 39/39, grok-4.3 37/39.

## Criteria and reading (stated now)
- Same success and validity criteria (V0 to V5) as P3.50/P3.52; Wilson 95% intervals.
- A model is "as capable as the others on these tasks" at 14/15 or more easy and 22/24 or more hard (the grok-4.3 level).
- Below that, every failing row is read before attributing it (no proposal vs wrong patch vs timeout vs a tool-format failure; a path failure is not a capability result).
- Speed and tokens per row are reported. Dollar cost is NOT computed by the script (it prices tokens at Mercury's rates); the founder can read the xAI usage page for the true spend.
- A model that is slower or costlier is not a failure here; it only affects routing, which is a later decision.

## Not claimed
Nothing about real repositories, local models or other xAI models; unseeded sampling; one run.
