# STATUS.md — Think Box AI Research Agent

## What Works
- Agent loop (`core/runtime/loop.py`) — XML tool-call parsing, iterative execution
- Tool registry (`core/tools/registry.py`) — register, execute, list, serialize to XML
- Ollama provider (`core/providers/ollama.py`) — local model inference
- OpenAI-compatible provider (`core/providers/openai_compat.py`) — cloud API fallback
- FastAPI backend (`backend/main.py`) — /health, /run, /stream, /ws endpoints
- SQLite memory store (`core/memory/store.py`) — key-value persistence
- Bootstrap (`core/foundation/bootstrap.py`) — wires all components together

## What Is Stubbed
- Memory tools (memory_put/get/search) — store exists, tools not built
- Filesystem tools — basic read/write exist, not jailed or agent-facing
- HTTP tool — not implemented
- Doginals tools — not implemented
- Agent loop memory integration — loop doesn't persist to SQLite yet

## What Is Missing
- `data/` directory for research artifacts
- `core/tools/fs.py` — jailed filesystem tools
- `core/tools/http.py` — HTTP GET with rate limiting
- `core/tools/memory.py` — SQLite-backed research memory
- `core/tools/doginals.py` — Doginals/DRC-20 domain tools
- `scripts/prove_dogi.py` — acceptance test
- `RESEARCH.md` — how to rerun the proof
- Frontend trace view

## How to Run
```bash
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
curl http://localhost:8000/health
```
