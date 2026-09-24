# CI spine-trust operator guide (PR #172)

Hermetic gate ensuring GitHub PR CI trusts **one fast** `verify_kilo_spine.py` pass
plus explicit beyond-KILO lint execute — without duplicating per-gate `verify_kilo_*`
scripts that spine already aggregates.

## Four-state cap

**CODE COMPLETE / TEST VERIFIED** only. `live_verified: false`, `live_api_called: false`.

## Local commands

```bash
python3 scripts/verify_kilo_pr172_ci_spine_trust.py
PYTHONUNBUFFERED=1 python3 -u scripts/verify_kilo_spine.py
```

## PR CI contract

Required snippets in `.github/workflows/test.yml`:

- `python3 -m unittest discover`
- `verify_kilo_spine.py` (fast default — **not** `--e2e` on every PR)
- `pip install -e ".[lint]"` + `KILO_BEYOND_KILO_LINT_EXECUTE=1` + `verify_kilo_beyond_kilo_lint.py`
- `scan_doc_secrets.py`

Individual `scripts/verify_kilo_*` remain for **operator** local runs; do not re-add them to PR CI.

## Fixtures

Workflow shape fixtures live under `data/kilo_pr172_ci_spine_trust/fixtures/` for hermetic
positive/negative manifest checks.
