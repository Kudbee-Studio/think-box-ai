# P3.35 confirmation of the Think Token effect: results

Computed only from `raw-*.jsonl` and `tokens.json` by `apps/web/tests/e2e/token-learning3-report.ts`, applying the rules pre-registered in `PLAN.md`.

## Stage 1: Mercury teacher and the real pipeline

- Teacher runs 10; verified 10; fed to the pipeline 10; runs that yielded at least one new token **7** (P3.34: 6 of 10); runs whose extract reply was unusable **0** (P3.34: 0 of 10)
- Accepted tokens 7 (written by mercury-2: 7); Mercury lane spend $0.0134, pipeline spend estimate $0.0131

### The accepted tokens, verbatim

- **TT-000009** (tool_pattern, mercury-2) Search whole repo with empty path: Set the repo_search path argument to an empty string to scan every file in the repository, both source and tests, for a given symbol. This quickly finds definitions and test references without needing to list directories.
- **TT-000008** (lesson, mercury-2) Use result_excerpt for immediate reporting of untested exports: After locating an exported function with repo_search, rely on the tool's result_excerpt (which includes file, line, and function name) to announce the missing test directly, skipping extra file reads.
- **TT-000005** (lesson, mercury-2) Inspect test imports to infer covered exports: Read the top of each test file (repo_read) to see which exported symbols are imported; any exported function not listed is likely untested. This works when tests import directly rather than using indirect calls.
- **TT-000004** (lesson, mercury-2) Include export keyword in repo_search to directly locate exported functions: Search for 'export function <name>' instead of just the name; this returns only exported definitions, eliminating a later repo_read check. Use repo_search with query 'export function recoverFrom' to confirm export in one step. Skip this if the name appears in comments or non-export contexts.
- **TT-000003** (lesson, mercury-2) Two‑step search to spot untested exported functions: First locate the function definition with repo_search, then run repo_search for the same name inside the tests folder. If the second search returns no matches, the function lacks test coverage. This works because the absence of references in test files reliably signals missing tests.
- **TT-000002** (fix, mercury-2) Detect missing tests via empty search results: When repo_search on the tests folder returns an empty matches array, treat it as a signal that the target function is untested, and flag it for test creation.
- **TT-000001** (lesson, mercury-2) Confirm export status with repo_read: After locating a function name via search, read a few lines around it with repo_read to ensure it is exported (e.g., starts with 'export function'). This avoids false positives from similarly named internal helpers.

## Primary A/B on 60 fresh held-out goals (n=60)

Local `qwen2.5:3b`, commit `a79de495`, goals hash `79f5ca0f9e0c`, tokens retrieved for 60/60 goals.

| Arm | Pass (95% Wilson CI) | False accepts | tool_failed | malformed | used a retry | Would escalate | Mean latency |
|---|---|---|---|---|---|---|---|
| A no tokens | 2/60 (3.3%, 0.9%-11.4%) | 52 | 0 | 0 | 3 | 54 | 27.6s |
| B tokens | 5/60 (8.3%, 3.6%-18.1%) | 36 | 2 | 9 | 13 | 54 | 48.1s |

- B minus A: +5.0 pts, paired-bootstrap 95% CI [-3.3, 13.3]; goals only B passed 5, only A passed 2; exact McNemar p=0.4531

## Pooled with P3.34 (descriptive only; two independent token sets; not a pre-registered test)

- Pass A 5/90 (5.6%), B 16/90 (17.8%); only B passed 16, only A passed 5; exact McNemar p=0.0266

## Decision (pre-registered rules, primary set only)

Total Mercury spend $0.0265 (cap $0.50). **Learning benefit: UNPROVEN.**

