# STATUS.md — Think Box AI Research Agent

**Session:** agent_79e656bf-37c6-46f2-833e-1eb027b99152
**Branch:** session/agent_79e656bf-37c6-46f2-833e-1eb027b99152

## What Works

### Tools (18 registered)
| # | Tool | Status |
|---|------|--------|
| 1 | file_read | ✅ |
| 2 | file_write | ✅ |
| 3 | shell_exec | ✅ |
| 4 | http_request | ✅ |
| 5 | memory_query | ✅ |
| 6 | fs_read | ✅ |
| 7 | fs_write | ✅ |
| 8 | fs_list | ✅ |
| 9 | http_get | ✅ |
| 10 | memory_put | ✅ |
| 11 | memory_get | ✅ |
| 12 | memory_search | ✅ |
| 13 | indexer_health | ✅ |
| 14 | doge_tx | ✅ |
| 15 | doginals_inscription | ✅ |
| 16 | compare_inscription | ✅ |
| 17 | parse_drc20 | ✅ |
| 18 | load_fixture | ✅ |

### Backend
- /health returns OK with provider + tool count
- /run endpoint works
- /stream and /ws implemented

### What Passed Today
- ✅ 18 tools register and respond
- ✅ Bootstrap completes
- ✅ indexer_health tool correctly identifies live/dead sources
- ✅ memory_put/get/search persist to SQLite
- ✅ Findings written to data/findings/dogi_indexer_split.md
- ✅ Fixtures load correctly

### What Failed / Blocked
- ❌ dogechain.info returns 403 (Cloudflare anti-bot) — not TLS, not fixable from box
- ❌ doginals.org inscription endpoints return 404 (not public, only /health works)
- ❌ api.inception.ai TLS SNI rejected by CDN — never use from box
- ❌ wonky-ord.dogeord.io DNS resolution failure
- ❌ ordinalswallet.com connection timeout (522)
- ❌ No Ollama on box (not installed)

## Source Reachability (2026-08-31)

### Live (returned data)
| Source | HTTP | Notes |
|--------|------|-------|
| api.doginals.org | 200 | Only /v1/health; inscription routes 404 |
| api.github.com | 200 | OK |

### Blocked (TLS OK, app-layer block)
| Source | HTTP | Notes |
|--------|------|-------|
| dogechain.info | 403 | Cloudflare anti-bot challenge |

### Dead (network-level failure)
| Source | Error |
|--------|-------|
| wonky-ord.dogeord.io | DNS resolution failure |
| ordinalswallet.com | Connection timeout (522) |
| api.inception.ai | TLS alert 112 (CDN SNI reject) |

## Model Provider Order

1. **Ollama** (preferred) — local, install with `ollama pull llama3.1:8b`
2. **FreeToken** — GPU server at `http://87.58.150.62:1919/v1` when started by Kudbee
3. **OpenAI-compatible** — any standard provider with valid key

## DOGI Proof Result

**Status:** Partial — tools work, inscription data inaccessible.

The 21M vs 2.1B DOGI deploy split remains **unverified** because:
- dogechain.info is Cloudflare-blocked (403)
- doginals.org doesn't expose inscription data publicly (404)
- Other indexers are dead (DNS/timeout)

See: `data/findings/dogi_indexer_split.md`

## Key Limitation

The indexer-split thesis **cannot be proven with public APIs alone**.
Requires: paid indexer API, residential proxy, or local ord indexer.

## How to Run Locally

```bash
git checkout session/agent_79e656bf-37c6-46f2-833e-1eb027b99152
pip install -r backend/requirements.txt

# Ollama provider
ollama pull llama3.1:8b
python3 -m uvicorn backend.main:app --port 8000 &

# Run proof
python3 scripts/prove_dogi.py
```
