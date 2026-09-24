# Think Job PR #185 — local environment

Run the lifecycle fix pack on a developer machine. **Hermetic only** — no live Mercury or Box HTTP.

## Prerequisites

- Python **3.10+**
- Repo checkout with `pip install -e .` (recommended inside a virtualenv)

## One-shot local workflow

```bash
chmod +x scripts/run_pr185_local.sh
./scripts/run_pr185_local.sh
```

Dry-run (list steps only):

```bash
python3 -m thinkbox.think_job_lifecycle_fixes.local.workflow_cli --dry-run
```

## Verify local environment + gate

```bash
python3 scripts/verify_pr185_local_environment.py
python3 scripts/verify_kilo_pr185_think_job_lifecycle_fixes.py
```

## Unit tests (PR #185)

```bash
python3 -m unittest tests.unit.test_think_job_pr185_fixes \
  tests.unit.test_kilo_live_proof_readiness_pr185 \
  tests.unit.test_think_job_pr185_local_env -v
```

**Four-state:** CODE COMPLETE / TEST VERIFIED only — not LIVE VERIFIED.
