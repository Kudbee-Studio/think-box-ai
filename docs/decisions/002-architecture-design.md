# ADR 002: Architecture Design — Upstash Box Execution Substrate, Provider-Agnostic Interfaces, Box Sizing, Lifecycle, and Kilo Bootstrap

**Date:** 2026-08-21
**Status:** Accepted (design phase, not yet implemented)
**Supersedes:** None
**Related:** ADR-001 (Execution Substrate)

---

## 1. Context

ADR-001 established the four-layer separation: Mayor (control plane), QStash
(orchestration), Upstash Box (execution substrate), Vector + Structured DB
(memory), Kilo (bootstrap-only), and BYOK LLM provider. This document
formalizes that architecture, reconciles it with the existing 5-layer code
architecture (`docs/architecture-v1.md`), defines provider-agnostic interfaces,
and specifies the Box sizing policy, lifecycle, and Kilo's role.

**Goal:** Produce a design that makes Upstash an *implementation* of the
execution substrate, not the architecture itself. All access goes through
provider-agnostic interfaces so that any compliant implementation can replace
Upstash without code changes.

---

## 2. Phase 1 — Review of Existing Architecture

### 2.1 Existing 5-Layer Code Architecture

The existing `core/` package implements a strict 5-layer architecture
(`docs/architecture-v1.md`):

| Layer | Module | Responsibility |
|-------|--------|----------------|
| Layer 0 — Foundation | `core/foundation/` | Config, logging, errors, bootstrap |
| Layer 1 — Provider Abstraction | `core/providers/` | `ModelProvider` protocol, OpenAI-compatible impl |
| Layer 2 — Memory Subsystem | `core/memory/` | SQLite-backed key-value store, Session/Task/Org adapters |
| Layer 3 — Tool Registry & Governance | `core/tools/`, `core/governance/` | Tool definitions, permission checks, audit log, approval gates |
| Layer 4 — Agent Runtime | `core/runtime/` | Agent, ThinkBox, Planner, Actor, Observer |

**Dependency rule:** Layer N may only import from layers 0 through N-1.

### 2.2 Existing Deployment Architecture

The existing `backend/` and `apps/web/` directories implement a *different*
deployment model:

- **`backend/main.py`** — FastAPI app with WebSocket + SSE. Contains its own
  agent loop (`run_agent_task`) that streams tokens from Ollama directly,
  bypassing the entire `core/runtime/` stack. Uses `backend/plugins/` (a
  separate tool system from `core/tools/`). Stores session state in
  in-memory dicts, not in the SQLite-backed `core/memory/store.py`.

- **`apps/web/server.js`** — Node.js Express + WebSocket server. Contains its
  own `AgentSession` class with its own agent loop, its own plugin system
  (`apps/web/services/plugins.js`), and its own in-memory state. Was
  intended to be replaced by the FastAPI backend per `docs/roadmap.md`
  ("NEW — replace Node.js with Python"), but both still exist.

- **`think_box_ai/`** — A separate package containing only the Think Token
  utility (`token.py`, `cli.py`). Unrelated to the agent runtime.

### 2.3 Where the Proposed Upstash Architecture Fits

The proposed architecture introduces a **deployment/runtime dimension** that
the existing 5-layer code architecture does not address:

```
┌─────────────────────────────────────────────────────────┐
│  CONTROL PLANE (outside Box)                            │
│  Mayor → decides what / which size / which provider     │
│  QStash → dispatches tasks to Boxes                     │
│  Kilo → provisions Boxes (bootstrap only)               │
├─────────────────────────────────────────────────────────┤
│  EXECUTION SUBSTRATE (inside Box)                       │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Layer 4 — Agent Runtime (core/runtime/)          │  │
│  │  Layer 3 — Tool Registry & Governance             │  │
│  │  Layer 2 — Memory Subsystem                       │  │
│  │  Layer 1 — Provider Abstraction                   │  │
│  │  Layer 0 — Foundation                             │  │
│  └───────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  SHARED MEMORY (outside Box, accessible to all)         │
│  Vector DB + Structured DB                              │
└─────────────────────────────────────────────────────────┘
```

The Box hosts the entire 5-layer stack. The Mayor, QStash, and Kilo operate
*outside* the Box and communicate with it via the `QueueProvider` interface.
The memory system (Vector + Structured DB) is shared between the Box and the
control plane.

### 2.4 Conflicts Identified

| # | Conflict | Details |
|---|----------|---------|
| C1 | **Three competing agent runtimes** | `core/runtime/` (proper Think Box loop), `backend/main.py` (FastAPI agent loop bypassing core), `apps/web/server.js` (Node.js agent loop). The proposed architecture says the Box should host the agent runtime, but there are three implementations with no clear winner. |
| C2 | **Dual tool systems** | `core/tools/` uses `@tool` decorator + `ToolDefinition` + `ToolRegistry`. `backend/plugins/` uses `Tool` ABC + `ToolResult` + `PluginRegistry`. `apps/web/services/plugins.js` uses JS plugin objects. None interoperate. |
| C3 | **Memory system not shared** | `core/memory/store.py` is SQLite-backed with 4 layers. `backend/main.py` uses in-memory dicts. `apps/web/server.js` uses in-memory state. The proposed architecture requires shared memory (Vector + Structured DB) accessible to both Box and control plane. |
| C4 | **Provider abstraction bypassed** | `core/providers/base.py` defines `ModelProvider` protocol. `backend/models/ollama_client.py` calls Ollama directly, bypassing the abstraction. The proposed architecture requires BYOK provider selection through the Box runtime. |
| C5 | **No execution boundary** | The existing code has no concept of a Box as an isolated execution substrate. All code runs in the same process. The proposed architecture requires a clear execution boundary that can freeze/resume. |
| C6 | **No orchestration layer** | The existing code has no queue/dispatch abstraction. `backend/core/event_bus.py` is an in-process WebSocket broadcast, not a distributed queue. The proposed architecture requires QStash (or equivalent) for async dispatch. |
| C7 | **No secret management** | `core/foundation/bootstrap.py` reads API keys from environment variables directly. The proposed architecture requires secrets as references resolved at LLM-call time, not `.env` files in the Box FS. |

---

## 3. Phase 2 — Architecture Decision Critique

### 3.1 What Is Correct

1. **Separation of control plane and execution substrate.** The Mayor should
   not be the worker. Intelligence scales with BYOK provider choice, not the
   bootstrap tool's model. This is the core insight of ADR-001 and is correct.

