# KUDBEECLI enterprise upgrade (PR #196)

After merged **#195** enterprise SDK lanes.

```bash
python3 scripts/verify_kilo_pr196_kudbee_cli_enterprise_upgrade.py
python3 -m thinkbox.cli cli enterprise status --format json
python3 -m thinkbox.cli cli enterprise hub --format json
python3 -m thinkbox.cli cli enterprise lanes --format json
```

Hermetic only — `live_api_called: false`.
