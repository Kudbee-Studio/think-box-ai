# KILO dashboard receipt-chain / END LINK bind (PR #156)

Hermetic gate id: `dashboard-receipt-chain-bind` (layers on `receipt-chain-etag`).

## END LINK (proprietary)

Operator validate API label: **END_LINK**

- `GET /api/v1/control-plane/receipts/{receipt_id}/validate`
- `If-None-Match` → 304 on chain/page reads (via dashboard client)
- `If-Match` mismatch → **412** on END LINK validate (fail-closed)

## UI

- `public/control-plane/receipt_chain_dashboard.html` — chain page, head/tail, END_LINK panel
- `public/control-plane/control_plane_end_link_client.js` — fetch helpers
- Deep link from `receipts.html` → chain dashboard + Think Job watch

## Verify

```bash
python3 -m unittest tests.unit.test_dashboard_receipt_chain_client tests.unit.test_end_link_api tests.unit.test_kilo_live_proof_readiness_pr156 -v
python3 scripts/verify_kilo_dashboard_receipt_chain_bind.py
python3 scripts/verify_kilo_spine.py
```

## Four-state

CODE COMPLETE / TEST VERIFIED only — not KILO LIVE VERIFIED.

See also: `docs/guides/kilo_receipt_chain_end_link_operator.md` (rollup #155–#159).
