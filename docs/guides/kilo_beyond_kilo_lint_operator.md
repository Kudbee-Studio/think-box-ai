# Beyond-KILO lint operator guide (PR #170)

Hermetic readiness lane for **ruff**, **mypy**, and **bandit** on a **scoped** path set
(`thinkbox/beyond_kilo_lint.py`, `thinkbox/kilo_beyond_kilo_lint.py`). This is **not**
a combined post-#N umbrella and does not nest prior theme evaluators.

## Four-state cap

**CODE COMPLETE / TEST VERIFIED** only. `live_verified: false`, `live_api_called: false`.

## Local commands

```bash
pip install -e ".[lint]"
export KILO_BEYOND_KILO_LINT_EXECUTE=1
python3 scripts/verify_kilo_beyond_kilo_lint.py
```

CI sets `KILO_BEYOND_KILO_LINT_REQUIRE_TOOLS=1` when `CI=true`.

PR **#172** CI step (after fast spine): `pip install -e ".[lint]"` then
`KILO_BEYOND_KILO_LINT_EXECUTE=1 python3 scripts/verify_kilo_beyond_kilo_lint.py`.

## Mypy scope

Mypy runs with `--follow-imports=skip` on gate modules only (gradual adoption).

## Spine

`python3 scripts/verify_kilo_spine.py` includes `beyond_kilo_lint_readiness` in **fast**
mode (static checks; linters run via `verify_kilo_beyond_kilo_lint.py` in CI).

## Gradual adoption

Expand `LINT_SCOPE_REL_PATHS` in `thinkbox/beyond_kilo_lint.py` in follow-on PRs; do not
nest combined post-#N umbrellas when widening scope.
