# THINK BOX AI — Architecture v1

**Status:** Draft — Phase 0
**Date:** 2026-08-20
**Supersedes:** None (first architecture document)

---

## 1. Purpose

This document defines the **structural boundaries** of the system. It answers
*what the components are* and *how they connect*, but does not prescribe every
implementation detail. Implementation choices belong in code and in decision
records (see `docs/decisions/`).

This version is the **minimum viable architecture**. It exists to prevent
architectural drift in Phase 1. It will be revised when reality contradicts
it.

---

## 2. System Overview

THINK BOX AI is an **agent execution environment**. Users provide goals. The
system decomposes them, executes bounded reasoning loops, uses tools, records
outcomes, and improves over time.

```
Goal
  → Think Box (bounded context)
    → Planner (decompose goal into steps)
      → Actor (execute one step using a tool)
        → Observer (validate result)
          → Memory (record outcome)
            → Improvement (extract pattern)
```

The outer loop is the Agent Runtime. The inner loop is the Think Box.

---

## 3. System Layers

Layers are **strictly ordered**. A layer may only depend on layers beneath it.

```
┌─────────────────────────────────────────────────────┐
│  Layer 5 — Agent Implementations                    │
│  (specific agent types, personalities, workflows)   │
├─────────────────────────────────────────────────────┤
│  Layer 4 — Agent Runtime                            │
│  (execution loop, Think Box, Planner, Actor,        │
│   Observer, Improvement)                            │
├─────────────────────────────────────────────────────┤
│  Layer 3 — Tool Registry & Governance               │
│  (tool definitions, permission checks, audit log,   │
│   approval gates)                                   │
├─────────────────────────────────────────────────────┤
│  Layer 2 — Memory Subsystem                         │
│  (session, task, organizational, verified knowledge) │
├─────────────────────────────────────────────────────┤
│  Layer 1 — Provider Abstraction                     │
│  (model interface, OpenAI-compatible, Anthropic,    │
│   local, streaming, retry, rate limit)              │
├─────────────────────────────────────────────────────┤
│  Layer 0 — Foundation                               │
│  (config, schemas, logging, error handling)         │
└─────────────────────────────────────────────────────┘
```

**Dependency rule:** Layer N may only import from layers 0 through N-1.
Violating this rule is an architectural error.

---

## 4. Core Concepts

### 4.1 Goal

A Goal is the user's intent, decomposed into a tree of sub-goals.

```
Goal
  └── Sub-goal 1
  └── Sub-goal 2
      └── Sub-sub-goal 2.1
```

A Goal has:
- `id`: unique identifier
- `statement`: natural language description
- `success_criteria`: observable, testable conditions
- `parent`: reference to parent goal (None for root)
- `status`: pending | running | succeeded | failed | blocked
- `result`: outcome when terminal

### 4.2 Think Box

The **Think Box** is the smallest unit of bounded agent execution.

> **What is the smallest useful Think Box?**
> A Think Box is useful when it contains: (1) a goal statement, (2) a memory
> snapshot relevant to that goal, (3) a registry of available tools with
> their schemas and permission levels, and (4) a set of constraints (time,
> token budget, approval requirements). Without these four, the agent is
> operating blind.

A Think Box:
- Is **ephemeral** — created for a sub-goal, destroyed on completion.
- Has a **lifecycle**: `initialized → planning → executing → observing → complete | failed`.
- Has a **budget**: maximum iterations, maximum tokens, maximum tool calls.
- Has a **memory reference**: it reads from and writes to memory, but does
  not own memory.

Think Boxes may be nested. A parent Think Box may spawn child Think Boxes for
sub-goals.

### 4.3 Planner

The Planner decomposes a Goal into an ordered sequence of Steps.

A Step is:
- `id`: unique within the Think Box
- `description`: what the step does
- `tool`: which tool to invoke (or `None` for reasoning-only steps)
- `input_schema`: expected input shape
- `expected_output`: what success looks like
- `approval_required`: boolean

### 4.4 Actor

The Actor executes one Step by:
1. Validating the step against current Think Box state
2. Checking permissions for the tool
3. Calling the tool via the Tool Registry
4. Recording the result in the Observer

The Actor never calls a model directly. It calls tools. The model is used by
the Planner and Observer to interpret results.

### 4.5 Observer

