# KILO API / ops harden (PR #157)

Hermetic hardening for control-plane HTTP, receipt-chain pagination integrity,
idempotency keys, ops rate windows, and structured error envelopes.

## Four-state

**CODE COMPLETE / TEST VERIFIED** only — not KILO LIVE VERIFIED, not PRODUCTION READY.

## Gate

- Gate id: `api-ops-harden`
- Verify: `python3 scripts/verify_kilo_api_ops_harden.py`
- Prior gate: `dashboard-receipt-chain-bind` (PR #156)

## Operator notes

- `Idempotency-Key` header on `POST /api/v1/control-plane/operations` replays the same operation.
- Chain list `limit` query params clamp to 200.
- Receipt page rows validate in-page `prev_receipt_id` linkage.
- Errors return structured envelopes with `live_api_called: false`.

See also: `docs/guides/kilo_receipt_chain_end_link_operator.md`, `docs/guides/kilo_end_link_api_ops_harden.md` (PR #161 stack harden).
