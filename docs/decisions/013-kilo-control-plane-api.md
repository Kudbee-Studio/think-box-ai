# ADR 013: Control-plane API surface upgrade (PR #154)

**Date:** 2026-09-23
**Status:** Accepted

## Context

Post-arc maintenance (#151–#153) added smoke evidence and operator paths. The FastAPI
control-plane router existed in stub form but was not mounted on `backend/main.py` and
lacked versioned envelopes, operation CRUD, or spine verification.

## Options Considered

1. Greenfield REST API parallel to `thinkbox/agent/control_plane/`
2. Extend existing agent control-plane modules + bind FastAPI routes with hermetic clients

## Decision

Option 2: add `thinkbox/control_plane_api_*` helpers, wire `backend/api/v1/control_plane.py`
with fail-closed auth, and gate via `thinkbox/kilo_control_plane_api.py` +
`scripts/verify_kilo_control_plane_api.py` layered on PR #153.

## Consequences

- Default/CI paths keep `live_api_called: false` and audit `live_verified: false`.
- Founder live proof still requires ack + Box URL + recorded smoke (#152/#153).
- Spine and post-season checklist include the new verify script.