2. **Kilo as bootstrap-only.** Kilo should provision the Box and then hand off.
   It should not become a permanent dependency per task. This prevents the
   scaling ceiling described in ADR-001.

3. **Secrets as references, not files.** Storing secrets as handles resolved at
   call time (not `.env` files in the Box FS) follows security best practices
   and Upstash's agent-workflow guidance.

4. **Upstash as implementation, not architecture.** Abstracting Upstash
   behind interfaces prevents vendor lock-in and allows replacement.

5. **Box freeze/resume.** The ability to freeze an idle Box and resume with
   state intact is a key efficiency feature for an agent OS.

### 3.2 What Is Unnecessary

1. **Naming QStash and Upstash Box in the architecture.** The proposed
   architecture names specific Upstash products. While these are the
   reference implementations, the architecture should be defined by interfaces,
   not vendor names. The ADR should state "QueueProvider (reference: QStash)"
   and "BoxRuntime (reference: Upstash Box)".

2. **Kilo as a separate agent process.** Kilo's bootstrap responsibilities
   (install deps, configure runtime, install skills) could be implemented as
   a function within the BoxRuntime's `configure()` method. A separate Kilo
   agent adds operational complexity without clear benefit unless Kilo also
   performs cross-Box coordination.

3. **Vector + Structured DB as separate memory systems.** For Phase 1, a
   single SQLite store can serve both structured state and vector embeddings
   (via a simple cosine similarity query). Splitting them adds complexity
   without immediate benefit. The split should be deferred to Phase 2 when
   vector search performance becomes a bottleneck.

### 3.3 What Is Missing

1. **VectorProvider interface.** No abstraction for vector similarity search.
   The existing code has no vector store at all.

2. **SecretProvider interface.** No abstraction for secret management. API
   keys are read from environment variables directly.

3. **QueueProvider interface.** No abstraction for async task dispatch. The
   existing event bus is in-process only.

4. **BoxRuntime interface.** No abstraction for the execution substrate.
   No concept of Box creation, freeze, resume, or destroy.

5. **Mayor control plane.** No agent or service that coordinates Boxes,
   selects sizes, or dispatches tasks.

6. **Box sizing policy.** No deterministic policy for selecting Box sizes.

7. **Box lifecycle management.** No lifecycle stages or state transitions.

8. **Handoff contract.** No defined contract for how Kilo hands off to the
   running Box.

### 3.4 Single Points of Failure

| SPOF | Risk | Mitigation |
|------|------|------------|
| QStash availability | If QStash is down, no tasks can be dispatched to Boxes. | Implement a fallback queue (e.g., local Redis) or direct Box API calls. |
| Box freeze/resume integrity | If a Box fails to freeze or resume, state could be lost or corrupted. | Persist state to external storage before freeze; verify integrity on resume. |
| Secret resolver availability | If the secret resolver is down, LLM calls cannot be made. | Cache resolved secrets with TTL; allow offline mode with cached secrets. |
| Vector DB availability | If the vector DB is down, memory retrieval fails. | Fall back to structured DB only; degrade gracefully. |
| Structured DB availability | If the structured DB is down, state persistence fails. | Use WAL mode; replicate to secondary store. |
| Mayor availability | If the Mayor is down, no new tasks can be dispatched. | Run Mayor in HA mode; queue tasks in QStash for later pickup. |

### 3.5 Vendor Lock-in Analysis

| Component | Lock-in Risk | Mitigation |
|-----------|-------------|------------|
| Upstash Box | High — Box lifecycle APIs are Upstash-specific. | Abstract behind `BoxRuntime` interface. |
| QStash | High — Queue APIs are Upstash-specific. | Abstract behind `QueueProvider` interface. |
| Upstash Vector | Medium — Vector DB APIs are Upstash-specific. | Abstract behind `VectorProvider` interface. |
| Upstash Secrets | Medium — Secret store APIs are Upstash-specific. | Abstract behind `SecretProvider` interface. |
| LLM Provider | Low — already abstracted via `ModelProvider`. | Extend to `LLMProvider` with secret resolution. |

### 3.6 What Should Be Implemented Now vs Later

**Phase 1 (now):**
- `AgentRuntime` interface (refactor existing `core/runtime/`)
- `LLMProvider` interface (rename existing `ModelProvider`, add secret resolution)
- `MemoryProvider` interface (refactor existing `core/memory/store.py`)
- `SecretProvider` interface (new, minimal — env var + handle resolution)
- `BoxRuntime` interface (new, minimal — create/configure/execute/destroy)
- `QueueProvider` interface (new, minimal — enqueue/dequeue/ack)

**Phase 2+ (later):**
- `VectorProvider` interface and implementation
- Full Box lifecycle (freeze/resume/persist)
- Box sizing policy
- Mayor control plane
- Kilo bootstrap agent
- Multi-Box orchestration

---

## 4. Phase 3 — Provider-Agnostic Interfaces

All interfaces use Python `Protocol` (structural typing) to avoid import
coupling. Implementations are registered via a factory pattern, not direct
imports at the runtime layer.

### 4.1 Data Structures

```python
@dataclass
class Goal:
    """A goal to execute, decomposable into sub-goals."""
    id: str
    statement: str
    success_criteria: list[str]
    parent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class Step:
    """A single step in a plan."""
    id: str
    description: str
    tool: str | None          # None = reasoning-only step
    input_schema: dict[str, Any]
    expected_output: dict[str, Any] | None
    approval_required: bool = False

@dataclass
class BoxSize:
    """Box resource specification."""
    cpu: int                  # vCPUs
    memory_gb: int            # RAM in GB
    disk_gb: int              # Disk in GB

@dataclass
class BoxSpec:
    """Specification for creating a Box."""
    size: BoxSize
    image: str                # Runtime image (e.g., "python:3.11-slim")
    env: dict[str, str]       # Environment variables (non-secret)
    volumes: list[str]        # Volume mount specs
    network_mode: str         # "bridge" | "host" | "none"
    security_profile: str     # "standard" | "isolated" | "privileged"

@dataclass
class BoxHandle:
    """Handle for an existing Box."""
    box_id: str
    status: str               # "created" | "running" | "frozen" | "destroyed"
    endpoint: str             # API endpoint URL
    created_at: str

@dataclass
class TaskSpec:
    """Specification for a task to execute in a Box."""
    task_id: str
    goal: Goal
    llm_provider: str         # Provider name (e.g., "openai_compat")
    llm_config: dict[str, Any]  # Provider config (model, base_url, etc.)
    tool_names: list[str]     # Tools to enable
    memory_ref: str           # Memory namespace reference
    repo_ref: str | None      # Repository reference (URL + branch)
    timeout_seconds: int
    max_iterations: int
    max_tokens: int

@dataclass
class SecretRef:
    """Reference to a secret, resolved at call time."""
    name: str
    version: str | None = None

@dataclass
class MemoryRef:
    """Reference to a memory namespace."""
    provider: str             # "sqlite" | "postgres" | etc.
    namespace: str            # Namespace for this task's memory
    connection_ref: SecretRef | None  # Connection string (if needed)

@dataclass
class VerificationResult:
    """Result of verifying a task execution."""
    success: bool
    evidence: list[str]       # Paths to evidence files
    metrics: dict[str, Any]   # Performance metrics
    errors: list[str]         # Any errors encountered
```

