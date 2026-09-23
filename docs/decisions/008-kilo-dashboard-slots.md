# ADR 008: KILO dashboard-slots hermetic gate

**Date:** 2026-09-23  
**Status:** Accepted

## Context

PR #139–#140 established receipt-keyed watch and jobs-digest multiplex panel helpers. PR #148
added proof JSON schema with receipt/etag, cues, and gate dependencies. Live-proof UI needs a
hermetic slot registry before any live HTTP dashboard work.

## Options Considered

1. Extend `think_job_status_ui` with Live-proof claims in-browser only  
2. New `thinkbox/kilo_dashboard_slots.py` gate module layered on proof-schema  

## Decision

We chose option 2: a dedicated PR #149 gate with fixtures, operator script, and spine wiring.
Slots bind receipt/etag/digest identity; fail-closed on stale/unbound/multiplex conflicts.
`definition_of_done_display` is display-only and cannot assert LIVE VERIFIED.

## Consequences

- Spine requires `dashboard_slots.hermetic_operator_ok` after proof-schema.  
- PR #150 `live-proof-exec` remains the only path to earn LIVE VERIFIED for KILO Live proof.
