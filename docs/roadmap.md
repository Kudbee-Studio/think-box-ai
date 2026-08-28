# KUdBEE — Implementation Roadmap

**Project:** kudbEE — Local-first, streaming, Devin-like agent OS
**Architecture:** Python backend (FastAPI + WebSocket + SSE) + React/Vite frontend + Ollama/OpenAI models
**Brand:** kudbEE — bee/honeycomb/hive metaphor, warm amber on dark, fast local dev UX

---

## STAGE 0 — Foundation Lock (Week 1) ✅ COMPLETE

**Goal:** Stable Python package, event schema, agent loop contract, plugin interface.

**Status:** Complete as of commit e677fb7. All core modules implemented and tests passing.

### 0.1 Core Python package
- [x] `core/foundation/` — config, logging, errors, bootstrap
- [x] `core/memory/` — SQLite store, session/task/org adapters, schemas
- [x] `core/governance/` — audit log, permissions, approval gate
- [x] `core/providers/` — ModelProvider protocol, OpenAI-compatible provider
- [x] `core/tools/` — registry, decorator, 5 built-in tools (file_read, file_write, shell_exec, http_request, memory_query)
- [x] `core/runtime/` — Agent, Goal, Step, ThinkBox, Planner, Actor, Observer
- [x] `tests/unit/` — tests passing
- [x] `tests/integration/` — tests passing
- [x] `tests/e2e/` — pending (deferred to Phase 2)
- [x] `core/foundation/secrets.py` — SecretResolver for secrets/capabilities abstraction

### 0.2 Event schema (FINAL — do not change after this)
```python
EVENT_TYPES = [
    "THOUGHT",      # Agent reasoning text
    "TOKEN",        # Streamed model token
    "TOOL_CALL",    # Plugin invocation
    "TOOL_RESULT",  # Plugin result
    "FILE_UPDATE",  # File change
    "TASK_UPDATE",  # Subtask progress
    "MEMORY_UPDATE",# Memory store/load
    "RISKY_ACTION", # Needs approval
    "STATUS",       # Agent status change
]
```

### 0.3 Plugin interface (FINAL)
```python
class Tool:
    name: str
    description: str
    schema: dict          # JSON schema for args
    permission: str       # read_only | read_write | network | exec | restricted
    requires_approval: bool

    async def run(self, args: dict, context: dict) -> dict:
        ...
```

### 0.4 Agent loop contract (FINAL)
```
Input:  goal (str), model (str), tools (dict), context (dict)
Output: events (async stream)
Behavior:
  1. Build context from memory
  2. Stream model tokens → TOKEN events
  3. Parse action from tokens
  4. If TOOL_CALL → execute → TOOL_RESULT
  5. Store in memory → MEMORY_UPDATE
  6. If finish → TASK_UPDATE (done) + exit
  7. Never block, always stream
```