### 4.2 AgentRuntime Interface

The agent execution loop (Planner → Actor → Observer). Runs inside a Box.
This is the refactored `core/runtime/agent.py` + `thinkbox.py` + `planner.py`
+ `actor.py` + `observer.py`.

```python
class AgentRuntime(Protocol):
    """The agent execution loop: Planner → Actor → Observer.

    Lives inside a Box. Does not know about Boxes, queues, or the Mayor.
    Depends only on: LLMProvider, MemoryProvider, StructuredStateStore,
    ToolRegistry, and governance components.
    """

    async def initialize(self, config: RuntimeConfig) -> None:
        """Initialize the runtime: load tools, set up memory, configure provider."""
        ...

    async def execute_goal(
        self,
        goal: Goal,
        context: ExecutionContext,
    ) -> GoalResult:
        """Execute a goal through the Think Box lifecycle.

        Creates a Think Box, runs the Planner → Actor → Observer loop,
        records outcomes in memory, and returns the result.
        """
        ...

    async def execute_step(
        self,
        step: Step,
        think_box: ThinkBox,
        context: ExecutionContext,
    ) -> StepResult:
        """Execute a single step: check permissions, call tool, record result."""
        ...

    async def shutdown(self) -> None:
        """Flush memory, close connections, persist state."""
        ...
```

**Responsibilities:**
- Decompose goals into steps (Planner)
- Execute steps using tools (Actor)
- Validate results against success criteria (Observer)
- Record outcomes in memory
- Handle replanning on failure
- Enforce iteration/token budgets

**Dependencies (injected, not imported):**
- `LLMProvider` — for model calls
- `MemoryProvider` — for memory persistence
- `StructuredStateStore` — for task/goal state
- `ToolRegistry` — for tool lookup and execution
- `ApprovalGate` — for permission checks
- `AuditLog` — for audit logging

### 4.3 BoxRuntime Interface

The execution substrate that hosts the AgentRuntime. Abstraction for Upstash
Box (or any container/VM-based execution environment).

```python
class BoxRuntime(Protocol):
    """The execution substrate that hosts the AgentRuntime.

    Manages the lifecycle of isolated execution environments (Boxes).
    Each Box runs an AgentRuntime instance.
    """

    async def create(self, spec: BoxSpec) -> BoxHandle:
        """Create a new Box with the given specification."""
        ...

    async def configure(
        self,
        handle: BoxHandle,
        config: BoxConfig,
    ) -> None:
        """Configure the Box: install deps, install skills, configure MCP.

        This is where Kilo's bootstrap responsibilities are invoked.
        """
        ...

    async def attach_memory(
        self,
        handle: BoxHandle,
        memory_ref: MemoryRef,
    ) -> None:
        """Attach a memory reference to the Box."""
        ...

    async def attach_repository(
        self,
        handle: BoxHandle,
        repo_url: str,
        branch: str,
    ) -> None:
        """Clone or mount a repository into the Box."""
        ...

    async def execute(
        self,
        handle: BoxHandle,
        task: TaskSpec,
    ) -> TaskHandle:
        """Start task execution inside the Box. Returns immediately with a handle."""
        ...

    async def get_status(
        self,
        handle: BoxHandle,
        task: TaskHandle,
    ) -> TaskStatus:
        """Poll the status of a running task."""
        ...

    async def get_result(
        self,
        handle: BoxHandle,
        task: TaskHandle,
    ) -> TaskResult:
        """Retrieve the result of a completed task."""
        ...

    async def verify(
        self,
        handle: BoxHandle,
        task: TaskHandle,
    ) -> VerificationResult:
        """Verify the result of a task execution against success criteria."""
        ...

    async def persist(self, handle: BoxHandle) -> SnapshotRef:
        """Persist Box state to durable external storage."""
        ...

    async def freeze(self, handle: BoxHandle) -> None:
        """Suspend the Box. State is preserved in external storage."""
        ...

    async def resume(self, handle: BoxHandle) -> None:
        """Resume a frozen Box from persisted state."""
        ...

    async def destroy(self, handle: BoxHandle) -> None:
        """Destroy the Box and release all resources."""
        ...
```

**Responsibilities:**
- Create/destroy isolated execution environments
- Configure environments (deps, skills, MCP, repos)
- Attach memory and repository references
- Start/stop task execution
- Freeze/resume with state preservation
- Persist state to external storage

### 4.4 QueueProvider Interface

Abstraction for async task dispatch. Reference implementation: QStash.

```python
class QueueProvider(Protocol):
    """Abstraction for async task dispatch (QStash, SQS, etc.).

    The Mayor uses this to dispatch tasks to Boxes. Boxes use this
    to report results back to the Mayor.
    """

    async def enqueue(
        self,
        queue_name: str,
        message: QueueMessage,
        delay_seconds: int = 0,
    ) -> MessageId:
        """Enqueue a message to a named queue."""
        ...

    async def dequeue(
        self,
        queue_name: str,
        max_count: int = 1,
        timeout_seconds: int = 30,
    ) -> list[QueueMessage]:
        """Dequeue messages from a queue. Blocks up to timeout_seconds."""
        ...

    async def ack(
        self,
        queue_name: str,
        message_id: MessageId,
    ) -> None:
        """Acknowledge a message as successfully processed."""
        ...

    async def nack(
        self,
        queue_name: str,
        message_id: MessageId,
        retry: bool = True,
    ) -> None:
        """Reject a message. If retry=True, requeue for another attempt."""
        ...

    async def schedule(
        self,
        queue_name: str,
        message: QueueMessage,
        run_at: datetime,
    ) -> ScheduleId:
        """Schedule a message for future delivery."""
        ...

    async def create_queue(
        self,
        queue_name: str,
        config: QueueConfig,
    ) -> None:
        """Create a new queue with the given configuration."""
        ...

    async def delete_queue(self, queue_name: str) -> None:
        """Delete a queue and all its messages."""
        ...
```