The Observer validates whether a Step's result meets its `expected_output`.

Validation is:
- **Structural**: does the output match the schema?
- **Goal-aligned**: does the output contribute to the parent Goal's success
  criteria?

If validation fails, the Observer signals the Planner to replan (replan loop).

### 4.6 Improvement

The Improvement layer extracts patterns from completed goals and feeds them
into Organizational Memory.

This includes:
- Successful tool sequences
- Failure modes and recovery strategies
- Prompt/strategy refinements (measured, not assumed)

---

## 5. Memory Strategy

> **What should an agent remember?**
> An agent should remember: (1) outcomes of every tool call, (2) reasoning
> steps taken, (3) verified facts (not guesses), (4) errors and how they
> were resolved, and (5) the provenance of every memory entry (which agent,
> which task, which observation).

Memory has four layers. They are **not** a chat history.

### 5.1 Session Memory

- **Scope:** One user session or conversation.
- **Lifetime:** From session start to session end.
- **Contents:** Goal tree, recent tool calls, recent observations, current
  Think Box state.
- **Storage:** In-memory (dict), flushed to SQLite on session end.
- **Key:** `session:{session_id}`

### 5.2 Task Memory

- **Scope:** One goal decomposition (one root Goal and all its sub-goals).
- **Lifetime:** From goal creation to goal termination.
- **Contents:** Step results, validation outcomes, replan history, error logs.
- **Storage:** In-memory during execution, persisted to SQLite on completion.
- **Key:** `task:{task_id}`

### 5.3 Organizational Memory

- **Scope:** Cross-task, long-lived.
- **Lifetime:** Indefinite, versioned.
- **Contents:** Verified patterns, known-good tool sequences, failure
  signatures, benchmark results, provider performance data.
- **Storage:** SQLite with schema versioning.
- **Key:** `org:*`
- **Write policy:** Append-only. Writes require evidence (a completed task
  with measurable outcome). No speculative entries.

### 5.4 Verified Knowledge

- **Scope:** Facts that have been confirmed through execution.
- **Lifetime:** Indefinite, but with confidence scores that decay over time
  or on contradiction.
- **Contents:** Confirmed tool capabilities, confirmed model behaviors,
  confirmed API contracts.
- **Storage:** Same as Organizational Memory, tagged `verified`.

### Memory Implementation (Phase 1)

```
memory/
  __init__.py
  store.py         # Key-value interface over SQLite
  session.py       # Session memory adapter
  task.py          # Task memory adapter
  org.py           # Organizational memory adapter
  schema.py        # Memory entry schemas
  migrations/      # SQLite schema migrations
```

No external database is required. SQLite is sufficient for Phase 1.

---

## 6. Provider Strategy

> **How do we verify model independence?**
> By implementing at least two providers against the same interface, and
> by measuring swap cost (lines of config change, not lines of code change).
> If swapping providers requires touching the runtime, the abstraction
> failed.

### 6.1 Interface

Every provider implements:

```python
class ModelProvider(Protocol):
    async def complete(self, messages: list[Message], **kwargs) -> Completion
    async def stream(self, messages: list[Message], **kwargs) -> AsyncIterator[Chunk]
    async def embed(self, texts: list[str]) -> list[Embedding]
    @property
    def capabilities(self) -> ProviderCapabilities
```

### 6.2 Capabilities

A provider declares its capabilities:

```python
@dataclass
class ProviderCapabilities:
    completion: bool = True
    streaming: bool = False
    embedding: bool = False
    function_calling: bool = False
    max_context_tokens: int = 0
    supports_system_prompt: bool = True
```

The runtime queries capabilities at startup and adjusts behavior accordingly.

### 6.3 Provider Implementations (Phase 1)

| Provider | Implementation | Notes |
|----------|---------------|-------|
| OpenAI-compatible | HTTP client wrapping `/v1/chat/completions` | Covers OpenAI, Groq, Together, vLLM, Ollama, any compatible API |
| Anthropic | HTTP client wrapping Messages API | If network access is available during development |

### 6.5 Provider Router

The `ProviderRouter` enables multi-provider routing and failover:

```python
router = ProviderRouter({
    "providers": [
        {"name": "openai_compat", "model": "gpt-4o-mini"},
        {"name": "openai_compat", "model": "local", "base_url": "http://localhost:8000/v1"},
    ],
    "order": ["openai_compat"],
    "snapshot_cache": True,
    "persistent_cache_path": "~/.local/share/thinkbox/snapshot_cache.db",
})
```

