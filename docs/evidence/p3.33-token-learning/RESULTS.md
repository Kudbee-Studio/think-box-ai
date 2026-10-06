# P3.33 Think Token learning test: results

Computed only from `raw-*.jsonl` and `tokens.json` by `apps/web/tests/e2e/token-learning-report.ts`, applying the rules pre-registered in `PLAN.md`.

## Stage 1: Mercury teacher and the real pipeline

- Teacher runs: 10; passed (grounded, on disk, machine check) 10; fed to the pipeline 10
- Accepted tokens: 3 (written by mercury-2: 3); Mercury lane spend $0.0145, pipeline spend estimate $0.0084

- Tokens by status: {"accepted":3}

### The accepted tokens, verbatim

- **TT-000003** (lesson, mercury-2) Flag missing coverage by empty search results: If a repo_search in the test folder returns an empty matches list, treat that as a signal that the target code is not exercised. This simple check is reliable for small projects with direct naming.
- **TT-000002** (lesson, mercury-2) Read source snippet before searching: Use repo_read to fetch the relevant lines of a file first. Seeing the exact export signature helps craft precise search queries and avoid false positives.
- **TT-000001** (lesson, mercury-2) Detect untested exported functions via search: Run a repo_search for the export name in the source, then run another repo_search restricted to the test directory. If the second search returns no matches, the export is likely untested. This works because the search tool quickly scans all files for a string.

## Stage 2: held-out A/B (n=20)

Local `qwen2.5:3b`, commit `b398dc27`, held-out goals hash `3d83676e5212`, tokens retrieved for 20/20 goals.

| Arm | Pass (95% Wilson CI) | False accepts | Would escalate | Mean latency |
|---|---|---|---|---|
| A no tokens | 1/20 (5.0%, 0.9%-23.6%) | 14 | 19 | 27.9s |
| B tokens | 0/20 (0.0%, 0.0%-16.1%) | 2 | 19 | 30.5s |

- B minus A: -5.0 pts, paired-bootstrap 95% CI [-15.0, 0.0]; goals only B passed 0, only A passed 1; exact McNemar p=1.0000
- Mercury spend (teacher + pipeline): $0.0229 of the $0.50 cap

## Decision (pre-registered rules)

**Learning benefit: UNPROVEN.**