**Responsibilities:**
- Enqueue/dequeue messages to named queues
- Acknowledge/nack messages
- Schedule delayed messages
- Create/delete queues
- Handle retries and dead-letter queues

### 4.5 MemoryProvider Interface

Abstraction for the structured key-value memory store. Reference implementation:
SQLite (`core/memory/store.py`). Future: PostgreSQL, etc.

```python
class MemoryProvider(Protocol):
    """Abstraction for structured memory storage.

    Stores MemoryEntry objects with layer, type, agent/task attribution,
    confidence scores, and metadata. Append-only write policy for
    Organizational and Verified Knowledge layers.
    """

    async def put(self, entry: MemoryEntry) -> None:
        """Store a memory entry. Raises MemoryConflictError on key conflict."""
        ...

    async def get(self, key: str) -> MemoryEntry | None:
        """Retrieve a memory entry by key."""
        ...

    async def delete(self, key: str) -> bool:
        """Delete a memory entry. Returns True if deleted."""
        ...

    async def query(
        self,
        layer: MemoryLayer | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        entry_type: MemoryEntryType | None = None,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        """Query memory entries with optional filters."""
        ...

    async def keys(self, layer: MemoryLayer | None = None) -> list[str]:
        """List all keys, optionally filtered by layer."""
        ...

    async def count(self, layer: MemoryLayer | None = None) -> int:
        """Count entries, optionally filtered by layer."""
        ...

    async def clear_layer(self, layer: MemoryLayer) -> int:
        """Delete all entries in a layer. Returns count deleted."""
        ...

    async def transaction(self) -> AsyncContextManager[Transaction]:
        """Begin a transaction for atomic multi-key operations."""
        ...
```

**Responsibilities:**
- Store/retrieve/delete memory entries
- Query by layer, task, agent, type
- Support transactions for atomic operations
- Enforce append-only policy for Organizational/Verified Knowledge layers

### 4.6 VectorProvider Interface

Abstraction for vector similarity search. Reference implementation: Upstash
Vector. Future: Pinecone, Weaviate, local FAISS.

```python
class VectorProvider(Protocol):
    """Abstraction for vector similarity search.

    Stores vector embeddings with metadata. Used for semantic memory
    retrieval (similarity search over past experiences).
    """

    async def upsert(
        self,
        vectors: list[VectorEntry],
    ) -> int:
        """Insert or update vectors. Returns count upserted."""
        ...

    async def query(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        include_metadata: bool = True,
    ) -> list[VectorMatch]:
        """Query for similar vectors. Returns matches sorted by score."""
        ...

    async def delete(
        self,
        ids: list[str],
        namespace: str | None = None,
    ) -> int:
        """Delete vectors by ID. Returns count deleted."""
        ...

    async def fetch(
        self,
        ids: list[str],
        namespace: str | None = None,
    ) -> list[VectorEntry]:
        """Fetch vectors by ID."""
        ...

    async def list_namespaces(self) -> list[str]:
        """List all available namespaces."""
        ...

    async def delete_namespace(self, namespace: str) -> None:
        """Delete an entire namespace and all its vectors."""
        ...
```

**Responsibilities:**
- Store/retrieve vector embeddings with metadata
- Perform similarity search (top-k nearest neighbors)
- Support namespace isolation
- Support metadata filtering

### 4.7 StructuredStateStore Interface

Abstraction for mutable structured state (task state, goal state, Think Box
state). Distinct from MemoryProvider: this store supports optimistic locking
and mutable updates, while MemoryProvider is append-only for certain layers.

```python
class StructuredStateStore(Protocol):
    """Abstraction for mutable structured state storage.

    Stores task/goal/Think Box state with optimistic locking.
    Unlike MemoryProvider (append-only for some layers), this store
    supports updates and deletes on any key.
    """

    async def put_state(
        self,
        key: str,
        state: dict[str, Any],
        version: int | None = None,
    ) -> int:
        """Store structured state. If version is provided, uses optimistic
        locking (raises StateConflictError if version mismatch).
        Returns the new version number."""
        ...

    async def get_state(self, key: str) -> StateEntry | None:
        """Retrieve structured state by key."""
        ...

    async def update_state(
        self,
        key: str,
        patch: dict[str, Any],
        version: int | None = None,
    ) -> int:
        """Apply a patch to structured state. Returns new version number."""
        ...

    async def delete_state(self, key: str) -> bool:
        """Delete structured state. Returns True if deleted."""
        ...

    async def query_state(
        self,
        prefix: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[StateEntry]:
        """Query structured state with optional prefix and filters."""
        ...
```

**Responsibilities:**
- Store/retrieve/update/delete mutable state
- Support optimistic locking via version numbers
- Support prefix-based queries
- Support metadata filtering

### 4.8 LLMProvider Interface

Abstraction for LLM providers. This is the renamed/extended `ModelProvider`
protocol from `core/providers/base.py`. Adds secret resolution.

```python
class LLMProvider(Protocol):
    """Abstraction for LLM providers (OpenAI, Anthropic, Ollama, etc.).

    All access goes through this interface. The runtime never imports
    a provider-specific SDK. Secrets are resolved via SecretProvider
    at call time, not stored in the provider config.
    """

    async def complete(
        self,
        messages: list[Message],
        **kwargs: Any,
    ) -> CompletionResponse:
        """Generate a non-streaming completion."""
        ...

    async def stream(
        self,
        messages: list[Message],
        **kwargs: Any,
    ) -> AsyncIterator[Chunk]:
        """Stream a completion token by token."""
        ...

    async def embed(
        self,
        texts: list[str],
        **kwargs: Any,
    ) -> list[list[float]]:
        """Generate embeddings for texts."""
        ...

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Return provider capabilities (streaming, embedding, etc.)."""
        ...

    async def resolve_secret(self, secret_ref: SecretRef) -> str:
        """Resolve a secret reference to its value at call time.

        Delegates to the injected SecretProvider. This ensures
        secrets are never stored in the provider config or Box FS.
        """
        ...
```

**Responsibilities:**
- Generate completions (streaming and non-streaming)
- Generate embeddings
- Declare capabilities
- Resolve secrets at call time (delegated to SecretProvider)

### 4.9 SecretProvider Interface

Abstraction for secret management. Reference implementation: environment
variables + handle resolution. Future: HashiCorp Vault, AWS Secrets Manager,
Upstash Secrets.

