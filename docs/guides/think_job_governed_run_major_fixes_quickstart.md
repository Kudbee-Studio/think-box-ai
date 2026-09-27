# Think Job governed run major fixes (PR #188)

Hermetic **25-fix** pack on `run_governed` / F132 spine. **Not LIVE VERIFIED** — no Mercury calls in gate paths.

## Verify

```bash
python3 scripts/verify_kilo_pr188_think_job_governed_run_major_fixes.py
python3 -m unittest tests.unit.test_think_job_governed_run_major_fixes tests.unit.test_kilo_live_proof_readiness_pr188 -v
```

## Related

- PR #187 receipt major fixes (upstream gate)
- `docs/guides/governed_run_http.md` — HTTP contract
- Gate id: `think-job-governed-run-major-fixes`
