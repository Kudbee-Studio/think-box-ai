# KILO dashboard-slots (PR #149)

Hermetic slot registry for control-plane Live-proof bindings. **Not** a live dashboard HTTP surface.

## Operator

```bash
python3 scripts/verify_kilo_dashboard_slots.py
```

Layers on `verify_kilo_proof_schema.py`. Expect `live_api_called: false` and `four_state_max: TEST_VERIFIED`.

## Fixtures

See `data/kilo_dashboard_slots/fixtures/README.md`.

## Multiplex identity

`build_multiplex_digest_identity(receipt_key, etag, dashboard_revision=…)` must match each slot `bind.multiplex_digest_id` when set. Receipt keys use `thinkbox.think_job_status_ui.normalize_receipt_key`.
