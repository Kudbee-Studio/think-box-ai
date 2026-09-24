# Think Job hermetic e2e quickstart (PR #183)

Hermetic toolkit under `thinkbox/think_job_e2e_deepen/` deepening Think Job
status/stream/UI and e2e scaffold surfaces from merged PRs #127–#140. **Four-state cap:**
CODE COMPLETE / TEST VERIFIED only — not LIVE VERIFIED.

## Verify gate

```bash
python3 scripts/verify_kilo_pr183_think_job_hermetic_e2e.py
python3 -m unittest tests.unit.test_think_job_hermetic_e2e tests.unit.test_kilo_live_proof_readiness_pr183 -v
```

## Example

```bash
python3 examples/think_job_hermetic_e2e_quickstart.py
```

## Environment

- `THINK_JOB_E2E_DEEPEN_DRY_RUN=true` (required; fail-closed otherwise)
- `THINK_JOB_E2E_DEEPEN_REDACT=true` (default)
- `THINK_JOB_E2E_DEEPEN_MAX_STEPS=64` (bounded hermetic runner)

No Box URL, Mercury, or governance tokens are required for this gate.
