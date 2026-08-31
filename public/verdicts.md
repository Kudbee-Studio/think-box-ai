# Verdict Registry

All Think Job verdicts.

| Job | Verdict | Reason |
|-----|---------|--------|
| [#0001](job-0001/) | unproven | Public APIs don't show both DOGI deploys |
| [#0002](job-0002/) | unproven | Public APIs can't fetch inscription content |
| [#0003](job-0003/) | unproven | Public APIs don't expose inscription content |
| [#0004](job-0004/) | blocked | Wallet endpoints not public |
| job_gpu_find_models | blocked | Needs GPU start + SSH |
| job_gpu_serve_20b | blocked | Depends on find_models |
| job_director_wallet_report_001 | blocked | Director hat not implemented |

## Verdict meanings

- **succeeded** — proof complete
- **failed** — proof failed
- **unproven** — APIs insufficient to prove or disprove
- **blocked** — needs human action or GPU

## By state

**Done:** 3 jobs (all unproven)
**Blocked:** 4 jobs (3 need GPU, 1 needs director)
**Total:** 7 jobs