```python
class SecretProvider(Protocol):
    """Abstraction for secret management.

    Secrets are stored as references (handles), not values. The
    SecretProvider resolves a reference to its value at call time.
    This ensures secrets never appear in the Box FS, config files,
    or audit logs.
    """

    async def resolve(self, secret_ref: SecretRef) -> str:
        """Resolve a secret reference to its value.

        Raises SecretNotFoundError if the secret does not exist.
        Raises SecretAccessDeniedError if access is denied.
        """
        ...

    async def store(
        self,
        name: str,
        value: str,
        metadata: dict[str, Any] | None = None,
    ) -> SecretRef:
        """Store a secret and return a reference.

        The value is never returned by any method other than resolve().
        """
        ...

    async def delete(self, secret_ref: SecretRef) -> bool:
        """Delete a secret. Returns True if deleted."""
        ...

    async def list_secrets(
        self,
        prefix: str | None = None,
    ) -> list[SecretMetadata]:
        """List available secrets (metadata only, no values)."""
        ...

    async def rotate(
        self,
        secret_ref: SecretRef,
        new_value: str,
    ) -> SecretRef:
        """Rotate a secret to a new value. Returns the new reference."""
        ...
```

**Responsibilities:**
- Resolve secret references to values at call time
- Store/delete/rotate secrets
- List secrets (metadata only)
- Never expose secret values except through `resolve()`

### 4.10 Interface Layer Mapping

The interfaces map to the existing 5-layer architecture as follows:

| Interface | Layer | Existing Code | Status |
|-----------|-------|---------------|--------|
| `AgentRuntime` | Layer 4 | `core/runtime/agent.py` | Refactor needed |
| `ToolRegistry` | Layer 3 | `core/tools/registry.py` | Compatible |
| `ApprovalGate` | Layer 3 | `core/governance/audit.py` | Compatible |
| `AuditLog` | Layer 3 | `core/governance/audit.py` | Compatible |
| `MemoryProvider` | Layer 2 | `core/memory/store.py` | Refactor needed |
| `StructuredStateStore` | Layer 2 | (new) | New |
| `VectorProvider` | Layer 2 | (none) | New |
| `LLMProvider` | Layer 1 | `core/providers/base.py` | Rename + extend |
| `SecretProvider` | Layer 1 | (none) | New |
| `BoxRuntime` | External | (none) | New |
| `QueueProvider` | External | (none) | New |

---

## 5. Phase 4 — Box Sizing Policy

### 5.1 Box Size Definitions

| Size | CPU | Memory | Disk | Use Case |
|------|-----|--------|------|----------|
| SMALL | 2 vCPU | 4 GB | 5 GB | Simple reasoning, read-only tasks, no builds |
| MEDIUM | 4 vCPU | 8 GB | 10 GB | Moderate coding, simple builds, some shell usage |
| LARGE | 8 vCPU | 16 GB | 20 GB | Complex builds, heavy shell usage, parallel tasks |

### 5.2 Scoring Model

The Mayor evaluates each task against 12 factors. Each factor is scored
0–5 (0 = minimal, 5 = maximal). The total score determines the Box size.

| Factor | Weight | Score 0–1 (Small) | Score 2–3 (Medium) | Score 4–5 (Large) |
|--------|--------|-------------------|---------------------|-------------------|
| CPU requirement | 10 | 1 core needed | 2–4 cores needed | 5+ cores needed |
| Memory requirement | 10 | < 2 GB needed | 2–8 GB needed | 8+ GB needed |
| Repo size | 8 | < 100 MB | 100 MB – 1 GB | > 1 GB |
| Context size | 8 | < 8K tokens | 8K – 32K tokens | > 32K tokens |
| Tool intensity | 7 | 1–2 tools | 3–5 tools | 6+ tools |
| Shell usage | 7 | None/minimal | Some shell commands | Heavy shell usage |
| Parallelism | 6 | Sequential | 2–4 parallel | 5+ parallel |
| Expected duration | 6 | < 5 min | 5–30 min | > 30 min |
| Model workload | 6 | Light (small model) | Moderate (medium model) | Heavy (large model) |
| Build requirements | 6 | None | Simple build | Complex build |
| Network activity | 5 | None | Moderate | Heavy |
| Security/isolation | 5 | Low | Medium | High |

**Score thresholds:**
- **0–20 points:** SMALL
- **21–40 points:** MEDIUM
- **41–60 points:** LARGE

### 5.3 Output Format

For each task, the Mayor produces:

```
Recommended Box: MEDIUM (4 CPU / 8 GB / 10 GB)
Reason: Repo size > 100MB (score 3), build requirements present (score 3),
        expected duration 15 min (score 3), tool intensity 4 tools (score 3)
Confidence: 85%
Expected Resource Usage: 4 CPU, 6 GB RAM, 8 GB disk
```

### 5.4 Over-Provisioning Rules

Deliberately over-provision by one tier when:

1. **Security/isolation score ≥ 4** — Isolated execution requires headroom
   for security tooling overhead.
2. **Expected duration > 20 min** — Long-running tasks benefit from extra
   memory for context accumulation.
3. **Build requirements score ≥ 4** — Complex builds may have unpredictable
   memory spikes during compilation.
4. **First execution of a new task type** — Unknown resource patterns warrant
   a safety margin.
5. **User explicitly requests "high priority"** — Over-provision to minimize
   latency.

### 5.5 Sizing Example

Task: "Refactor the authentication module in a 500MB repo, run tests, and
commit changes."

| Factor | Score | Weight | Weighted |
|--------|-------|--------|----------|
| CPU requirement | 2 | 10 | 20 |
| Memory requirement | 2 | 10 | 20 |
| Repo size | 3 | 8 | 24 |
| Context size | 2 | 8 | 16 |
| Tool intensity | 3 | 7 | 21 |
| Shell usage | 3 | 7 | 21 |
| Parallelism | 1 | 6 | 6 |
| Expected duration | 3 | 6 | 18 |
| Model workload | 2 | 6 | 12 |
| Build requirements | 3 | 6 | 18 |
| Network activity | 1 | 5 | 5 |
| Security/isolation | 2 | 5 | 10 |
| **Total** | | | **181** |

Wait — the weighted score exceeds 60. Let me recalculate. The scoring model
should use the raw score (0–5) multiplied by weight, then normalized.

Actually, the correct interpretation is: each factor gets a raw score 0–5,
multiplied by its weight. The maximum possible weighted score is
5 × (10+10+8+8+7+7+6+6+6+6+5+5) = 5 × 78 = 390.

