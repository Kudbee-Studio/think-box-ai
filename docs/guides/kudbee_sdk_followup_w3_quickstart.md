# Kudbee SDK follow-up wave 3 quickstart (PR #191)

Hermetic toolkit under `thinkbox/kudbee_sdk_followup_w3/` deepening merged #177, #179, and #181 (wave 2).
**Four-state cap:** CODE COMPLETE / TEST VERIFIED only — not LIVE VERIFIED.

## Verify gate

```bash
python3 scripts/verify_kilo_pr191_kudbee_sdk_followup_w3.py
```

## Run example

```bash
python3 examples/kudbee_sdk_followup_w3_quickstart.py
```

## Environment (optional)

| Variable | Purpose |
|----------|---------|
| `KUDBEE_SDK_FOLLOWUP_W3_BASE_URL` | HTTP base (must be `http://` or `https://`) |
| `KUDBEE_SDK_FOLLOWUP_W3_DRY_RUN` | Force dry-run transport (`true`/`1`) |
| `KUDBEE_SDK_FOLLOWUP_W3_TIMEOUT_S` | Request timeout seconds |

## TypeScript

See `apps/web/sdk/followup_w3.ts` and exports from `apps/web/sdk/index.ts`.
