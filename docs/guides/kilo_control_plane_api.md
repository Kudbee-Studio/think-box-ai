# KILO control-plane API (PR #154)

Hermetic HTTP surface upgrade for `/api/v1/control-plane/*`. **CODE COMPLETE /
TEST VERIFIED only** — does not earn KILO LIVE VERIFIED.

## Verify (hermetic)

```bash
python3 scripts/verify_kilo_control_plane_api.py
python3 scripts/verify_kilo_spine.py
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr154 -v
```

## Local auth

Set `THINKBOX_CONTROL_PLANE_TOKEN` or `THINKBOX_CONTROL_PLANE_ALLOW_DEV_TOKEN=1` for
`Bearer dev-only-local-token` (tests only).

## Routes

- `GET /contract` — API version + route catalog
- `GET /status`, `/admission`, `/capacity`
- `GET|POST /operations`, `GET /operations/{id}`, `POST /operations/{id}/cancel`
- `GET /receipts/chain` — conditional GET with ETag (status + page; filters)
- `GET /receipts/chain/page` — paginated receipts only
- `GET /receipts/chain/head` / `tail` — boundary reads
- `GET /receipts/{receipt_id}/validate` — fail-closed link check (`If-Match` → 412 on mismatch)

No live Mercury or Box HTTP from these handlers in CI.

## Prior gates

Requires PR #153 `live-smoke-operator` spine block to pass first.
