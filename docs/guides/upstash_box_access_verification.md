# Upstash Box access verification (PR #201)

Hermetic / operator path for proving whether this runtime can reach the **existing** Upstash Box. No new infrastructure. No UpCloud.

## Adapter contract (source of truth)

| Name | Role |
|------|------|
| `UPSTASH_PUBLIC_BOX_URL` | Box preview URL (required) |
| `UPSTASH_PUBLIC_BOX_TOKEN` | Bearer token on `POST {url}/run` (required) |
| `UPSTASH_BOX_API_KEY` | Documented only — **not** read by `UpstashBoxExecutionAdapter` |

## Classifications

| Code | Name | Meaning |
|------|------|---------|
| A | ENV_NOT_CONFIGURED | Official URL and/or token absent or empty |
| B | ENDPOINT_REACHABLE_AUTH_FAILED | Host answered; auth rejected (401/403) |
| C | ENDPOINT_REACHABLE | Successful HTTP without verified remote execution |
| D | REMOTE_EXECUTION_VERIFIED | Adapter receipt `COMPLETED` and hash-verified on a live Box |
| E | BLOCKED | Reachability/preview/network/artifact failure after config is present |

HTTP reachability is not D. A mocked or loopback stub is not LIVE VERIFIED.

## Cursor Cloud Agent injection (PR #201 continuation)

The adapter reads **process environment variables only**. It does not read `.env` from the repo (gitignored) and must not read `UPSTASH_BOX_API_KEY`.

| Mechanism | Injects adapter vars? | Notes |
|-----------|----------------------|--------|
| **Cursor Environment secrets** | Yes (when configured) | Supported path. Secret **names** must match exactly: `UPSTASH_PUBLIC_BOX_URL`, `UPSTASH_PUBLIC_BOX_TOKEN`. Values are set in the Cursor dashboard for the agent environment, not in git. |
| `.cursor/environment.json` | No | Defines `install` / `terminals` only (see public schema). Does **not** declare secret values or secret names. |
| Personal / team saved environment | Partial in this run | Can inject other Upstash keys (Vector, Redis, `UPSTASH_BOX_API_KEY`) while omitting the adapter pair — yields classification **A**. |

**Why classification A occurred:** this agent booted from a **Personal** environment (`environmentJsonPath` null). Partial Upstash secrets were injected, but the two **official** adapter variables were not present in the process.

**After secrets are added:** start a **new** Cloud Agent (same repo/branch). Confirm presence-only, then:

```bash
python3 scripts/upstash_box_access_probe.py \
  --allow-network --allow-execute --live \
  --out data/upstash_box_access/probe_live.json
```

Do not substitute `UPSTASH_BOX_API_KEY` for `UPSTASH_PUBLIC_BOX_TOKEN`.

## Commands

```bash
# Fail-closed presence + adapter probe (safe in CI; no live claim)
python3 scripts/upstash_box_access_probe.py --out data/upstash_box_access/probe_latest.json

# Operator-only: allow one unauthenticated GET and one POST /run when configured
python3 scripts/upstash_box_access_probe.py --allow-network --allow-execute --live

python3 scripts/verify_kilo_pr201_upstash_box_access.py
python3 -m unittest tests.unit.test_upstash_box_access tests.unit.test_kilo_live_proof_readiness_pr201 -v
```

Never print, commit, or log token values.
