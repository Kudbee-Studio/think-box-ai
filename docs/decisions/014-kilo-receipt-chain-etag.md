# ADR 014: Receipt-chain and ETag deepen (PR #155)

**Date:** 2026-09-23
**Status:** Accepted

## Context

PR #154 mounted control-plane HTTP routes with a basic `/receipts/chain` conditional GET.
PR #140 introduced shared browser etag store helpers. The chain read path still lacked
pagination, head/tail probes, fail-closed link validation, and documented If-Match 412
behavior aligned with one canonical ETag helper path.

## Options Considered

1. New parallel receipt stack under `thinkbox/receipts/`
2. Extend `thinkbox/agent/control_plane/store.py`, PR #140 etag store, and #154 routes

## Decision

Option 2: add `receipt_chain_query`, `control_plane_conditional`, deepen
`backend/api/v1/control_plane.py` and gate via `receipt-chain-etag` layered on
`control-plane-api`.

## Consequences

- Hermetic default; `live_verified: false` on audit passes.
- Founder Live proof still requires ack + Box URL + recorded smoke (#152/#153).
- Spine includes `scripts/verify_kilo_receipt_chain_etag.py`.
