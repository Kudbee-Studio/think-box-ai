# KILO receipt-chain / ETag deepen (PR #155)

Hermetic gate id: `receipt-chain-etag` (layers on `control-plane-api`).

## Verify

```bash
python3 -m unittest tests.unit.test_receipt_chain_query tests.unit.test_backend_receipt_chain_pr155 -v
python3 scripts/verify_kilo_receipt_chain_etag.py
python3 scripts/verify_kilo_spine.py
```

## HTTP surface

- `GET /api/v1/control-plane/receipts/chain` — status + page; `If-None-Match` → 304
- `GET /api/v1/control-plane/receipts/chain/page` — cursor pagination; filters `action`, `agent_id`
- `GET /api/v1/control-plane/receipts/chain/head` / `tail` — boundary reads
- `GET /api/v1/control-plane/receipts/{receipt_id}/validate` — fail-closed link check; bad `If-Match` → 412

## Four-state

CODE COMPLETE / TEST VERIFIED only — not KILO LIVE VERIFIED.
