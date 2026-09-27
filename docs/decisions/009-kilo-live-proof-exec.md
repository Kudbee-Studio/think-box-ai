# ADR 009: KILO live-proof-exec (PR #150 season close)

**Date:** 2026-09-23  
**Status:** Accepted

## Context

Arc #141–#150 prepared hermetic gates for an honest KILO Live proof. PR #150 must close
the final gate `live-proof-exec` without executing Live proof or claiming LIVE VERIFIED.

## Options Considered

1. Run bounded Live proof inside PR #150 CI — rejected (violates hermetic arc contract).
2. Hermetic execution-plan module + operator verify + runbook only — chosen.

## Decision

Ship `thinkbox/kilo_live_proof_exec.py` with execution-plan JSON validation, founder ack
(`THINKBOX_SWARM_LIVE_ACK`) and Box URL (`UPSTASH_PUBLIC_BOX_URL`) fail-closed rules,
spine wiring, and season-close markers. Audit passes for PR #150 keep `live_verified: false`.

## Consequences

- Full spine requires `live_proof_exec.hermetic_operator_ok`.
- Cloud Bot stands by after merge; no #151 unless founder asks.
- LIVE VERIFIED requires separate founder-run smoke + artifact + audit flip documented in runbook.