**Snapshot hashing**: SHA-256 of model input for cache/dedup
**Failover**: Tries providers in order, continues on error
**Snapshot cache**: Skips model call when input unchanged (in-memory + persistent SQLite)

**Not implemented in Phase 1:**
- Local GGUF models (deferred until local inference is needed)
- Custom fine-tuned models (use OpenAI-compatible endpoint instead)

### 6.4 Provider Selection

Provider is selected by configuration, not by code:

```python
provider = get_provider(config.provider_name, config.provider_config)
```

Swapping providers is a config change. No runtime code changes required.

---

## 7. Tool Strategy

> **What actions require approval?**
> Any tool that: (1) modifies persistent state (file write, database write,
> memory write), (2) makes external network calls, (3) executes shell
> commands, or (4) sends messages to external systems, requires explicit
> approval. Read-only tools that query internal state do not.

### 7.1 Tool Definition

Every tool is a stateless function with a declarative schema:

```python
@tool(
    name="file_read",
    description="Read contents of a file",
    input_schema=FileReadInput,
    permission=PermissionLevel.READ_ONLY,
    approval_required=False,
)
async def file_read(input: FileReadInput) -> FileReadOutput:
    ...
```

### 7.2 Permission Levels

| Level | Description | Examples |
|-------|-------------|---------|
| `READ_ONLY` | No side effects | file_read, search, query |
| `READ_WRITE` | Modifies local state | file_write, memory_write |
| `NETWORK` | External calls | http_request, api_call |
| `EXEC` | Shell execution | shell_command, code_interpreter |
| `RESTRICTED` | Requires human approval | delete, deploy, send_message |

### 7.3 Tool Registry

The Tool Registry is a singleton that:
- Indexes tools by name and permission level
- Validates inputs against schemas before execution
- Logs every call to the audit log
- Enforces approval gates before execution

Tools do not call each other directly. The Actor mediates all tool calls.

### 7.4 Tool Implementations (Phase 1)

| Tool | Permission | Description |
|------|-----------|-------------|
| `file_read` | READ_ONLY | Read file contents |
| `file_write` | READ_WRITE | Write file contents (approval required for new files) |
| `shell_exec` | EXEC | Execute shell commands (approval required) |
| `http_request` | NETWORK | Make HTTP requests (approval required) |
| `memory_query` | READ_ONLY | Query memory store |
| `memory_write` | READ_WRITE | Write to memory (approval required) |

No tools are pre-registered. Tools are added by importing and decorating.

---

## 8. Security & Governance

> **How do we verify success?**
> Every goal has explicit success criteria. Every step has expected output.
> Verification is structural (does output match schema?) and goal-aligned
> (does output advance the success criteria?). If either check fails, the
> step is marked failed and the planner replans. Success is never assumed;
> it is measured.

### 8.1 Audit Log

Every significant action is logged:

```
{
  "timestamp": "2026-08-20T08:00:00Z",
  "agent_id": "agent-001",
  "task_id": "task-abc",
  "think_box_id": "tb-123",
  "action": "tool_call",
  "tool": "file_write",
  "input": {...},
  "output": {...},
  "approval_granted": true,
  "result": "success | failure",
  "error": null
}
```

The audit log is:
- Append-only (writes only, no updates or deletes).
- Stored in SQLite with a tamper-evident hash chain (simple sequential hash).
- Retained for the lifetime of the task and session.

### 8.2 Approval Gates

Certain tools require explicit approval before execution:

1. The Actor detects `approval_required=True`.
2. The Actor pauses and emits an `approval_requested` event.
3. A human (or an approval policy engine) responds with `approve` or `deny`.
4. The Actor proceeds or aborts.

In Phase 1, approval is manual (CLI prompt). Future phases may implement
policy-based automated approval for low-risk tools.

### 8.3 Permission Model

Permissions are checked at two points:

1. **Before execution:** Tool Registry checks the agent's permission set
   against the tool's required level.
2. **Before approval:** The governance layer checks whether the action is in
   the allowed set for the current policy.

Agents start with `READ_ONLY` permission. Elevated permissions are granted
explicitly per session or per task.

### 8.4 Sandboxing (Future)

