# P3.52 experiment plan: xAI (Grok) as a third cloud reference model

Written and committed BEFORE any xAI call on these tasks. The founder has an xAI key and asked to test Mercury, DeepSeek and xAI.

## Model and path
- `grok-4.3` (override `P348_XAI_MODEL`) at `https://api.x.ai/v1` (OpenAI-compatible), key `XAI_API_KEY` from the environment or repo `.env`, never printed (the script checks it is absent from the results). Same convoy SIMULATE patch-worker path, real sandbox and independent unsandboxed test as P3.48 to P3.50; only the endpoint and key differ. No product provider code in this PR.
- Chosen because a 1-token tool-call check (before this plan) showed it answers a function call with a proper `tool_calls` entry; `grok-4.20-0309-non-reasoning` did too. I picked one; the other was not run.
- What leaves the machine: each task's few lines of fixture code, as for DeepSeek.

## Runs
1. The easy set (15 frozen tasks, hash 6eadb56a...), 1 trial.
2. The hard set (12 frozen tasks, hash 0001b611...), 2 trials = 24 rows.
Mercury (15/15 easy; 24/24 hard) and DeepSeek (15/15; 24/24) are the references from earlier runs and are NOT re-run.

## Criteria and reading (stated now)
- Same success and validity criteria (V0 to V5) as P3.50. Wilson 95% intervals.
- xAI ≥ 22/24 on the hard set and ≥ 14/15 on the easy set: it is as capable as the other two on these tasks (still the ceiling; says nothing about limits).
- Below that: I read every failing row (no proposal, wrong patch, timeout, tool-format error) and say which it is before attributing it to the model. A format or HTTP failure is reported as a path failure, not a capability result.
- Speed and tokens are reported descriptively; xAI's cost is not computed (the script prices tokens at Mercury's rates, which is wrong for xAI).

## Not claimed
Anything about real repositories, local models, or grok models other than this one; sampling unseeded; one run.
