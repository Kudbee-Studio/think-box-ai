# KILO proof-schema guide (PR #148)

Hermetic JSON contract for KILO live-proof and ledger artifacts. Gate id: **`proof-schema`**.

## Quick verify

```bash
python3 scripts/verify_kilo_proof_schema.py
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr148 -v
```

Runs after `verify_kilo_swarm_instrumentation.py`. No live Mercury, GPU, or Box HTTP.

## Document shape

- Schema version: `kilo-proof-v1`
- Required: `receipt_key`, `etag`, `prior_gate_ids`, `gates`, `cues`, four-state fields
- Dependency graph: `gates[].depends_on` references `node_id` values; cycles rejected
- Cues: `user` may set `counts_as_user_intent: true`; injected types must not
- DoD: `definition_of_done[]` with `met` booleans; LIVE claims require all `met` and `live_verified`

## Fixtures

See `data/kilo_proof_schema/fixtures/README.md`.

Four-state on this gate: **CODE COMPLETE / TEST VERIFIED** only.
