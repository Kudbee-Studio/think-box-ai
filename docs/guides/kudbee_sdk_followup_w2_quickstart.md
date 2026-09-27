# Kudbee SDK follow-up wave 2 quickstart (PR #181)

Hermetic toolkit under `thinkbox/kudbee_sdk_followup_w2/` deepening merged #177 and #179.
**Four-state cap:** CODE COMPLETE / TEST VERIFIED only — not LIVE VERIFIED.

## Verify gate

```bash
python3 scripts/verify_kilo_pr181_kudbee_sdk_followup_w2.py
```

## Run example

```bash
python3 examples/kudbee_sdk_followup_w2_quickstart.py
```

## Environment (optional)

| Variable | Purpose |
|----------|---------|
| `KUDBEE_SDK_FOLLOWUP_W2_BASE_URL` | HTTP base (must be `http://` or `https://`) |
| `KUDBEE_SDK_FOLLOWUP_W2_DRY_RUN` | Force dry-run transport (`true`/`1`) |
| `KUDBEE_SDK_FOLLOWUP_W2_TIMEOUT_S` | Request timeout seconds |

## TypeScript

See `apps/web/sdk/followup_w2.ts` and exports from `apps/web/sdk/index.ts`.
