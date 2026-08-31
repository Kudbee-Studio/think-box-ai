# STATUS.md — Think Box AI Research Agent

## What Works ✅
- 17 tools registered and functional
- Agent loop with XML tool-call parsing
- SQLite research memory (memory_put/get/search)
- Filesystem tools (fs_read/write/list) — jailed to repo + data/
- HTTP tool with rate limiting
- Doginals domain tools (doge_tx, doginals_inscription, compare_inscription, parse_drc20, load_fixture)
- FastAPI backend (/health, /run, /stream, /ws)
- Bootstrap wires all components

## Verified Tool Count: 18

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

## Source Reachability (2026-08-31)

### Live (returned data)
- **api.doginals.org** — /v1/health OK; inscription endpoints 404 (not public)
- **api.github.com** — OK
- **example.com** — OK

### Blocked (TLS OK, app-layer block)
- **dogechain.info** — HTTP 403 (Cloudflare anti-bot challenge)

### Dead (network-level failure)
- **wonky-ordinals.fly.dev** — DNS resolution failure
- **ordinalswallet.com** — HTTP 522 (connection timeout)
- **api.inception.ai** — TLS alert 112 (CDN SNI reject from AWS IPs)

## Model Provider Status

| Provider | Box | Cloud Local | Notes |
|----------|-----|-------------|-------|
| Ollama | ❌ Not installed | ❌ Not installed | Install locally |
| Inception | ❌ TLS fail | ❌ TLS 525 | Don't use from cloud |
| OpenAI | ✅ Reachable | ✅ Reachable | Needs key |
| Groq | ✅ Reachable | ✅ Reachable | Needs key |

## How to Run Locally

```bash
git checkout session/agent_79e656bf-37c6-46f2-833e-1eb027b99152
pip install -r backend/requirements.txt

# Option A: Local Ollama
ollama pull llama3.1:8b
python3 -m uvicorn backend.main:app --port 8000 &

# Option B: Groq (free tier)
export THINKBOX_DEFAULT_PROVIDER=openai_compat
export THINKBOX_OPENAI_COMPAT_API_KEY=gsk_your_key
export THINKBOX_OPENAI_COMPAT_BASE_URL=https://api.groq.com/openai/v1
export THINKBOX_DEFAULT_MODEL=llama-3.1-8b-instant
python3 -m uvicorn backend.main:app --port 8000 &

# Run proof
python3 scripts/prove_dogi.py
```

## DOGI Proof Result

**Status:** Partial — tools work, but inscription data inaccessible via public APIs.

See: `data/findings/dogi_indexer_split.md`

## Key Finding

The indexer-split thesis is **not provable via public APIs alone**. Most inscription
indexers don't expose public endpoints, require auth, or are unreachable. To prove
the thesis, we need a paid API, residential proxy, or local indexer.