Revised thresholds (normalized to 0–390):
- **0–130:** SMALL
- **131–260:** MEDIUM
- **261–390:** LARGE

Recalculating the example: total weighted = 181 → **SMALL**.

But build requirements score 3 and expected duration 15 min triggers
over-provisioning rule #2 → **MEDIUM**.

```
Recommended Box: MEDIUM (4 CPU / 8 GB / 10 GB)
Reason: Base score 181/390 (SMALL), but over-provisioned due to
        expected duration > 20 min (rule: over-provision by one tier)
Confidence: 80%
Expected Resource Usage: 4 CPU, 6 GB RAM, 8 GB disk
```

---

## 6. Phase 5 — Box Lifecycle

### 6.1 Lifecycle Stages

```
CREATE → BOOTSTRAP → CONFIGURE → ATTACH_MEMORY → ATTACH_REPOSITORY
    → EXECUTE → VERIFY → PERSIST → [FREEZE → RESUME]* → DESTROY
```

| Stage | Mandatory | Reversible | Dangerous | Description |
|-------|-----------|------------|-----------|-------------|
| CREATE | Yes | No | No | Allocate Box resources (CPU, memory, disk). |
| BOOTSTRAP | Yes | No | No | Install base dependencies (Python, pip, git). |
| CONFIGURE | Yes | No | No | Install project deps, skills, MCP servers. |
| ATTACH_MEMORY | Yes | Yes | No | Mount/connect memory namespace. |
| ATTACH_REPOSITORY | No | Yes | No | Clone/mount repository into Box. |
| EXECUTE | Yes | No | No | Start AgentRuntime with task spec. |
| VERIFY | Yes | No | No | Validate results against success criteria. |
| PERSIST | Yes | No | No | Save state to external durable storage. |
| FREEZE | No | Yes | No | Suspend Box, preserve state externally. |
| RESUME | No | Yes | No | Restore Box from persisted state. |
| DESTROY | Yes (terminal) | No | Yes | Release all resources, delete Box FS. |

### 6.2 State That Survives Freezing

When a Box is frozen, the following state is persisted to external storage
and survives the freeze:

1. **File system state** — All files created/modified during execution.
2. **Installed dependencies** — Python packages, npm packages, system packages.
3. **Configured runtime** — Python environment, PATH, environment variables.
4. **Installed skills** — Skill definitions and configurations.
5. **MCP server connections** — MCP server configurations and connection state.
6. **Attached memory reference** — The memory namespace reference (not the
   data itself, which lives in the external memory store).
7. **Attached repository state** — Git checkout state, uncommitted changes.
8. **Task execution state** — Current Think Box state, step progress, memory
   snapshots, budget consumption.
9. **Tool registry state** — Registered tools and their configurations.

### 6.3 State That Must Be Stored Outside the Box

The following state must **never** be stored inside the Box filesystem. It
must live in external, durable, access-controlled storage:

1. **Secrets** — API keys, tokens, passwords. Stored as references in the
   Box; resolved at call time by the `SecretProvider`.
2. **Authoritative memory** — The source of truth for Session, Task,
   Organizational, and Verified Knowledge memory. Stored in the
   `MemoryProvider` (external SQLite/PostgreSQL).
3. **Vector embeddings** — Semantic memory embeddings. Stored in the
   `VectorProvider` (external vector DB).
4. **Structured state** — Task/goal/Think Box state. Stored in the
   `StructuredStateStore` (external database).
5. **Audit logs** — Append-only, tamper-evident logs. Stored externally
   with hash chaining.
6. **Benchmark results** — Performance measurements. Stored in
   Organizational Memory.
7. **Box metadata** — Box ID, size, creation time, lifecycle state. Stored
   in the Mayor's state store.

### 6.4 Freeze/Resume Integrity

- **Before freeze:** The Box must flush all in-memory state to external
  storage. The `AgentRuntime.shutdown()` method is called, which flushes
  memory, closes connections, and persists state.
- **During freeze:** The Box is suspended. No execution occurs. State is
  preserved in external storage.
- **On resume:** The Box is restored from external storage. The
  `AgentRuntime.initialize()` method is called, which reloads memory,
  reconnects to providers, and restores the Think Box state.
- **Integrity check:** On resume, the Box verifies that the persisted state
  matches the external storage. If corruption is detected, the Box is
  destroyed and a new one is created.

### 6.5 Destroy

- **Before destroy:** The Box must persist all state to external storage.
  The `PERSIST` stage is called.
- **During destroy:** The Box filesystem is deleted. All resources (CPU,
  memory, disk) are released.
- **After destroy:** The Box handle is invalidated. Any attempt to use it
  raises `BoxDestroyedError`.

---

## 7. Phase 6 — Kilo Bootstrap Role

### 7.1 Kilo's Responsibilities (MAY)

Kilo is the **provisioning agent**. It runs once per Box, during the
`BOOTSTRAP` and `CONFIGURE` lifecycle stages. After configuration is
complete, Kilo hands off to the `AgentRuntime` inside the Box.

Kilo MAY:

1. **Initialize Box** — Create the Box instance, allocate resources, set up
   the base runtime image.
2. **Install dependencies** — Run `pip install`, `npm install`, `apt-get
   install`, etc. based on the project's dependency files.
3. **Configure runtime** — Set up Python virtual environment, configure
   PATH, set non-secret environment variables.
4. **Install skills** — Copy skill definitions into the Box, register them
   with the ToolRegistry.
5. **Configure MCP** — Set up MCP server connections, install MCP clients.
6. **Connect repositories** — Clone or mount the project repository into
   the Box.
7. **Environment checks** — Verify Python version, disk space, network
   connectivity, required tools are available.

### 7.2 Kilo's Hard Limits (MUST NOT)

Kilo MUST NOT:

1. **Become the permanent Mayor.** Kilo is not the control plane. The Mayor
   makes decisions about what to execute, which Box size to use, and which
   LLM provider to use. Kilo only provisions.
2. **Become the permanent worker.** Kilo is not the agent that executes
   tasks. The `AgentRuntime` inside the Box is the worker. Kilo's job ends
   after configuration.
3. **Become the secret store.** Kilo must not store, manage, or resolve
   secrets. Secrets are handled by the `SecretProvider` and resolved at
   LLM-call time inside the Box.
4. **Make task-level decisions.** Kilo does not decide which tools to use,
   which steps to plan, or how to validate results. That is the
   `AgentRuntime`'s job.
