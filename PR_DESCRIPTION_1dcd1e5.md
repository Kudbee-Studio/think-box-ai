Title: fix(test): correct SCHEMA_DIR to SCHEMA_PATH in test_jobs.py

## Summary
Fixes a test-suite bug where `SCHEMA_DIR` was referenced instead of
`SCHEMA_PATH` in `test_all_jobs_have_valid_verdict()`.

## Problem
The test referenced an undefined/incorrect schema path symbol, which could
cause schema resolution to fail or behave inconsistently.

## Change
- `tests/unit/test_jobs.py`
  - Replaced `SCHEMA_DIR` with `SCHEMA_PATH`

## Verification
- Swarm instrumentation tests: 23/23 passing
- Repository clean after commit
- Commit: `1dcd1e5`
- Branch: `agent/dashboard-command-center/kilo-20260916`

## Risk
Low. Test-only change.