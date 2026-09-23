# KILO END LINK API / ops harden (PR #161)

Hermetic hardening for control-plane END LINK routes after PR #159–#160:
chain-filter validation, normalized `failure_code` values, ops timing metadata,
and Idempotency-Key replay for batch validate.

## Four-state

**CODE COMPLETE / TEST VERIFIED** only — not KILO LIVE VERIFIED, not PRODUCTION READY.

## Gate

- Gate id: `end-link-api-ops-harden`
- Verify: `python3 scripts/verify_kilo_end_link_api_ops_harden.py`
- Prior gate: `receipt-chain-end-link-docs` (PR #160)

## Operator notes

- `GET /receipts/chain` and `/receipts/chain/page` reject unsafe filter query values (400).
- `GET /receipts/{id}/validate` responses include `ops.timing_ms` and `idempotent_retry_safe: true`.
- `POST /receipts/validate/batch` supports optional `Idempotency-Key` for safe replay.
- All envelopes keep `live_api_called: false` and `live_verified: false` on spine paths.

See also: `docs/guides/kilo_receipt_chain_end_link_operator.md`.
