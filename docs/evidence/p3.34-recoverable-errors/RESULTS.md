# P3.34 re-test of Think Token learning: results

Computed only from `raw-*.jsonl` and `tokens.json` by `apps/web/tests/e2e/token-learning2-report.ts`, applying the rules pre-registered in `PLAN.md`.

## Stage 1: Mercury teacher and the real pipeline

- Teacher runs 10; verified 10; fed to the pipeline 10; runs that yielded at least one new token **6** (P3.33: 1 of 10); runs whose extract reply was unusable **0** (P3.33: 6 of 10)
- Accepted tokens 8 (written by mercury-2: 8); Mercury lane spend $0.0158, pipeline spend estimate $0.0164

### The accepted tokens, verbatim

- **TT-000013** (lesson, mercury-2) Double‑check query spelling/case on empty search results: If repo_search returns zero matches, verify that the search term matches the identifier’s spelling and case; a typo or case mismatch can look a false missing‑coverage signal.
- **TT-000011** (lesson, mercury-2) Target file path in repo_search for quick export lookup: Give repo_search the exact file (e.g., src/audit.ts) when you need to list its exported functions; this avoids scanning the whole repo and returns precise matches instantly.
- **TT-000010** (lesson, mercury-2) Read test imports before searching for coverage: Open the test files with repo_read to list the functions they import, then compare that list to the exported symbols gathered from src files. Any exported function not appearing in the imports list is likely untested.
- **TT-000009** (lesson, mercury-2) Scope repo_search to target directories: Run repo_search with an empty path to locate the source file, then repeat the search within the test folder only. Narrowing the path for the second search speeds up the query and prevents false positives from unrelated directories.
- **TT-000004** (lesson, mercury-2) Report exact line location of uncovered export: After finding an exported function with no test matches, use repo_read to capture its line number and include that line in the output. This lets developers jump straight to the definition and add tests efficiently.
- **TT-000003** (lesson, mercury-2) Read source around the export to confirm exact name before searching: Use repo_read to display a few lines of the source file around the export declaration. Knowing the precise identifier prevents false‑negative searches in tests.
- **TT-000002** (lesson, mercury-2) Treat empty search results as evidence of missing references: If repo_search reports zero matches for a symbol in the test directory, interpret it as a lack of test coverage rather than a tool error. This avoids overlooking untested code.
- **TT-000001** (tool_pattern, mercury-2) Search exported symbols then verify test usage: Run a repo_search for the source file to list exported names, then run another repo_search in the test folder for each name. If the second search returns no matches, the export lacks tests. This two‑step search is fast and reliable for coverage checks.

## Primary A/B on 30 fresh held-out goals (n=30)

Local `qwen2.5:3b`, commit `45fcff47`, goals hash `9fb7ce053a04`, tokens retrieved for 30/30 goals.

| Arm | Pass (95% Wilson CI) | False accepts | tool_failed | malformed | used a retry | Would escalate | Mean latency |
|---|---|---|---|---|---|---|---|
| A no tokens | 3/30 (10.0%, 3.5%-25.6%) | 24 | 0 | 0 | 2 | 27 | 31.0s |
| B tokens | 11/30 (36.7%, 21.9%-54.5%) | 18 | 0 | 0 | 2 | 19 | 21.1s |

- B minus A: +26.7 pts, paired-bootstrap 95% CI [3.3, 46.7]; goals only B passed 11, only A passed 3; exact McNemar p=0.0574

## Regression check on the 20 P3.33 goals (descriptive; already seen, so not a held-out result)

P3.33 on these goals with the old loop: A 1/20 pass, B 0/20; B ended `tool_failed` in 13 of 20 runs.

| Arm | Pass (95% Wilson CI) | False accepts | tool_failed | malformed | used a retry | Would escalate | Mean latency |
|---|---|---|---|---|---|---|---|
| A no tokens | 1/20 (5.0%, 0.9%-23.6%) | 17 | 0 | 0 | 3 | 19 | 29.2s |
| B tokens | 6/20 (30.0%, 14.5%-51.9%) | 13 | 0 | 0 | 1 | 14 | 22.5s |

- B minus A: +25.0 pts, paired-bootstrap 95% CI [0.0, 50.0]; goals only B passed 6, only A passed 1; exact McNemar p=0.1250

## Decision (pre-registered rules, primary set only)

Total Mercury spend $0.0322 (cap $0.50). **Learning benefit: UNPROVEN.**