5. **Persist task state.** Kilo does not write to the memory store or
   structured state store. It only configures the Box to be able to access
   them.

### 7.3 Handoff Contract

The handoff from Kilo to the running Box follows this contract:

```
1. Mayor → QueueProvider: enqueue task spec
2. BoxRuntime: CREATE Box with spec
3. Kilo (inside Box): BOOTSTRAP
   a. Install base dependencies
   b. Configure runtime environment
4. Kilo (inside Box): CONFIGURE
   a. Install project dependencies
   b. Install skills
   c. Configure MCP servers
   d. Connect repository
   e. Run environment checks
5. Kilo (inside Box): ATTACH_MEMORY
   a. Connect to MemoryProvider (external)
   b. Connect to VectorProvider (external)
   c. Connect to StructuredStateStore (external)
   d. Connect to SecretProvider (external)
6. Kilo (inside Box): ATTACH_REPOSITORY
   a. Clone/mount repository
7. Kilo → BoxRuntime: signal "configuration complete"
8. BoxRuntime: EXECUTE
   a. Start AgentRuntime with task spec
   b. AgentRuntime takes over: Planner → Actor → Observer loop
9. Kilo: exits (no longer involved)
10. AgentRuntime: runs until completion or timeout
11. BoxRuntime: VERIFY → PERSIST → FREEZE or DESTROY
```

**Key invariant:** After step 9, Kilo is no longer running. The Box is
self-contained. If the Box needs to re-bootstrap (e.g., after a resume),
it uses the persisted configuration, not Kilo.

### 7.4 Kilo Implementation Notes

- Kilo should be implemented as a lightweight agent that runs inside the Box
  during the BOOTSTRAP and CONFIGURE stages.
- Kilo should use the `BoxRuntime` interface to interact with the Box
  infrastructure.
- Kilo should use the `SecretProvider` interface to resolve any secrets
  needed for configuration (e.g., repository access tokens).
- Kilo should log all actions to the audit log.
- Kilo should fail fast if environment checks fail.

---

## 8. Reconciliation with Existing 5-Layer Architecture

### 8.1 Mapping

The existing 5-layer architecture (Layers 0–4) defines the **internal code
structure** of the Box. The Upstash architecture defines the **external
deployment/runtime structure**. They are orthogonal and complementary:

```
┌─────────────────────────────────────────────────────────┐
│  EXTERNAL (outside Box)                                 │
│  Mayor (control plane)                                  │
│  QStash (QueueProvider)                                 │
│  Kilo (bootstrap agent)                                 │
│  Memory: Vector + Structured DB (MemoryProvider,        │
│    VectorProvider, StructuredStateStore)                │
├─────────────────────────────────────────────────────────┤
│  INTERNAL (inside Box)                                  │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Layer 4 — Agent Runtime (AgentRuntime)           │  │
│  │  Layer 3 — Tool Registry & Governance             │  │
│  │  Layer 2 — Memory Subsystem                       │  │
│  │  Layer 1 — Provider Abstraction (LLMProvider)     │  │
│  │  Layer 0 — Foundation                             │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 8.2 Resolving Conflicts

**C1 (Three competing runtimes):** The `backend/main.py` agent loop and
`apps/web/server.js` agent loop should be deprecated. The `core/runtime/`
stack becomes the `AgentRuntime` that runs inside the Box. The FastAPI app
in `backend/main.py` can be repurposed as the Mayor's API surface (HTTP
endpoints for goal submission, status polling, approval handling).

**C2 (Dual tool systems):** The `backend/plugins/` system should be
consolidated into `core/tools/`. The `core/tools/` system already has the
proper `@tool` decorator, `ToolDefinition`, and `ToolRegistry` with
permission levels and approval gates. The `backend/plugins/` system should
be removed or refactored to use `core/tools/`.

**C3 (Memory not shared):** The `backend/main.py` in-memory dicts should
be replaced with the `MemoryProvider` interface. The `core/memory/store.py`
SQLite store becomes the reference implementation of `MemoryProvider`.

**C4 (Provider abstraction bypassed):** The `backend/models/ollama_client.py`
should be refactored to use the `LLMProvider` interface. The Ollama client
becomes one implementation of `LLMProvider`, alongside the existing
`OpenAICompatProvider`.

**C5 (No execution boundary):** The `BoxRuntime` interface defines the
execution boundary. The existing code runs everything in-process; the new
architecture isolates execution in Boxes.

**C6 (No orchestration layer):** The `QueueProvider` interface defines the
orchestration layer. The existing `backend/core/event_bus.py` is an
in-process WebSocket broadcast; it should be replaced or augmented with a
`QueueProvider` implementation.

**C7 (No secret management):** The `SecretProvider` interface defines
secret management. The existing `bootstrap.py` reads API keys from
environment variables; this should be refactored to use `SecretProvider`.

### 8.3 Layer Discipline Preservation

The 5-layer dependency rule (Layer N may only import from layers 0–N-1)
is preserved *inside* the Box. The external interfaces (`BoxRuntime`,
`QueueProvider`, `MemoryProvider`, `VectorProvider`, `StructuredStateStore`,
`SecretProvider`) are injected into the Box at configuration time, not
imported. This maintains layer discipline while enabling external
orchestration.

The `AgentRuntime` (Layer 4) depends on:
- `LLMProvider` (Layer 1) — injected
- `MemoryProvider` (Layer 2) — injected
- `StructuredStateStore` (Layer 2) — injected
- `VectorProvider` (Layer 2) — injected
- `SecretProvider` (Layer 1) — injected
- `ToolRegistry` (Layer 3) — internal
- `ApprovalGate` (Layer 3) — internal
- `AuditLog` (Layer 3) — internal

The `BoxRuntime` is external to the 5-layer stack. It creates the Box,
configures it, and starts the `AgentRuntime`. It does not import any layer
directly; it communicates via the `QueueProvider` interface.

---

## 9. Data Flow

```
User Goal
    │
    ▼
Mayor (control plane)
    │
    ├── Evaluate task against Box Sizing Policy → BoxSize
    ├── Select LLM provider (BYOK) → LLMProvider config
    ├── Create TaskSpec (goal, tools, memory_ref, repo_ref, budget)
    │
    ▼
QueueProvider.enqueue("box-tasks", TaskSpec)
    │
    ▼
