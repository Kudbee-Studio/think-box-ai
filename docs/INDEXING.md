# Indexing Architecture — Think Box AI

**Component:** `core/indexing/`
**Date:** 2026-08-31

## Overview

Local-first indexing system for sessions and project memory.
Built on SQLite + FTS5 (Full-Text Search 5). No external dependencies.

## Architecture

```
┌─────────────────────────────────────────┐
│  CLI (thinkbox memory ...)             │
├─────────────────────────────────────────┤
│  Search Engine (core/indexing/search.py)│
│  - FTS5 full-text search (BM25)         │
│  - Session search                       │
│  - Memory search                        │
│  - Context expansion                    │
├─────────────────────────────────────────┤
│  Project Memory (core/indexing/memory.py)│
│  - Durable facts                        │
│  - Environment notes                    │
│  - Corrections                          │
│  - Session store                        │
├─────────────────────────────────────────┤
│  Database (core/indexing/database.py)   │
│  - SQLite WAL mode                      │
│  - FTS5 virtual tables                  │
│  - Triggers for auto-sync               │
│  - Project-scoped isolation             │
└─────────────────────────────────────────┘
```

## Schema

### sessions
- `id` TEXT PRIMARY KEY
- `title` TEXT
- `project_hash` TEXT (SHA-256 of repo path, first 16 chars)
- `created_at`, `updated_at` TEXT
- `metadata` TEXT (JSON)

### messages
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `session_id` TEXT REFERENCES sessions(id)
- `role` TEXT (user | assistant | tool)
- `content` TEXT
- `tool_name`, `tool_args` TEXT
- `created_at` TEXT

### messages_fts (FTS5 virtual table)
- Indexes `content` from messages
- Auto-synced via INSERT/UPDATE/DELETE triggers
- BM25 ranking

### project_memory
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `project_hash` TEXT
- `key`, `value` TEXT
- `source` TEXT (auto | explicit | correction)
- `created_at`, `updated_at` TEXT

### memory_fts (FTS5 virtual table)
- Indexes key + value from project_memory
- Auto-synced via triggers

## Search

```python
from core.indexing.search import SearchEngine

engine = SearchEngine()

# Search messages
results = engine.search_messages("deploy", project=".", limit=10)

# Search memory
results = engine.search_memory("language", project=".")

# Read session
messages = engine.read_session("session-id")

# Get project context (for startup injection)
context = engine.get_project_context(".")
```

## Memory

```python
from core.indexing.memory import ProjectMemory, SessionStore

# Project memory
pm = ProjectMemory(".")
pm.remember("deploy_cmd", "docker build .")
pm.save_correction("language", "Use Python")
pm.save_environment("port", "8080")
pm.forget("old_key")

# Session store
store = SessionStore(".")
store.create_session("ses_001", "My Session")
store.add_message("ses_001", "user", "Hello")
store.add_message("ses_001", "assistant", "Hi!")
```

## CLI

```bash
thinkbox memory search <query>
thinkbox memory show <session_id>
thinkbox memory list
thinkbox memory remember <key> <value>
thinkbox memory forget <key>
thinkbox memory context
```

## Project Isolation

Each project gets isolated storage via `project_hash` (SHA-256 of resolved path).
Sessions and memory from different projects never mix.

## Performance

| Metric | Value |
|--------|-------|
| Search time | < 20ms per query |
| Write time | ~0.1ms per message |
| Storage | ~1MB per 10K messages |
| Concurrency | WAL mode (readers never block writers) |

## Future Enhancements

1. **Vector search** — Add LanceDB for semantic similarity
2. **Hybrid search** — FTS5 + vector with Reciprocal Rank Fusion
3. **Auto-capture** — Auto-save session digests on close
4. **Code chunking** — Tree-sitter for AST-aware indexing
5. **Cross-agent sync** — CRDT-based sync between agents
