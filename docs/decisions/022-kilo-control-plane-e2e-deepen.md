# ADR 022: KILO control-plane E2E deepen (PR #162)

**Date:** 2026-09-23  
**Status:** Accepted

## Context

PR #154–#161 shipped control-plane receipt-chain / END_LINK HTTP routes and ops harden
(#161) with unit-level backend tests. We need hermetic near-E2E coverage without live
Box/Mercury HTTP.

## Decision

Add FastAPI TestClient e2e modules (F162) plus a `control-plane-e2e-deepen` KILO gate
that runs the suite in CI via `scripts/verify_kilo_control_plane_e2e_deepen.py`.

## Consequences

- Spine adds `control_plane_e2e_deepen`; `pr162_gate_id` points at this gate.
- Audit pass `pr162` documents `live_verified: false` only.
