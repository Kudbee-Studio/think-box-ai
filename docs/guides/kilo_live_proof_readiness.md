# KILO Live-proof readiness (PR #141 spine)

Canonical runbook: [`docs/runbooks/kilo-live-proof-readiness.md`](../runbooks/kilo-live-proof-readiness.md)

Hermetic verification:

```bash
python3 scripts/verify_kilo_spine.py
python3 scripts/verify_kilo_env_matrix.py
python3 scripts/verify_kilo_substrate_checklist.py
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr141 -v
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr142 -v
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr143 -v
```

PR **#142** closes the `env-matrix` gate (`thinkbox/kilo_env_matrix.py`). PR **#143** closes `substrate-checklist` (`thinkbox/kilo_substrate_checklist.py`). Do not claim KILO LIVE VERIFIED until PR #150 Live proof artifacts exist.
