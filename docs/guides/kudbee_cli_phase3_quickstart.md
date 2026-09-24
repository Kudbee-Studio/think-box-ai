# KUDBEECLI Phase 3 quickstart (PR #180)

Hermetic deepen layer for the `thinkbox` CLI after merged **#178 Phase 2**. Caps at **CODE COMPLETE / TEST VERIFIED** — not LIVE VERIFIED.

## Verify

```bash
python3 scripts/verify_kilo_pr180_kudbee_cli_phase3.py
python3 -m unittest tests.unit.test_cli_phase3_deepen tests.unit.test_kilo_live_proof_readiness_pr180 -v
python3 scripts/verify_kilo_spine.py
python3 scripts/scan_doc_secrets.py
```

## Example commands (no network)

```bash
thinkbox cli status --format json
thinkbox cli profile --list --format yaml
thinkbox cli cassette-replay health_flow --format json
thinkbox cli job create "hermetic-goal" --format json
thinkbox cli batch goal-a goal-b --parallel 2 --format json
thinkbox cli capabilities --format table
```

## Manifest

Feature list: `data/kudbee_cli/pr180_features.json`

## Profiles

Set `THINKBOX_CLI_PROFILE` to one of `THINKBOX_CLI_PROFILES` (default `default,inspect,ci`). Unknown profiles fail closed.
