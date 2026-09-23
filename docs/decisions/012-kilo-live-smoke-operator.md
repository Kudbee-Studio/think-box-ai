# ADR 012: Live-smoke operator path (PR #153)

**Date:** 2026-09-23
**Status:** Accepted

## Context

PR #152 introduced the bounded live smoke evidence schema, validators, and
`audit_flip_candidate`. Founders still need a **hermetic operator path** to write
`data/thinkboxmd/artifacts/kilo_live_smoke_*.json` and emit audit-flip **candidate**
JSON without live HTTP in CI.

## Options Considered

1. Duplicate binder logic in a new module
2. Extend #152 with a thin operator module + CLI that delegates to existing APIs

## Decision

We chose option 2: `thinkbox/kilo_live_smoke_operator.py` layers on
`thinkbox/kilo_live_smoke_evidence` for build/write/flip helpers. CLI lives at
`scripts/kilo_live_smoke_operator.py`; spine verify at
`scripts/verify_kilo_live_smoke_operator.py`.

## Consequences

- Default/CI paths keep `live_api_called: false` and audit `live_verified: false`.
- Founder live smoke still requires ack + Box URL + recorded artifact after merge.
- Post-season checklist and CI workflow reference the new verify script.
