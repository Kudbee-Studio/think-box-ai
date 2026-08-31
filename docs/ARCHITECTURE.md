# Architecture — Think Box AI

## Overview

Think Box AI is a control plane for **Think Jobs** — units of work that turn intent into verified outcomes.

## Layers

```
┌─────────────────────────────────────────┐
│  CLI (thinkbox)                         │
│  job, findings, config, box, serve      │
├─────────────────────────────────────────┤
│  Backend API (FastAPI)                  │
│  /health, /jobs, /findings, /run, /ws   │
├─────────────────────────────────────────┤
│  Core Runtime                           │
│  Agent Loop, Planner, Actor, Observer   │
├─────────────────────────────────────────┤
│  Tools & Providers                      │
│  fs, http, memory, doginals, ollama     │
├─────────────────────────────────────────┤
│  Governance                             │
│  Audit Log, Approval Gate, Policy       │
├─────────────────────────────────────────┤
│  Memory                                 │
│  SQLite Store, Session/Task Adapters    │
└─────────────────────────────────────────┘
```

## Components

### CLI (`think_box_ai/cli.py`)
- Entry point with argparse subcommands
- Global flags: `--json`, `--plain`, `--quiet`, `--verbose`, `--dry-run`
- Commands: `job`, `findings`, `config`, `box`, `serve`, `watch`

### Backend (`backend/main.py`)
- FastAPI REST + WebSocket + SSE
- Job submission and execution
- Streaming responses

### Core Runtime (`core/runtime/loop.py`)
- Agent loop with XML tool-call parsing
- Max iteration limit
- Memory persistence

### Tools (`core/tools/`)
- `registry.py` — tool registration and execution
- `fs.py` — jailed filesystem access
- `http.py` — rate-limited HTTP GET
- `memory.py` — SQLite research memory
- `doginals.py` — Doginals domain tools

### Providers (`core/providers/`)
- `ollama.py` — local model inference
- `openai_compat.py` — OpenAI-compatible APIs

### Governance (`core/governance/audit.py`)
- Audit logging
- Permission checking
- Approval gates

### Memory (`core/memory/`)
- SQLite store
- Session/task adapters

## Data Flow

```
User → CLI → Backend API → Agent Loop → Tools → Memory
                         ↓
                   Findings (data/findings/)
                   Jobs (jobs/done/|blocked/)
```

## Job Lifecycle

```
queue → active → done
              → blocked (needs human/GPU)
```

## Security

- No secrets in git
- Path-jailed filesystem tools
- Rate-limited HTTP
- Audit logging for governance
