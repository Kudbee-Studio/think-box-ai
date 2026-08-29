# Think Box AI

**Think Box AI** is an agent execution environment with local-first token tracking, multi-provider routing, and a CLI for operator control.

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [CLI Commands](#cli-commands)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [Contributing](#contributing)

---

## Overview

Think Box AI provides:

- **Think Boxes** — bounded execution contexts with identity, policy, and evidence
- **Think Tokens** — Elo-scored claims backed by execution evidence
- **Provider Router** — multi-provider routing with failover and snapshot dedup
- **CLI** — operator commands for create, exec, evidence, tokens, challenges

---

## Quick Start

### Prerequisites

- Python ≥ 3.10

### Run the CLI

```bash
# Create a Think Box
thinkbox create
# → tb-a1b2c3d4e5f6

# Execute a command
thinkbox exec tb-a1b2c3d4e5f6 -- echo KUDBEE_LOCAL_OK

# View evidence
thinkbox evidence tb-a1b2c3d4e5f6

# List tokens
thinkbox tokens tb-a1b2c3d4e5f6

# Token score
thinkbox token-score tt-1234567890ab

# Human challenge
thinkbox challenge-human tt-1234567890ab pass

# Jury challenge (requires LLM endpoint)
thinkbox challenge-jury tt-1234567890ab --base-url http://localhost:8000/v1
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `thinkbox create` | Generate a new Think Box ID |
| `thinkbox exec <id> -- <argv>` | Execute a command, prints output |
| `thinkbox evidence <id>` | Show execution evidence rows |
| `thinkbox tokens <id>` | List tokens for a box |
| `thinkbox token-score <tid>` | Print token Elo score + last challenge |
| `thinkbox challenge-jury <tid>` | Run LLM jury challenge |
| `thinkbox challenge-human <tid> <verdict>` | Manual scoring (pass/fail/neutral) |
| `thinkbox challenge-replay <tid>` | Replay the most recent challenge |
| `thinkbox list` | List all boxes with tokens |
| `thinkbox status <id>` | Detailed box status |
| `thinkbox export <id> [-o FILE]` | Export box to JSON |
| `thinkbox import <file>` | Import box from JSON |
| `thinkbox delete <id>` | Delete a box and all its data |
| `thinkbox leaderboard [--limit N]` | Top-scoring tokens |
| `thinkbox clear-cache` | Clear provider snapshot cache |
| `thinkbox --version` | Print version |

---

## Project Structure

```
think-box-ai/
├── think_box_ai/              # Main Python package
│   ├── __init__.py            # Package init
│   ├── __main__.py            # Entry point
│   ├── cli.py                 # CLI commands
│   └── token.py               # Token constants
├── core/                      # Core modules
│   ├── foundation/            # Config, logging, errors, bootstrap
│   ├── memory/                # SQLite store, tokens, challenges
│   │   ├── store.py           # MemoryStore + ThinkStore
│   │   ├── schema.py          # Memory entry types
│   │   ├── session.py         # Session adapter
│   │   ├── task.py            # Task adapter
│   │   └── org.py             # Org adapter
│   ├── governance/            # Audit log, permissions
│   │   └── audit.py           # AuditLog
│   ├── providers/             # Model provider abstraction
│   │   ├── base.py            # ModelProvider protocol
│   │   ├── openai_compat.py   # OpenAI-compatible provider
│   │   ├── router.py          # Multi-provider router + failover
│   │   └── snapshot.py        # Snapshot hashing for dedup
│   ├── runtime/               # Agent runtime
│   │   ├── actor.py           # Actor (execution routing)
│   │   ├── agent.py           # Agent
│   │   ├── observer.py        # Observer
│   │   ├── planner.py         # Planner + Step
│   │   └── thinkbox.py        # ThinkBox
│   └── tools/                 # Built-in tools
│       ├── filesystem.py      # File read/write
│       ├── shell_exec.py      # Shell execution
│       ├── http_request.py    # HTTP requests
│       ├── memory_query.py    # Memory queries
│       └── registry.py        # Tool registry
├── tests/                     # Tests
│   ├── unit/                  # Unit tests
│   └── integration/           # Integration tests
├── docs/                      # Documentation
│   ├── architecture-v1.md     # Architecture document
│   ├── project-foundation.md  # Project foundation
│   └── roadmap.md             # Roadmap
└── AGENTS.md                  # Agent rules
```

---

## Architecture

### Token Model

- **Mint**: Only when `thinkbox exec` evidence row has `ok=true`
- **Claim**: argv joined, capped at 200 chars
- **Initial score**: s=1.0, grounded=1

### Challenge Types

| Type   | Weight | Outcome |
|--------|--------|---------|
| exec   | 3      | ok=true → o=+1, ok=false → o=-1 |
| jury   | 2      | LLM YES/NO/garbage → o=+1/-1/0 |
| human  | 2      | pass/fail/neutral → o=+1/-1/0 |
| replay | 1      | Replays last challenge outcome |

### Elo Formula

```
s += η * w * (o - σ(s - s_challenger))
```

- η = 0.25
- s_challenger = 1.0
- Floor: 0, Cap: 100
- σ = sigmoid

### Evidence Storage

- `~/.local/share/thinkbox/evidence/<box_id>.jsonl` — append-only evidence log
- `~/.local/share/thinkbox/thinkbox.db` — SQLite (tokens + challenges tables)

### Provider Router

The `openai_compat` provider supports multi-provider routing:

```json
{
  "providers": [
    {"name": "openai_compat", "model": "gpt-4o-mini"},
    {"name": "openai_compat", "model": "local", "base_url": "http://localhost:8000/v1"}
  ],
  "order": ["openai_compat"],
  "snapshot_cache": true,
  "persistent_cache_path": "~/.local/share/thinkbox/snapshot_cache.db"
}
```

---

## Contributing

All external contributors must follow the rules in [AGENTS.md](AGENTS.md).