Tool execution must eventually run in a sandbox. Phase 1 does not implement
sandboxing. The architecture must be designed so that the execution boundary
is clear and replaceable.

---

## 9. Multi-Agent Coordination

> **How do multiple agents coordinate?**
> Through shared memory and a task hierarchy. Agents do not communicate
> directly. They read and write to the same memory store, and the runtime
> schedules Think Boxes for sub-goals. Coordination is implicit through
> memory state, not explicit through message passing.

### 9.1 Task Tree

Multiple agents operate on the same Goal tree. Each agent owns one or more
sub-goals. The runtime ensures no two agents write to the same memory key
concurrently (optimistic locking via SQLite transactions).

### 9.2 Shared Memory

Organizational Memory is the coordination substrate:
- Agent A writes a verified pattern to `org:patterns:file_write`.
- Agent B reads from `org:patterns:file_write` before deciding how to write
  a file.

Memory writes are tagged with agent ID and task ID, enabling attribution and
conflict detection.

### 9.3 Conflict Resolution

- If two agents attempt to modify the same memory entry, the second write
  fails with a conflict error.
- The runtime replans the conflicting sub-goal with updated memory state.

---

## 10. System Improvement

> **How does the system improve?**
> Through measured outcome analysis. Every completed goal produces data.
> The Improvement layer analyzes patterns across goals: which tool sequences
> succeeded, which failed, under what conditions. Patterns are promoted to
> Organizational Memory only when they are verified by multiple outcomes.
> Improvement is never speculative; it is evidence-driven.

### 10.1 Outcome Logging

Every completed task logs:
- Goal tree shape (success/failure at each node)
- Tool sequence used
- Time per step
- Token usage per model call
- Validation outcomes

### 10.2 Pattern Extraction (Phase 2+)

Phase 1 stores raw outcomes. Phase 2 adds pattern extraction:
- Cluster successful tool sequences
- Identify failure modes
- Correlate model choice with outcome quality

### 10.3 Benchmarking

A benchmark suite measures:
- Goal completion rate
- Time to completion
- Token efficiency
- Tool call efficiency
- Replan frequency

Benchmarks run on a fixed set of goals. Results are stored in Organizational
Memory and compared over time.

---

## 11. Project Structure

```
thinkbox-ai/
├── apps/
│   ├── cli/                    # CLI interface (Phase 1)
│   │   ├── main.py
│   │   ├── commands/
│   │   └── repl.py
│   └── web/                    # Web interface (deferred)
│       └── ...
├── core/
│   ├── runtime/                # Agent Runtime
│   │   ├── __init__.py
│   │   ├── agent.py            # Agent class, execution loop
│   │   ├── thinkbox.py         # Think Box lifecycle
│   │   ├── planner.py          # Goal decomposition
│   │   ├── actor.py            # Step execution
│   │   ├── observer.py         # Result validation
│   │   └── improvement.py      # Pattern extraction (Phase 2)
│   ├── memory/                 # Memory Subsystem
│   │   ├── __init__.py
│   │   ├── store.py            # Key-value interface over SQLite
│   │   ├── session.py          # Session memory adapter
│   │   ├── task.py             # Task memory adapter
│   │   ├── org.py              # Organizational memory adapter
│   │   ├── schema.py           # Memory entry schemas
│   │   └── migrations/         # SQLite schema migrations
│   ├── providers/              # Provider Abstraction
│   │   ├── __init__.py
│   │   ├── base.py             # ModelProvider protocol, dataclasses
│   │   ├── openai_compat.py    # OpenAI-compatible HTTP provider
│   │   ├── anthropic.py        # Anthropic provider
│   │   └── local.py            # Local model provider (Phase 2)
│   ├── tools/                  # Tool Registry
│   │   ├── __init__.py
│   │   ├── registry.py         # Tool registration, lookup, validation
│   │   ├── decorator.py        # @tool decorator
│   │   ├── file_tools.py       # file_read, file_write
│   │   ├── shell_tools.py      # shell_exec
│   │   ├── http_tools.py       # http_request
│   │   └── memory_tools.py     # memory_query, memory_write
│   └── governance/             # Governance
│       ├── __init__.py
│       ├── audit.py            # Audit log
│       ├── permissions.py      # Permission levels, checks
│       └── approval.py         # Approval gate logic
├── agents/                     # Agent Implementations
│   ├── __init__.py
│   ├── base.py                 # Base agent class
│   └── ...
├── benchmarks/                 # Benchmark Suite
│   ├── __init__.py
│   ├── suite.py
│   ├── goals.py                # Fixed benchmark goals
│   └── metrics.py              # Measurement functions
├── docs/
│   ├── project-foundation.md
│   ├── architecture-v1.md      # This document
│   ├── architecture/
│   │   └── ...
│   ├── guides/
│   │   └── ...
│   └── decisions/
│       └── 001-*.md
├── tests/
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── e2e/                    # End-to-end tests
├── pyproject.toml              # Project configuration
├── README.md
└── AGENTS.md                   # Development rules
```

