# Think Job POST /run contract deepen quickstart (PR #184)

Hermetic toolkit under `thinkbox/think_job_post_run_deepen/` deepening `POST /api/v1/run`
and F131 contract surfaces after merged **#183**. **Four-state cap:** CODE COMPLETE /
TEST VERIFIED only — not LIVE VERIFIED.

## Verify gate

```bash
python3 scripts/verify_kilo_pr184_think_job_post_run_deepen.py
python3 -m unittest tests.unit.test_think_job_post_run_deepen tests.unit.test_think_job_post_run_major_fixes tests.unit.test_kilo_live_proof_readiness_pr184 -v
```

## Example

```bash
python3 examples/think_job_post_run_deepen_quickstart.py
```

## Environment

- `THINK_JOB_POST_RUN_DEEPEN_DRY_RUN=true` (required; fail-closed otherwise)
- `THINK_JOB_POST_RUN_DEEPEN_MAX_PAYLOAD=65536` (bounded request body)

No Box URL, Mercury, or live governance execution in this gate.
