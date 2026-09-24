# Receipt-chain deepen quickstart (PR #182)

Hermetic toolkit under `thinkbox/receipt_chain_deepen/` deepening receipt-chain,
END_LINK, and audit-ledger surfaces from merged PRs #155–#164. **Four-state cap:**
CODE COMPLETE / TEST VERIFIED only — not LIVE VERIFIED.

## Verify gate

```bash
python3 scripts/verify_kilo_pr182_receipt_chain_deepen.py
python3 -m unittest tests.unit.test_receipt_chain_deepen tests.unit.test_kilo_live_proof_readiness_pr182 -v
```

## Example

```bash
python3 examples/receipt_chain_deepen_quickstart.py
```

## Environment

- `RECEIPT_CHAIN_DEEPEN_DRY_RUN=true` (required; fail-closed otherwise)
- `RECEIPT_CHAIN_DEEPEN_REDACT=true` (default)
- `RECEIPT_CHAIN_DEEPEN_MAX_ENTRIES=256` (bounded in-memory chain)

No Box URL, Mercury, or governance tokens are required for this gate.
