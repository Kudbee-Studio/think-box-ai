# DOGI Indexer-Split Proof Report

**Date:** 2026-08-31
**Session:** agent_79e656bf-37c6-46f2-833e-1eb027b99152
**Method:** Tool execution via `prove_dogi.py` (18 tools registered)

## Source Health Check

| Source | Type | HTTP | Status |
|--------|------|------|--------|
| api.doginals.org | Doginals API | 200 | ✅ Live (health only) |
| dogechain.info | Dogecoin explorer | 403 | ❌ Cloudflare anti-bot |
| ordinalsdotcom | Ordinals API | 522 | ❌ Timeout |
| wonky | Ordinals indexer | — | ❌ DNS failure |
| unisat | Multi-chain indexer | 404 | ❌ Not found |

## Inscription IDs Tested

1. `15f3b73df7e5c072becb1d84191843ba080734805addfccb650929719080f62ei0`
2. `0bd32d69ca2221f3fc34d99aa14bccc2af10eedc7514770ae842ab9a72468743`
3. `ee688262677b00d973d0aa18e40863e8ba984e4237ac6ef46dd53a5b0d380092`

## Results Per Inscription

All three inscription IDs returned **no data** from any indexer:

### doginals_org (api.doginals.org)
- Health endpoint: **200 OK**
  ```json
  {"ok":true,"service":"doge-api","timestamp":1788181549,
   "dogecoin_rpc":{"ok":true,"chain":"main","blocks":6354899},
   "wonky":{"ok":true,"indexed_block_count":6354900}}
  ```
- Inscription endpoint: **404 Not Found** — route not exposed publicly
- All tested paths returned 404: `/v1/inscription/{id}`, `/v1/inscriptions`, `/v1/drc20`, `/v1/tokens`, `/inscription/{id}`, `wonky/inscription/{id}`

### dogechain.info
- Transaction endpoint: **403 Forbidden** — Cloudflare challenge
- TLS handshake succeeds; blocked at application layer

## What This Proves

1. **Public inscription data is NOT accessible.** Only health/status endpoints are exposed.
2. **TLS works for most hosts** — 403 is anti-bot, not network failure.
3. **No indexer comparison possible** — zero sources returned inscription data.
4. **Source availability varies by environment** — cloud IPs face more blocks than residential.

## What This Does NOT Prove

- ❌ The 21M vs 2.1B DOGI deploy split is **neither confirmed nor denied**.
- ❌ We cannot determine which indexer (if any) shows the "correct" supply.
- ❌ We cannot compare indexer consensus because no inscription data was returned.
- ❌ This does NOT disprove the indexer-split thesis.

## Honest Assessment

**The indexer-split thesis cannot be proven with publicly available APIs alone.**

The data required (inscription content per indexer) is behind:
- Cloudflare anti-bot protection (dogechain.info)
- Non-public API endpoints (doginals.org)
- Dead DNS entries (wonky-ord)
- Connection timeouts (ordinalswallet.com)
- CDN SNI rejects (api.inception.ai — not even tested here)

To actually prove the thesis, we need one of:
1. A paid indexer API with inscription access (Hiro, Unisat paid tier)
2. A residential IP proxy (bypass Cloudflare)
3. Running our own ordinals indexer (ord, ord-server)
4. Direct database access from an indexer operator

## Recommendations

1. Do NOT rely on single-source findings — always cross-reference.
2. Consider paid indexer APIs for production research.
3. Build automated consensus checks once working sources are found.
4. Test from residential IP before concluding sources are dead.

## Local Commands

```bash
git checkout session/agent_79e656bf-37c6-46f2-833e-1eb027b99152
pip install -r backend/requirements.txt
export THINKBOX_DEFAULT_PROVIDER=openai_compat
export THINKBOX_OPENAI_COMPAT_API_KEY=sk_your_key
export THINKBOX_OPENAI_COMPAT_BASE_URL=https://api.openai.com/v1
export THINKBOX_DEFAULT_MODEL=qwen/qwen3.6-27b
python3 -m uvicorn backend.main:app --port 8000 &
python3 scripts/prove_dogi.py
```

## SQLite Record

Finding persisted to `data/thinkbox.sqlite` with key `dogi_indexer_split`.
