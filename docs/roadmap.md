# KUdBEE — Implementation Roadmap

**Project:** kudbEE — Local-first, streaming, Devin-like agent OS
**Architecture:** Python backend (FastAPI + WebSocket + SSE) + React/Vite frontend + Ollama/OpenAI models
**Brand:** kudbEE — bee/honeycomb/hive metaphor, warm amber on dark, fast local dev UX

---

## PHASE 9 — Zero-to-One Innovations (Complete)

> **2026-09-23:** KILO Live-proof readiness arc **#141–#150** — runbook at `docs/runbooks/kilo-live-proof-readiness.md` (spine in PR #141; Live proof not claimed until #150).

**Goal:** 55 novel innovations across coalition, consensus, economy, intelligence, and benchmarking subsystems.

### Phase 9 Modules

- [x] `thinkbox/coalition.py` — CRDT shared memory, task bidding market, pub/sub bus, capability registry, governance voting
- [x] `thinkbox/consensus.py` — Multi-model voting, Bayesian confidence scoring, disagreement resolution, model ranking, audit trail
- [x] `thinkbox/economy.py` — Token economy, contribution mining, staking mechanism, slash conditions, treasury governance
- [x] `thinkbox/intelligence.py` — Knowledge graph, self-healing, reputation, federated learning, post-quantum security
- [x] `thinkbox/benchmark.py` — High-throughput concurrency scaling sweeps (16–512 workers), system metrics, markdown report generation
- [x] `thinkbox/session.py` — Session tracking with Upstash Vector sync

### Phase 9 Bug Fixes

| Bug | File | Fix |
|-----|------|-----|
| Missing treasury account | `thinkbox/economy.py` | Added treasury existence check in `AgentTokenEconomy.transfer()` |
| `_threshold` attribute | `thinkbox/consensus.py` | Added validation in `DisagreementResolver.__init__` |

### Phase 9 Testing

Phase 9 innovations are tested in `tests/unit/test_session_tracker.py` (27 tests)
covering all Phase 9 modules. Each innovation has at least one unit test covering
valid input, invalid input, and edge cases.

---

## STAGE 0 — Foundation Lock (Week 1)

**Goal:** Stable Python package, event schema, agent loop contract, plugin interface.

### 0.1 Core Python package
- [x] `core/foundation/` — config, logging, errors, bootstrap
- [x] `core/memory/` — SQLite store, session/task/org adapters, schemas
- [x] `core/governance/` — audit log, permissions, approval gate
- [x] `core/providers/` — ModelProvider protocol, OpenAI-compatible provider
- [x] `core/tools/` — registry, decorator, 5 built-in tools (file_read, file_write, shell_exec, http_request, memory_query)
- [x] `core/runtime/` — Agent, Goal, Step, ThinkBox, Planner, Actor, Observer
- [x] `tests/unit/` — tests passing
- [x] `tests/integration/` — tests passing
- [ ] `tests/e2e/` — pending

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

## MILESTONE — THINKBOXMD-RESEARCH (2026-09-15)

**Goal:** prove KUDBEE can run a real end-to-end research workflow on existing
infrastructure with a live model, an auditable proof, and honest failure handling.

### Verified this milestone

- [x] **Live provider.** Inception **Mercury 2** (`api.inceptionlabs.ai/v1`) works
      from the cloud sandbox. Earlier "TLS-blocked" status was wrong-host.
- [x] **Think Box + governance + ledger.** Box created, persisted to SQLite,
      admitted through the gate, recorded in a SHA-256 hash chain that verifies.
- [x] **Five-worker swarm.** PHARMA / TOX / VALIDATOR / SAFETY / SYNTH, each a
      **live** model call (not simulated).
- [x] **Tiered findings.** `EVIDENCE` / `INFERENCE` / `HYPOTHESIS` / `UNVERIFIED`.
- [x] **Failure recovery.** Injected provider failure → detected → preserved in
      ledger → recovered on a healthy endpoint.
- [x] **Proof artifacts.** Machine JSON + human Markdown + proof hash.

### Verified, honestly-limited (PARTIAL)

- [~] **MEMORY.** Local SQLite Commons works. **Upstash Vector writes are broken**
      against the dense index (`HTTP 422`); no embedding provider exists.
- [~] **THINK INTEGRATION.** Token economy is integer simulation, not settlement.

### Not built (blocking production-grade THINKBOXMD)

- [ ] **Distributed execution substrate** — worker process isolation + scheduler.
      *This is the single largest missing capability.*
- [ ] **Credentialed work queue** (Upstash Redis) so work survives a dropped connection.
- [ ] **Upstash Box execution client** (currently metadata-only; preview not found).
- [ ] **UpCloud access** — API token rejected (401); SSH key absent. Needs a fresh
      token/key from the panel.
- [ ] **MCP tool bridge** — none configured.
- [ ] **Embedding provider** — required to repair Vector memory.
- [ ] **`tests/e2e/`** — still empty.

### Next larger improvement (ordered)

1. **Embedding provider** → repair Vector memory (unblocks distributed Commons).
2. **Worker process isolation + Redis work queue** → durable, resumable swarm.
3. **UpCloud worker** → put the credentialed 16-CPU machine behind the queue.
4. **MCP bridge** → real evidence retrieval (FDA/PubMed-style sources).

**Next action:** implement an embedding provider and fix
`thinkbox/session.py::UpstashVectorSync.upsert()` (see
`data/findings/thinkboxmd_upstash_vector_defect.md`).

---

## MILESTONE — SWARM INSTRUMENTATION (2026-09-15)

**Goal:** turn a swarm run into a measurable experiment. "Our AI got smarter" is
not a claim we make; "after N runs the validated index moved by X" is.

### Shipped

- [x] `thinkbox/flightrecorder.py` — permanent per-worker records + proof chains + genomes
- [x] `thinkbox/arena.py` — adversarial traps with detection/challenge/recovery rates
- [x] `thinkbox/metrics.py` — THINK Swarm Strength Index + session store + learning curve
- [x] `thinkbox/memory_evolution.py` — memory lifecycle (created→…→promoted/decayed)
- [x] `thinkbox/reputation.py` — worker reputation from demonstrated performance
- [x] `thinkbox/experiments.py` — A/B variants, self-improvement loop, cost/insight
- [x] `experiments/big_swarm.py` — the harness that drives all ten
- [x] `experiments/swarm_dashboard.py` — mobile-first, stdlib, DB-backed view
- [x] `experiments/verify_instrumentation.py` — 10 checks + `--live` end-to-end
- [x] `tests/unit/test_swarm_instrumentation.py` — 22 unit tests

### Evidence

- 11/11 instrumentation checks pass (10 offline + 1 live)
- Full suite: **301 tests OK**
- Learning curve: `0.6405 → 0.7318 (+0.0913)`
- Mercury 2 ceiling measured: **~24 rps** single client, 0 errors to conc 64

### Next

- [ ] Wire `SelfImprovementLoop` into the swarm run so the retest happens automatically
- [ ] Persist arena outcomes per session (currently reported in the proof payload)
- [ ] Add a `--replay <session_id>` path that reloads a genome and re-runs identically
- [ ] Reputation-weighted worker sampling in the next wave
- [ ] Implement `docs/DASHBOARD_BUILDOUT.md` Phase 1–4 (harden middleware, optional auth)

