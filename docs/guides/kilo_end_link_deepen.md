# KILO END LINK deepen (PR #158)

Gate id: `end-link-deepen`  
Four-state max: **TEST_VERIFIED** (not LIVE VERIFIED)

## Scope

- Bulk validate: `POST /api/v1/control-plane/receipts/validate/batch`
- Single validate enrichments: `link_integrity`, `prev_receipt_id`, `failure_code`
- Chain page filters: `status`, `evidence_label`
- Dashboard: `TBEndLink.endLinkBatchValidate` in `control_plane_end_link_client.js`

## Verify

```bash
python3 scripts/verify_kilo_end_link_deepen.py
python3 -m unittest tests.unit.test_end_link_deepen tests.unit.test_backend_end_link_deepen_pr158 tests.unit.test_kilo_live_proof_readiness_pr158 -v
```

Hermetic only — `live_api_called=false`.

Consolidated operator surface: `docs/guides/kilo_receipt_chain_end_link_operator.md`.
