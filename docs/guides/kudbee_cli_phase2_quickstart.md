# KUDBEECLI Phase 2 quickstart (PR #178)

Hermetic deepen layer for the `thinkbox` CLI. Caps at **CODE COMPLETE / TEST VERIFIED** — not LIVE VERIFIED.

## Verify

```bash
python3 scripts/verify_kilo_pr178_kudbee_cli_phase2.py
python3 -m unittest tests.unit.test_cli_phase2_deepen tests.unit.test_kilo_live_proof_readiness_pr178 -v
python3 scripts/scan_doc_secrets.py
```

## Example commands (no network)

```bash
thinkbox cli health --json
thinkbox cli dry-run --goal "inspect-only" --json
thinkbox cli receipt-bind rcpt_demo '{"event":"cli"}' --json
```

## Manifest

Feature list: `data/kudbee_cli/pr178_features.json`
