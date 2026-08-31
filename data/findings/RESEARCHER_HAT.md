# Researcher Hat — Think Box AI

**Scope:** Inscription chain indexer consensus research.
**Out of scope:** Token, movie swarm, Polar browser, FreeToken install.

## Intent

Prove or disprove that different indexers disagree on inscription data (e.g., DOGI 20M vs 2.1B supply).

## Inputs

| Input | Format | Example |
|-------|--------|---------|
| Transaction ID | 64-char hex | `0bd32d69ca2221f3fc34d99aa14bccc2af10eedc7514770ae842ab9a72468743` |
| Inscription ID | txid + `i0` | `15f3b73df7e5c072becb1d84191843ba080734805addfccb650929719080f62ei0` |
| Wallet Address | Dogecoin address | `D8vF...` |

## Tools Allowed

| Tool | Purpose |
|------|---------|
| doge_tx | Fetch Dogecoin transaction |
| doginals_inscription | Fetch inscription from indexer |
| compare_inscription | Compare across indexers |
| parse_drc20 | Parse DRC-20 JSON |
| indexer_health | Check source availability |
| http_get | Generic HTTP GET |
| fs_read/write/list | Filesystem (jailed) |
| memory_put/get/search | SQLite persistence |
| load_fixture | Load test data |

## Proof Schema

```
1. INTENT    — what claim is being tested
2. CAPABILITY — which tools/sources can observe it
3. ARTIFACTS  — raw data pulled (saved to data/raw/)
4. EVALUATION — what the data proves or disproves
5. GAPS       — what remains unproven and why
```

## Source Allowlist

| Source | Status |
|--------|--------|
| api.doginals.org | ✅ Live (health only) |
| api.github.com | ✅ Live |

## Source Blocklist

| Source | Reason |
|--------|--------|
| api.inception.ai | TLS SNI reject |
| wonky-ord.dogeord.io | DNS dead |
| ordinalswallet.com | Timeout |
| dogechain.info | Cloudflare 403 |

## Output

- `data/findings/<claim>.md` — human-readable report
- `data/raw/<host>/<hash>.json` — raw API responses
- SQLite record — structured finding

## Honest Reporting Rules

1. Record exact HTTP status codes (200/403/404/DNS).
2. Do NOT claim "proven" if sources cannot see the data.
3. Distinguishes "unproven" from "disproven".
4. Lists what would be needed to actually prove the claim.
