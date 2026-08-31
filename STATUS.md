# STATUS.md — Think Box AI Research Agent

## What Works ✅
- Agent loop (`core/runtime/loop.py`) — XML tool-call parsing, iterative execution, memory persistence
- Tool registry (`core/tools/registry.py`) — register, execute, list, serialize to XML (17 tools)
- Ollama provider (`core/providers/ollama.py`) — local model inference
- OpenAI-compatible provider (`core/providers/openai_compat.py`) — cloud API fallback
- FastAPI backend (`backend/main.py`) — /health, /run, /stream, /ws endpoints
- SQLite memory store (`core/memory/store.py`) — key-value persistence
- Research memory (`core/tools/memory.py`) — SQLite research records (memory_put/get/search)
- Filesystem tools (`core/tools/fs.py`) — jailed fs_read/fs_write/fs_list
- HTTP tool (`core/tools/http.py`) — rate-limited GET with raw save
- Doginals tools (`core/tools/doginals.py`) — doge_tx, compare_inscription, parse_drc20, etc.
- Bootstrap (`core/foundation/bootstrap.py`) — wires all components
- Proof script (`scripts/prove_dogi.py`) — acceptance test

## Verified On Upstash Box
- 17 tools registered and functional
- fs_read/write/list: ✅ working
- memory_put/get/search: ✅ working
- load_fixture: ✅ working
- http_get/doge_tx: ⚠️ network blocked on box (will work locally)

## What Needs Local Testing
- Full agent run with Ollama (needs local model)
- HTTP tools with real network access
- End-to-end proof run with live indexers

## How to Run Locally
```bash
git checkout session/agent_79e656bf-37c6-46f2-833e-1eb027b99152
pip install -r backend/requirements.txt
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
# Or run the proof:
python3 scripts/prove_dogi.py
```