### 0.5 Brand seed
- Name: **kudbEE** (pronounced "koo-dee-bee")
- Concept: Worker-bee agent OS, hive mind, honeycomb grid
- Colors: Dark charcoal base (#0a0a0f), warm amber accent (#f59e0b), soft white text
- UI: Bento grid of "thinking windows"

**Deliverable:** `docs/roadmap.md` + frozen `EVENT_TYPES` + `Tool` interface + agent loop contract

---

## STAGE 1 — Web Backend (Week 2)

**Goal:** FastAPI backend with WebSocket + SSE, event bus, Ollama streaming, plugin pack.

### 1.1 Backend structure
```
apps/web/
├── package.json
├── public/
│   ├── index.html
│   ├── css/main.css
│   └── js/app.js
└── runtime_bridge.py      # Python bridge
```

### 1.2 FastAPI backend (NEW — replace Node.js with Python)
```
backend/
├── main.py                # FastAPI app, CORS, routes
├── event_bus.py           # WebSocket broadcast
├── agent_loop.py          # Core agent loop
├── task_manager.py        # Task state machine
├── memory.py              # Short/long-term memory
├── model_registry.py      # Ollama + OpenAI clients
├── plugins/
│   ├── base.py            # Tool base class
│   ├── filesystem.py      # Read/write/list files
│   ├── terminal.py        # Shell command execution
│   ├── git.py             # Git operations
│   └── http.py            # HTTP fetch
└── requirements.txt
```

### 1.3 Event bus
- [ ] WebSocket endpoint `/ws`
- [ ] SSE endpoint `/stream` for token streaming
- [ ] Broadcast to all connected clients
- [ ] Dead client cleanup

### 1.4 Ollama integration
- [ ] `GET /models` — list local Ollama models
- [ ] `POST /run` — start agent loop with goal + model
- [ ] Stream tokens via SSE
- [ ] Stream events via WebSocket
- [ ] Auto-detect Ollama at `localhost:11434`

### 1.5 Plugin pack
- [ ] `filesystem` — read, write, list, diff
- [ ] `terminal` — shell exec with timeout + cwd
- [ ] `git` — status, diff, log, checkout
- [ ] `http` — GET/POST with headers
- [ ] `web_search` — DuckDuckGo HTML scrape
- [ ] `code_analyzer` — AST-lite analysis

### 1.6 REST API
```
GET  /health              # Health check
GET  /models              # List Ollama models
POST /tasks               # Create task
POST /tasks/{id}/stop     # Stop task
POST /tasks/{id}/approve  # Approve risky action
GET  /plugins             # List plugins
```

**Deliverable:** Running FastAPI backend on port 8000, WebSocket + SSE working, Ollama streaming, 6 plugins

---

## STAGE 2 — Frontend Shell (Week 3)

**Goal:** kudbEE branded UI, bento grid layout, WebSocket connection, model selector.

### 2.1 Tech stack
- React 18 + Vite
- Tailwind CSS (or plain CSS variables)
- WebSocket hook
- SSE hook (for token streaming)

### 2.2 Layout (Bento Grid)
```
┌─────────────────────────────────────────────┐
│  🐝 kudbEE          [Model: deepseek-coder] [Status: Idle] │
├──────────────┬──────────────────┬───────────┤
│ 📁 Files     │ 💬 Terminal      │ 📋 Tasks  │
│              │                  │           │
│              │                  │           │
├──────────────┼──────────────────┼───────────┤
│ 🔌 Plugins   │ 🧠 Memory        │ 💭 Thoughts│
│              │                  │           │
└──────────────┴──────────────────┴───────────┘
```

### 2.3 Components
- [ ] `BentoGrid` — CSS grid layout
- [ ] `WindowFrame` — reusable panel chrome
- [ ] `ChatPanel` — goal input + streamed output
- [ ] `TerminalPanel` — THOUGHT + TOOL_CALL + TOOL_RESULT stream
- [ ] `TaskPanel` — TASK_UPDATE events
- [ ] `FileExplorer` — FILE_UPDATE events + file tree
- [ ] `MemoryPanel` — MEMORY_UPDATE events
- [ ] `ModelSelector` — dropdown with Ollama models
- [ ] `StatusBar` — global status indicator

### 2.4 Brand integration
- [ ] kudbEE logo (hexagon + bee wings)
- [ ] Honeycomb grid lines (subtle CSS)
- [ ] Amber glow on active panels
- [ ] Bee status indicator (idle/running/error)

**Deliverable:** Running kudbEE UI on port 5173, connected to backend, shows events in real-time

---

## STAGE 3 — Agent Loop Wiring (Week 4)

**Goal:** Full agent loop with streaming, tool execution, task decomposition, memory.

### 3.1 Agent loop
- [ ] Build context from memory
- [ ] Stream model response via SSE
- [ ] Parse TOOL_CALL from model output
- [ ] Execute tool via plugin registry
- [ ] Emit events in order: THOUGHT → TOKEN → TOOL_CALL → TOOL_RESULT → MEMORY_UPDATE
- [ ] Handle finish condition
- [ ] Error recovery + retry

### 3.2 Task decomposition
- [ ] Break goal into subtasks
- [ ] Emit TASK_UPDATE for each subtask
- [ ] Execute subtasks sequentially
- [ ] Track progress

### 3.3 Memory system
- [ ] Short-term: per-task context (last N events)
- [ ] Long-term: SQLite key-value store
- [ ] MEMORY_UPDATE events on store/load
- [ ] Context window management (summarize old events)

### 3.4 File change tracking
- [ ] Track files read/written
- [ ] Emit FILE_UPDATE with diff summary
- [ ] Show in FileExplorer panel

**Deliverable:** End-to-end agent execution with streaming, tools, memory, file tracking

---

## STAGE 4 — Approval Flow + Safety (Week 5)

**Goal:** Human-in-the-loop for risky actions, audit logging, policy engine.

### 4.1 Approval flow
- [ ] RISKY_ACTION event emitted before dangerous tool calls
- [ ] Frontend shows approval modal
- [ ] Approve/reject/actions sent to backend
- [ ] Agent pauses until decision
- [ ] Timeout fallback

### 4.2 Audit logging
- [ ] Append-only event log in SQLite
- [ ] Hash chain for tamper evidence
- [ ] Retention policy (90 days)
- [ ] Export to JSON

### 4.3 Policy engine
- [ ] Per-plugin approval requirements
- [ ] Allowed/forbidden directories
- [ ] Max file size limits
- [ ] Max API calls per task

**Deliverable:** Safe, auditable agent execution with approval gates

---

## STAGE 5 — Speed + Polish (Week 6)

**Goal:** Fast local testing, hot reload, caching, responsive UI.

### 5.1 Performance
- [ ] Async everywhere (FastAPI + asyncio tools)
- [ ] Streaming-first (never wait for full response)
- [ ] Local caching (model responses, tool results, file metadata)
- [ ] Connection pooling for Ollama

### 5.2 Dev experience
- [ ] Hot reload backend (`uvicorn --reload`)
- [ ] Hot reload frontend (Vite HMR)
- [ ] Plugin hot reload (watch plugins/ folder)
- [ ] Debug mode with verbose event logging

### 5.3 UI polish
- [ ] Smooth animations (panel transitions, streaming text)
- [ ] Dark/light theme toggle
- [ ] Resizable panels (drag handles)
- [ ] Keyboard shortcuts (Ctrl+Enter to run, Esc to stop)
- [ ] Mobile responsive (stack panels)

**Deliverable:** Fast, polished local dev experience

---

## STAGE 6 — Intelligence (Week 7-8)

**Goal:** Agent learns from experience, adaptive routing, reasoning windows.

### 6.1 Memory enhancement
- [ ] Vector embeddings for long-term memory (sentence-transformers)
- [ ] Similarity search for relevant past experiences
- [ ] Memory pruning (forget low-value events)

### 6.2 Reasoning windows
- [ ] Show chain-of-thought in Terminal panel
- [ ] Highlight tool selection reasoning
- [ ] Show error analysis + recovery
- [ ] Show next-step planning

### 6.3 Adaptive model routing
- [ ] Route simple tasks to fast/cheap model
- [ ] Route complex tasks to reasoning model
- [ ] User can override per-task

**Deliverable:** Smarter agent that learns and shows its work

---

## STAGE 7 — Enterprise (Week 9-10)

**Goal:** Multi-user, compliance, audit, deployment-ready.

### 7.1 Multi-user
- [ ] User authentication (JWT)
- [ ] Per-user sessions and tasks
- [ ] Shared organizational memory

### 7.2 Compliance
- [ ] Secret detection (no API keys in code)
- [ ] License scanning
- [ ] Risky action scoring
- [ ] Immutable audit trail

### 7.3 Deployment
- [ ] Docker container
- [ ] docker-compose.yml (backend + frontend + Ollama)
- [ ] Environment config
- [ ] Health checks

**Deliverable:** Production-ready agent OS

---

## STAGE 8 — Billion-Dollar Extensions (Post-MVP)

**Goal:** Marketplace, telemetry, multi-agent, monetization.

### 8.1 Plugin marketplace
- [ ] Plugin registry API
- [ ] Developer docs
- [ ] Rating/review system
- [ ] Revenue share

### 8.2 Agent telemetry
- [ ] Record sessions (events, decisions, failures)
- [ ] Replay agent sessions
- [ ] Auto-tune prompts from data

### 8.3 Multi-agent orchestration
- [ ] Spawn multiple agents
- [ ] Assign specialized roles (planner, coder, tester)
- [ ] Hive dashboard

### 8.4 Repo-native HUD
- [ ] `/agent` folder in any repo
- [ ] Auto-detect stack
- [ ] Load specialized tools

---

## IMMEDIATE NEXT STEPS (Start Here)

### Priority 1: Backend FastAPI (Stage 1)
1. Create `backend/` directory
2. Set up FastAPI + WebSocket + SSE
3. Port existing Node.js server logic to Python
4. Wire Ollama streaming
5. Test with existing frontend

### Priority 2: Frontend Connection (Stage 2)
1. Keep existing vanilla JS frontend (works, no build step)
2. Connect to FastAPI WebSocket
3. Add SSE token streaming
4. Test end-to-end

### Priority 3: Agent Loop (Stage 3)
1. Port Python agent runtime to FastAPI
2. Wire event bus to WebSocket
3. Test with Ollama model
4. Verify streaming works

---

## SUCCESS CRITERIA

**Stage 0:** All tests pass, event schema frozen, plugin interface stable
**Stage 1:** FastAPI backend running, WebSocket + SSE working, Ollama streaming
**Stage 2:** kudbEE UI connected, events streaming in real-time, bento grid layout
**Stage 3:** Agent executes goal with streaming, tools work, memory persists
**Stage 4:** Approval flow works, audit log tamper-evident
**Stage 5:** Hot reload works, UI responsive, <100ms event latency
**Stage 6:** Agent shows reasoning, learns from past tasks
**Stage 7:** Docker deploy works, multi-user auth works
**Stage 8:** Plugin marketplace live, multi-agent orchestration works

---

## TECH STACK SUMMARY

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | FastAPI + WebSocket + SSE | Async, fast, great streaming |
| Frontend | React + Vite (or vanilla JS) | Fast dev, easy layout |
| Models | Ollama (local) + OpenAI (cloud) | Local-first, pluggable |
| Agent | Custom Python async loop | Full control, Devin-pattern |
| Plugins | Python async tools | Easy to extend |
| Storage | SQLite | Simple, local, fast |
| Events | WebSocket + SSE | Real-time, low latency |
| Brand | kudbEE — bee/honeycomb | Memorable, unique |

---

## FILES TO CREATE (Stage 1)

```
backend/
├── main.py                # FastAPI app
├── event_bus.py           # WebSocket broadcast
├── agent_loop.py          # Core loop
├── task_manager.py        # Task state
├── memory.py              # Memory system
├── model_registry.py      # Ollama + OpenAI
├── plugins/
│   ├── base.py
│   ├── filesystem.py
│   ├── terminal.py
│   ├── git.py
│   └── http.py
└── requirements.txt

apps/web/
├── server.js (deprecated, replace with backend/)
├── public/ (keep frontend)
└── runtime_bridge.py (deprecated)
```

---

## FILES TO KEEP (Already Built)

```
core/                    # Python agent runtime (KEEP)
├── foundation/
├── memory/
├── governance/
├── providers/
├── tools/
└── runtime/

apps/web/public/         # Frontend UI (KEEP)
├── index.html
├── css/main.css
└── js/app.js

tests/                   # Tests (KEEP)
├── unit/
├── integration/
└── e2e/
```

---

**Next action:** Start Stage 1 — build `backend/main.py` with FastAPI + WebSocket, wire to existing frontend.

---

## SYSTEM OVERVIEW — Compute Fabric Pattern

The Compute Fabric is the architectural pattern of nested Think Boxes that enables hierarchical goal decomposition, parallel execution, and multi-agent coordination.

```
Goal
  → Think Box (bounded context)
    → Planner (decompose goal into steps)
      → Actor (execute one step using a tool)
        → Observer (validate result)
          → Memory (record outcome)
            → Improvement (extract pattern)
```

**Compute Fabric:** A parent Think Box may spawn child Think Boxes for sub-goals. This enables:

- Hierarchical goal decomposition (root goal → sub-goals → leaf tasks)
- Parallel execution of independent sub-goals
- Isolated memory scopes per sub-goal
- Sub-goal approval and rollback

---

## PROVIDER STRATEGY

### Supported Providers

| Provider | Implementation | Status |
|----------|---------------|--------|
| OpenAI-compatible | HTTP client wrapping `/v1/chat/completions` | ✅ Implemented |
| Ollama | `OllamaProvider` wrapping local Ollama API | 🔄 Planned |
| Anthropic | HTTP client wrapping Messages API | 🔄 Planned |
| AWS Bedrock | `BedrockProvider` using `InvokeModel` API | 🔄 Planned |

### AWS Bedrock Provider

AWS Bedrock is the primary enterprise inference route for organizations already in the AWS ecosystem. Adding it as a provider demonstrates that the `ModelProvider` abstraction works for non-OpenAI-compatible APIs (Bedrock uses `InvokeModel` API, not `/v1/chat/completions`). This validates architecture principle 1.2 (Provider Independence) with a third, structurally different provider.

**Implementation:** `core/providers/bedrock.py` — `BedrockProvider` implementing `ModelProvider` for AWS Bedrock `InvokeModel` API. Secrets resolved via `SecretResolver` (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`).

---

## STAGE 9 — 10 Improvements (Post-Foundation)

**Goal:** Address architectural gaps identified in `docs/improvements.md`. Wire the runtime execution loop, unify plugin systems, add enterprise providers, and expose compute fabric management.

### 9.1 Complete the Runtime Execution Loop
- [ ] Wire `Provider` into `Planner` for real goal decomposition
- [ ] Wire `Actor` to invoke tools from `ToolRegistry` with permission checks
- [ ] Pass `provider` to `Planner` in `Agent.run()`
- [ ] Wire `Actor` with `ctx.tool_registry`, `ctx.approval_gate`, `ctx.audit_log`

### 9.2 Add OllamaProvider
- [ ] Create `core/providers/ollama.py` implementing `ModelProvider` protocol
- [ ] Wrap `ollama_client.py` logic behind the `ModelProvider` interface
- [ ] Register `OllamaProvider` when `THINKBOX_PROVIDER=ollama`

### 9.3 Implement Approval Gate End-to-End
- [ ] Actor checks `approval_required` before tool invocation
- [ ] Actor calls `approval_gate.require_approval()` for restricted tools
- [ ] Pass `approval_gate` to `Actor` construction

### 9.4 Unify Plugin Systems
- [ ] Refactor `backend/plugins/` to register tools with core `ToolRegistry`
- [ ] Replace direct plugin calls in `backend/agent_loop.py` with `ToolRegistry` lookups
- [ ] Extend core tools with any missing from `backend/plugins/` (e.g., `git_operations`)

### 9.5 Add Secrets/Capabilities Resolution
- [ ] Create `core/foundation/secrets.py` — `SecretResolver` class
- [ ] Implement `resolve()`, `has_capability()`, lazy evaluation
- [ ] Integrate `SecretResolver` into `ThinkBoxConfig`
- [ ] Never log secret values

### 9.6 Implement Compute Fabric Pattern
- [ ] Add `parent` reference, `children` list to `ThinkBox`
- [ ] Decompose goals into sub-goals in `Planner`
- [ ] Support nested execution in `Agent.run()` — spawn child Think Boxes
- [ ] Namespace memory by `task_id` for sub-goal isolation

### 9.7 Add AWS Bedrock Provider
- [ ] Create `core/providers/bedrock.py` — `BedrockProvider`
- [ ] Implement `ModelProvider` for AWS Bedrock `InvokeModel` API
- [ ] Register `BedrockProvider` when `THINKBOX_PROVIDER=bedrock`
- [ ] Resolve AWS credentials via `SecretResolver`

### 9.8 Connect Core Runtime to Backend
- [ ] Replace `run_agent_task()` with `core.runtime.Agent.run()`
- [ ] Subscribe `event_bus.py` to core runtime events
- [ ] Emit events at each loop iteration in `Agent.run()`

### 9.9 Implement Memory Persistence
- [ ] Implement `flush()` in `SessionMemoryAdapter`
- [ ] Implement `flush()` in `TaskMemoryAdapter`
- [ ] Implement `flush()` in `OrganizationalMemoryAdapter`
- [ ] Call `flush()` on session/task/org adapters at `run()` completion

### 9.10 Add CLI Commands for Compute Fabric Management
- [ ] Add `thinkbox list`, `thinkbox status <id>`, `goal tree <task_id>`
- [ ] Add `approve <request_id>`, `memory query <key>`, `provider list`
- [ ] Expose introspection API in `Agent`
- [ ] Add `list_all()` with full tool metadata to `ToolRegistry`

---

## KUDBEE COMPUTE FABRIC ROADMAP

The Compute Fabric maps the 10 improvements to implementation priorities:

### Phase 1: Foundation (Complete)

- Single Think Box, sequential execution
- One provider (OpenAI-compatible)
- Core runtime loop structure exists but unwired

### Phase 2: Wire the Loop

Implement improvements #1, #2, #3, #5:

| # | Improvement | Priority |
|---|-------------|----------|
| 1 | Complete the Runtime Execution Loop | **Critical** |
| 2 | Add OllamaProvider | **High** |
| 3 | Implement Approval Gate End-to-End | **High** |
| 5 | Add Secrets/Capabilities Resolution | **Medium** |

**Target:** Provider → Planner → Actor → Tools → Observer → Memory loop functional with Ollama and OpenAI providers, approval gate enforced, secrets resolution.

### Phase 3: Nested Execution

Implement improvements #6, #9:

| # | Improvement | Priority |
|---|-------------|----------|
| 6 | Implement Compute Fabric Pattern | **Medium** |
| 9 | Implement Memory Persistence | **Medium** |

**Target:** Think Boxes can spawn child Think Boxes, sub-goal trees with isolated memory scopes, memory flush on session/task completion.

### Phase 4: Enterprise Providers

Implement improvements #7, #4:

| # | Improvement | Priority |
|---|-------------|----------|
| 7 | Add AWS Bedrock Provider | **Medium** |
| 4 | Unify Plugin Systems | **Medium** |

**Target:** AWS Bedrock provider operational, unified plugin system (core tools only), backend delegates to core runtime.

### Phase 5: Operational Interface

Implement improvements #8, #10:

| # | Improvement | Priority |
|---|-------------|----------|
| 8 | Connect Core Runtime to Backend | **Medium** |
| 10 | Add CLI Commands | **Low** |

**Target:** Backend fully uses core runtime via `Agent.run()`, CLI exposes compute fabric introspection and control, WebSocket events sourced from core runtime.

---

## IMPLEMENTATION PRIORITY SUMMARY

| # | Improvement | Priority | Depends On | Phase |
|---|-------------|----------|------------|-------|
| 1 | Complete the Runtime Execution Loop | **Critical** | — | 2 |
| 2 | Add OllamaProvider | **High** | — | 2 |
| 3 | Implement Approval Gate End-to-End | **High** | #1 | 2 |
| 4 | Unify Plugin Systems | **Medium** | #1 | 4 |
| 5 | Add Secrets/Capabilities Resolution | **Medium** | — | 2 |
| 6 | Implement Compute Fabric Pattern | **Medium** | #1, #3 | 3 |
| 7 | Add AWS Bedrock Provider | **Medium** | #5 | 4 |
| 8 | Connect Core Runtime to Backend | **Medium** | #1, #4 | 5 |
| 9 | Implement Memory Persistence | **Medium** | #1 | 3 |
| 10 | Add CLI Commands | **Low** | #1, #6 | 5 |

---

*Reference: `docs/improvements.md` for detailed current state, architecture mapping, and rationale for each improvement.*
