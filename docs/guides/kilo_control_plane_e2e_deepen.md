# KILO control-plane E2E deepen (PR #162)

Hermetic end-to-end (HTTP TestClient) coverage for receipt-chain / END_LINK control-plane
routes after PR #161 API ops harden. **No live Box/Mercury HTTP.**

## Four-state

- CODE COMPLETE / TEST VERIFIED only
- `live_verified: false`
- `live_api_called: false`
- `four_state_max`: TEST_VERIFIED

## Harness

- `tests/e2e/control_plane_hermetic.py` — isolated FastAPI client + seed helpers
- `thinkbox/control_plane_e2e_assertions.py` — envelope / ops / integrity assertions

## E2E modules (F162)

| Module | Coverage |
|--------|----------|
| `test_f162_cp_validate_single_e2e` | Single validate + 404 fail-closed |
| `test_f162_cp_batch_validate_e2e` | Batch validate + Idempotency-Key replay |
| `test_f162_cp_chain_filters_e2e` | Chain list filters + invalid filter 400 |
| `test_f162_cp_integrity_fields_e2e` | `prev_receipt_id`, `link_integrity` |
| `test_f162_cp_ops_envelope_e2e` | Ops timing / stack_layers inside 200 |
| `test_f162_cp_fail_closed_e2e` | Batch body errors + auth 401 |

## Verify

```bash
python3 scripts/verify_kilo_control_plane_e2e_deepen.py
python3 -m unittest tests.e2e.test_f162_cp_validate_single_e2e tests.e2e.test_f162_cp_batch_validate_e2e
python3 -m unittest discover tests/e2e -p 'test_f162_*'
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr162 -v
```