BoxRuntime (in Box)
    │
    ├── CREATE → BOOTSTRAP → CONFIGURE (Kilo)
    │   ├── Install deps
    │   ├── Install skills
    │   ├── Configure MCP
    │   ├── Connect repo
    │   └── Environment checks
    │
    ├── ATTACH_MEMORY (MemoryProvider + VectorProvider + StructuredStateStore)
    ├── ATTACH_REPOSITORY
    │
    ├── EXECUTE (AgentRuntime)
    │   ├── Planner: decompose Goal → Steps
    │   ├── Actor: for each Step:
    │   │   ├── Check permissions (ToolRegistry + ApprovalGate)
    │   │   ├── Call tool
    │   │   └── Record result (AuditLog + MemoryProvider)
    │   ├── Observer: validate result against expected_output
    │   │   ├── success → continue
    │   │   └── failure → Planner replans
    │   └── Improvement: extract patterns → Organizational Memory
    │
    ├── LLM calls via LLMProvider (secrets resolved via SecretProvider)
    │
    ├── VERIFY: check success criteria
    ├── PERSIST: save state to external storage
    │
    ├── FREEZE (if idle, for potential resume)
    │   or
    ├── DESTROY (if complete)
    │
    ▼
QueueProvider.enqueue("mayor-results", TaskResult)
    │
    ▼
Mayor (receives result, updates state, notifies user)
```

---

## 10. Consequences

### 10.1 What Changes

1. **New interfaces** (`AgentRuntime`, `BoxRuntime`, `QueueProvider`,
   `VectorProvider`, `StructuredStateStore`, `SecretProvider`) must be
   defined before any implementation.
2. **Existing `core/runtime/agent.py`** must be refactored to implement the
   `AgentRuntime` interface.
3. **Existing `core/memory/store.py`** must be refactored to implement the
   `MemoryProvider` interface (async methods).
4. **Existing `core/providers/base.py`** must be renamed to `LLMProvider`
   and extended with `resolve_secret()`.
5. **`backend/main.py`** agent loop must be deprecated; FastAPI app
   repurposed as Mayor API surface.
6. **`backend/plugins/`** must be consolidated into `core/tools/`.
7. **`apps/web/server.js`** must be deprecated; frontend connects to Mayor
   API.
8. **`core/foundation/bootstrap.py`** must be refactored to use
   `SecretProvider` instead of direct env var reads.

### 10.2 What Stays the Same

1. **5-layer code architecture** — preserved inside the Box.
2. **Layer discipline** — Layer N may only import from layers 0–N-1.
3. **Provider independence** — no provider-specific SDK at runtime layer.
4. **Memory-first** — four memory layers (Session, Task, Organizational,
   Verified Knowledge).
5. **Governance by default** — permission checks, audit log, approval gates.
6. **Evidence over assumptions** — benchmark results in Organizational Memory.
7. **Phase boundaries** — Phase 1 scope unchanged (single agent, single
   provider, 5 tools).

### 10.3 Migration Path

1. **Phase 1:** Define interfaces. Refactor `core/runtime/` to implement
   `AgentRuntime`. Refactor `core/memory/store.py` to implement
   `MemoryProvider`. Rename `ModelProvider` to `LLMProvider`. Add
   `SecretProvider` with env-var implementation.
2. **Phase 2:** Add `VectorProvider` interface and SQLite-based implementation.
   Add `StructuredStateStore` interface. Add `QueueProvider` interface with
   in-process implementation.
3. **Phase 3:** Add `BoxRuntime` interface. Implement with Upstash Box as
   reference. Add Mayor control plane. Add Kilo bootstrap agent.
4. **Phase 4:** Deprecate `backend/main.py` agent loop and `apps/web/server.js`.
   Consolidate tool systems. Repurpose FastAPI as Mayor API.

---

## 11. Open Items

| # | Item | Phase |
|---|------|-------|
| O1 | VectorProvider implementation (SQLite-based for Phase 1) | Phase 2 |
| O2 | StructuredStateStore implementation | Phase 2 |
| O3 | QueueProvider implementation (in-process for Phase 1, QStash for Phase 3) | Phase 2 |
| O4 | BoxRuntime implementation (Upstash Box reference) | Phase 3 |
| O5 | Mayor control plane implementation | Phase 3 |
| O6 | Kilo bootstrap agent implementation | Phase 3 |
| O7 | Consolidation of `backend/plugins/` into `core/tools/` | Phase 4 |
| O8 | Deprecation of `backend/main.py` agent loop | Phase 4 |
| O9 | Deprecation of `apps/web/server.js` | Phase 4 |
| O10 | Frontend connection to Mayor API | Phase 4 |

---

## 12. Summary of Top 3 Conflicts and Top 3 Missing Pieces

### Top 3 Conflicts

1. **Three competing agent runtimes** — `core/runtime/` (proper Think Box
   loop), `backend/main.py` (FastAPI agent loop bypassing core), and
   `apps/web/server.js` (Node.js agent loop). The proposed architecture
   says the Box should host the agent runtime, but there are three
   implementations with no clear winner. Resolution: deprecate
   `backend/main.py` and `apps/web/server.js` agent loops; use
   `core/runtime/` as the `AgentRuntime` inside the Box.

2. **Dual tool systems** — `core/tools/` (decorator-based, with permission
   levels and approval gates) vs. `backend/plugins/` (ABC-based, simpler).
   Neither interoperates with `apps/web/services/plugins.js` (JS).
   Resolution: consolidate into `core/tools/`; remove `backend/plugins/`.

3. **Memory system not shared** — `core/memory/store.py` is SQLite-backed
   with 4 layers, but `backend/main.py` and `apps/web/server.js` use
   in-memory dicts. The proposed architecture requires shared memory
   (Vector + Structured DB) accessible to both Box and control plane.
   Resolution: refactor `core/memory/store.py` to implement
   `MemoryProvider`; replace in-memory dicts in backend with
   `MemoryProvider` calls.

### Top 3 Missing Pieces

1. **VectorProvider interface** — No abstraction for vector similarity
   search exists. The existing code has no vector store at all. The proposed
   architecture mentions "VECTOR + STRUCTURED DATABASE → MEMORY SYSTEM" but
   there is no `VectorProvider` interface or implementation.

2. **SecretProvider interface** — No abstraction for secret management. API
   keys are read from environment variables directly in
   `core/foundation/bootstrap.py`. The proposed architecture requires
   secrets as references resolved at LLM-call time, not `.env` files in the
   Box FS.

3. **BoxRuntime interface** — No abstraction for the execution substrate.
   There is no concept of a Box that can be created, configured, frozen,
   resumed, or destroyed. The existing code runs everything in-process with
   no isolation boundary.
