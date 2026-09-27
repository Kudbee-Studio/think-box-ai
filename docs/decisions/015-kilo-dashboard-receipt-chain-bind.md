# ADR 015: Dashboard bind for receipt-chain / END LINK

**Date:** 2026-09-23
**Status:** Accepted

## Context

PR #155 deepened receipt-chain reads and conditional HTTP. Operators need a hermetic dashboard surface to exercise chain pagination, ETag behavior, and the proprietary **END_LINK** validate API without live Box/Mercury calls.

## Decision

Add PR #156 gate `dashboard-receipt-chain-bind` with:

- Python client/models bound to existing control-plane payloads
- Static control-plane UI (`receipt_chain_dashboard.html`) and JS client
- Spine + verify script; `live_verified` remains false

## Consequences

- Receipts nav links to chain dashboard and END_LINK validate
- Dashboard slots gain `receipt_chain_end_link` kind for future registry fixtures
