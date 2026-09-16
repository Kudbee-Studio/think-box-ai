# Skill: test-validate

**Description:** Run, validate, and interpret test results

# When to Use

Use before committing, after changes, and when investigating failures.

# Workflow

## Step 1 — Run All Tests

```bash
python3 -m unittest discover tests/ 2>&1 | tail -5
```

## Step 2 — Run Specific Module

```bash
python3 -m unittest tests.unit.test_session_tracker -v
python3 -m unittest tests.unit.test_substrate -v
python3 -m unittest tests.unit.test_swarm_instrumentation -v
```

## Step 3 — Interpret Results

| Result | Meaning | Action |
|--------|---------|--------|
| OK | All tests pass | Safe to commit |
| FAIL | Test assertion failed | Fix the code or fix the test (if test is wrong) |
| ERROR | Unhandled exception | Debug and fix |
| SKIP | Optional dependency absent | Expected, no action needed |

## Step 4 — Test Count Baseline

Current baseline: **390 tests OK, 1 skip** (optional fastapi/uvicorn in sandbox).

If count drops significantly, investigate immediately.

## Step 5 — New Test Requirements

Every public function needs at least one test covering:
- Valid input
- Invalid input (fail-closed where appropriate)
- Edge cases

# Rules

- Never commit with failing tests (unless documented as known issues)
- Never skip tests to make the count look better
- Test counts must be honest — document any expected skips
- Run tests before and after every commit