---

## 12. Data Flow

A typical execution path:

```
User provides Goal
    │
    ▼
Agent Runtime creates Think Box
    │
    ▼
Planner decomposes Goal → Step list
    │
    ▼
For each Step:
    Actor checks permissions
        │
        ├── approval_required? → pause for approval
        │
    Actor calls Tool via Tool Registry
        │
        ▼
    Observer validates result against Step.expected_output
        │
        ├── success → continue to next Step
        └── failure → Planner replans
    │
    ▼
All Steps complete → Goal succeeds
    │
    ▼
Improvement layer extracts pattern → writes to Organizational Memory
    │
    ▼
Think Box destroyed, memory persisted
```

---

## 13. Configuration

Configuration is hierarchical and environment-driven:

```
System defaults  (in code)
    ↓
Project config   (pyproject.toml [tool.thinkbox])
    ↓
Environment vars (THINKBOX_*)
    ↓
Runtime overrides (CLI flags)
```

No configuration is hardcoded. Every configurable value has a default.

---

## 14. Error Handling Philosophy

- **Fail loudly, fail early.** Errors are not swallowed. They are logged,
  attributed, and surfaced to the user.
- **No silent fallbacks.** If a provider is unreachable, the runtime raises.
  It does not silently fall back to a different model without explicit
  configuration.
- **Structured errors.** All errors carry: agent ID, task ID, Think Box ID,
  timestamp, error type, and context. They are not bare strings.
- **Recovery is explicit.** The Observer decides whether to replan, retry,
  or abort. Automatic retry is opt-in per tool, not the default.

---

## 15. Phase 1 Boundaries

Phase 1 implements the **minimum viable execution loop**:

| Component | Phase 1 Scope |
|-----------|---------------|
| Agent Runtime | Single agent, single Think Box, sequential step execution |
| Memory | Session + Task memory, SQLite-backed |
| Providers | OpenAI-compatible only |
| Tools | file_read, file_write, shell_exec, http_request, memory_query |
| Governance | Permission checks, audit log, manual approval for restricted tools |
| Improvement | Outcome logging only (no pattern extraction) |
| Multi-agent | Not implemented |
| Benchmarks | Not implemented |
| UI | Not implemented |

Phase 1 goal: prove the architecture works end-to-end with a single goal,
a single agent, and one provider.

---

## 16. Open Questions

These questions are unresolved. They must be answered before or during
implementation, not deferred indefinitely.

| # | Question | Owner | Resolution |
|---|---------|-------|------------|
| Q1 | What is the maximum safe Think Box depth for Phase 1? | Architecture | Limit to 2 levels (root + one nesting) |
| Q2 | How are memory keys namespaced across sessions? | Memory | Use `{layer}:{scope}:{id}` format |
| Q3 | What is the audit log retention policy? | Governance | Retain for 90 days, then archive |
| Q4 | How are schemas defined and validated without pydantic? | Foundation | Use dataclasses + manual validation in Phase 1, add pydantic when schemas stabilize |
| Q5 | Should the runtime be sync or async? | Runtime | Async (asyncio), required for concurrent tool I/O |
| Q6 | How are benchmarks executed and reported? | Benchmarks | CLI command, JSON output, deferred to Phase 2 |

---

## 17. What This Document Is Not

This document is **not**:
- A feature list
- An API reference
- A deployment guide
- A performance specification

It is a **structural contract**. Implementation may vary within the bounds it
defines. When implementation contradicts this document, the document is wrong
and must be revised.

**Next step:** `AGENTS.md` captures the development rules that govern how this
architecture is translated into code.