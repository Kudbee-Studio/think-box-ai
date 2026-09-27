# Think Job lifecycle fix pack (PR #185)

Hermetic integration fixes under `thinkbox/think_job_lifecycle_fixes/` bridging **#183** e2e deepen,
**#184** POST `/api/v1/run` deepen, and F131–F140 status/stream contracts.

**Four-state cap:** CODE COMPLETE / TEST VERIFIED only — not LIVE VERIFIED.

## Local environment

See `docs/runbooks/think-job-pr185-local-environment.md`.

```bash
./scripts/run_pr185_local.sh
python3 scripts/verify_pr185_local_environment.py
```

## Verify

```bash
python3 scripts/verify_kilo_pr185_think_job_lifecycle_fixes.py
python3 -m unittest tests.unit.test_think_job_pr185_fixes tests.unit.test_kilo_live_proof_readiness_pr185 tests.unit.test_think_job_pr185_local_env -v
python3 examples/think_job_lifecycle_fixes_quickstart.py
```
