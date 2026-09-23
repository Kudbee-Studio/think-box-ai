# KILO receipt-chain + END_LINK operator surface (#155–#159)

Hermetic operator/founder reference for the control-plane receipt chain and **END_LINK** validate paths shipped in PR #155–#159. This guide does **not** execute live Box/Mercury HTTP.

## Four-state (honesty)

| State | Claimed for #155–#160 spine |
|-------|-----------------------------|
| CODE COMPLETE | Yes |
| TEST VERIFIED | Yes (hermetic unittest + verify scripts) |
| LIVE VERIFIED | **No** — founder-run proof only |
| PRODUCTION READY | **No** |

Audit fields: `live_verified: false`, `live_api_called: false`, `four_state_max: TEST_VERIFIED`.

## Gate stack (newest first)

| PR | Gate ID | Verify script |
|----|---------|---------------|
| **160** | `receipt-chain-end-link-docs` | `scripts/verify_kilo_receipt_chain_end_link_docs.py` |
| **159** | `end-link-operator-ux` | `scripts/verify_kilo_end_link_operator_ux.py` |
| **158** | `end-link-deepen` | `scripts/verify_kilo_end_link_deepen.py` |
| **157** | `api-ops-harden` | `scripts/verify_kilo_api_ops_harden.py` |
| **156** | `dashboard-receipt-chain-bind` | `scripts/verify_kilo_dashboard_receipt_chain_bind.py` |
| **155** | `receipt-chain-etag` | `scripts/verify_kilo_receipt_chain_etag.py` |

Spine: `python3 scripts/verify_kilo_spine.py` (exit 0).

## Receipt chain reads (#155)

- Paginated chain: `GET /api/v1/control-plane/receipts/chain` and `/chain/page`
- Conditional GET: `If-None-Match` → **304** when etag matches
- Head/tail boundary reads
- Per-receipt validate route (fail-closed); bad `If-Match` → **412**

Filters (chain list): `action`, `agent_id` (see `thinkbox/receipt_chain_query.py`).

Integrity fields on receipts: `receipt_id`, `prev_receipt_id`, `etag`, `action`, `agent_id`, `evidence_label`.

See also: `docs/guides/kilo_receipt_chain_etag.md`.

## Dashboard bind (#156)

- Static UI: `public/control-plane/receipt_chain_dashboard.html`
- Hermetic client: `thinkbox/dashboard_receipt_chain_client.py`
- END_LINK validate wired for single-receipt panel

See also: `docs/guides/kilo_dashboard_receipt_chain_bind.md`.

## API / ops harden (#157)

- Structured error envelopes, idempotency keys, rate limits on control-plane routes
- Receipt page link checks

See also: `docs/guides/kilo_api_ops_harden.md`.

## END_LINK deepen (#158)

- batch validate: `POST` batch path (hermetic: `run_end_link_batch_validate`)
- Link integrity: `failure_code`, `link_integrity`, `prev_receipt_id` in validate payloads
- Chain status / evidence_label filters on list reads

See also: `docs/guides/kilo_end_link_deepen.md`.

## Operator UX (#159)

- Batch results table + summary (`summarize_end_link_batch`)
- Chain filter controls: status, `evidence_label`
- Empty / loading / error states; four-state honesty copy in UI
- JS: `public/control-plane/control_plane_end_link_operator_ux.js`

See also: `docs/guides/kilo_end_link_operator_ux.md`.

## Validate workflows (hermetic)

**Single END_LINK validate**

```bash
python3 -c "from thinkbox.dashboard_receipt_chain_client import hermetic_end_link_validate; print(hermetic_end_link_validate('r1'))"
```

**Batch validate + operator summary**

```bash
python3 -c "
from thinkbox.dashboard_receipt_chain_client import ReceiptChainDashboardClient
from thinkbox.agent.control_plane.store import ActionReceiptStore
c = ReceiptChainDashboardClient(ActionReceiptStore())
print(c.summarize_end_link_batch_for_operator(['r1','r2']))
"
```

## Audit pack (#160)

- Era index (partial #155–#159): `docs/audit/passes/2026-09-23-pr155-159-era-consolidated.json`
- PR #160 pass: `docs/audit/passes/2026-09-23-pr160.json`
- PR #161 API/ops harden (hermetic): `docs/guides/kilo_end_link_api_ops_harden.md`
- Checklist: `docs/audit/checklists/kilo-receipt-chain-end-link-docs-pr160.md`

## Era audit close (#162)

Consolidated honesty index for the full control-plane receipt-chain / **END_LINK** era
**#154–#161** (`live_verified: false`, `live_api_called: false`, `four_state_max: TEST_VERIFIED`).

- Full era pack: `pr154-pr161-era-consolidated` →
  `docs/audit/passes/2026-09-23-pr154-161-era-consolidated.json`
- Gate id: `receipt-chain-end-link-era-close` (layers `end-link-api-ops-harden`)
- PR #162 pass: `docs/audit/passes/2026-09-23-pr162.json`
- Checklist: `docs/audit/checklists/kilo-receipt-chain-end-link-era-close-pr162.md`

## Verify bundle

```bash
python3 scripts/verify_kilo_receipt_chain_end_link_docs.py
python3 scripts/verify_kilo_receipt_chain_end_link_era_close.py
python3 scripts/verify_kilo_spine.py
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr160 tests.unit.test_kilo_live_proof_readiness_pr162 tests.unit.test_receipt_chain_end_link_docs tests.unit.test_receipt_chain_end_link_era_close -v
```

Do **not** claim KILO LIVE VERIFIED or run live Box/Mercury smokes from this guide.
