# ADR 007: KILO proof-schema gate (PR #148)

**Date:** 2026-09-23
**Status:** Accepted

## Context

Live-proof readiness arc PR #148 must close gate `proof-schema` so KILO proof and ledger
artifacts have a hermetic JSON contract before PR #150 Live proof execution. Founder
requested cue/dependency patterns from KudbeeZero/kudbee-kirocrew (read-before-touch
dependency router, injected cues vs user speech, DoD checklist, halt sentinels) without
vendoring kirocrew or adding runtime dependencies.

## Options Considered

1. JSON Schema file only with external validator dependency
2. Python dict schema + stdlib validators in `thinkbox/kilo_proof_schema.py`
3. Duplicate proof shapes already in governance-evidence only

## Decision

We chose option 2: `kilo_proof_json_schema()` documents the contract; `validate_proof_document`
implements fail-closed checks (cycles, cue types, four-state honesty, redaction). Gate layers
on `swarm-instrumentation` like prior arc modules. Proof admission for a gate is the
**intersection** of prerequisites: every `prior_gate_ids` entry must correspond to a gate node
with `hermetic_operator_ok: true` (analogous to POLICY∩PROFILE composition in kirocrew).

Injected cue types (`injected_nudge`, `cron`, `subagent_completion`, `gate_ready`, `blocker`)
must set `counts_as_user_intent: false` so autonudge-like loops cannot masquerade as user
intent in proof records.

## Consequences

- Fixtures under `data/kilo_proof_schema/fixtures/` exercise valid and negative paths.
- Spine operator verify adds `scripts/verify_kilo_proof_schema.py` after swarm gate.
- Four-state remains capped at TEST VERIFIED until PR #150 Live proof.
- Next non-binding arc gate: #149 `dashboard-slots`.
