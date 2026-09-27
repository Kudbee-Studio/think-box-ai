# Memory Layers — Four-Layer Design

## Overview

Think Box AI uses four memory layers instead of chat history. Each layer has distinct scope, lifetime, and write policy.

| Layer | Scope | Lifetime | Access | Policy |
|-------|-------|----------|--------|--------|
| **SESSION** | Single conversation | Duration of session | Unbounded read | Write: agent + task |
| **TASK** | Single task execution | One task | Filtered by task_id | Write: task completion only |
| **ORGANIZATIONAL** | All agents across time | Indefinite | Query-able | Append-only; never overwrite |
| **VERIFIED** | Proven facts only | Indefinite but fades | Confidence score | Write: governance gate + audit |

---

## SESSION Layer

Scratch space for the current agent session. Cleared on session end.

### Use Cases
- Intermediate reasoning steps
- Observations during task execution
- Temporary state that doesn't outlive the session

### Example

```python
from core.memory.store import MemoryStore
from core.memory.schema import MemoryEntry, MemoryLayer, MemoryEntryType

memory = MemoryStore("./data/memory.db")

# Record a reasoning step during inference
memory.put(MemoryEntry(
    key=f"reasoning_{task_id}_step_1",
    layer=MemoryLayer.SESSION,
    entry_type=MemoryEntryType.REASONING_STEP,
    value={
        "prompt": "evaluate trade-offs",
        "options": ["A", "B", "C"],
        "chosen": "B",
        "rationale": "lowest latency"
    },
    agent_id=agent_id,
    task_id=task_id
))

# Later: query all reasoning for this session
reasoning_steps = memory.query(
    layer=MemoryLayer.SESSION,
    entry_type=MemoryEntryType.REASONING_STEP,
    task_id=task_id
)
```

---

## TASK Layer

Bounded scope — records facts about a single task execution. Immutable after task completion.

### Use Cases
- Task inputs and parameters
- Task execution results
- Error conditions specific to one run

### Example

```python
# Record goal state at task start
memory.put(MemoryEntry(
    key=f"goal_{task_id}",
    layer=MemoryLayer.TASK,
    entry_type=MemoryEntryType.GOAL_STATE,
    value={
        "goal": "optimize cache hit rate",
        "input_size": 10000,
        "budget_tokens": 5000
    },
    agent_id=agent_id,
    task_id=task_id
))

# Record result at completion
memory.put(MemoryEntry(
    key=f"result_{task_id}",
    layer=MemoryLayer.TASK,
    entry_type=MemoryEntryType.TOOL_RESULT,
    value={
        "cache_hits": 7234,
        "cache_misses": 2766,
        "hit_rate": 0.723,
        "tokens_used": 4891
    },
    agent_id=agent_id,
    task_id=task_id
))
```

---

## ORGANIZATIONAL Layer

**Append-only.** Records patterns, benchmarks, and lessons learned across all agents and tasks. Never overwrite.

### Use Cases
- Discovered patterns ("if X then usually Y")
- Benchmark results (model performance, latency, cost)
- Lessons from failed tasks
- Generalizable facts about the system

### Key Rule
Every write to ORGANIZATIONAL is a NEW entry. No updates. No deletes. Only appends.

### Example

```python
# Record a discovered pattern (never overwritten)
memory.put(MemoryEntry(
    key=f"pattern_cache_thrashing_{uuid.uuid4().hex[:8]}",
    layer=MemoryLayer.ORGANIZATIONAL,
    entry_type=MemoryEntryType.PATTERN,
    value={
        "pattern": "cache thrashing occurs when working set > memory",
        "condition": "task_type == 'streaming' AND batch_size > threshold",
        "consequence": "latency increases 10x",
        "mitigation": "reduce batch size or increase memory allocation",
        "evidence_count": 47,
        "confidence": 0.94
    },
    agent_id=agent_id,
    task_id=task_id  # Some patterns span multiple tasks
))

# Later: query all patterns about a topic
cache_patterns = memory.query(
    layer=MemoryLayer.ORGANIZATIONAL,
    entry_type=MemoryEntryType.PATTERN,
    limit=20
)
print(f"Found {len(cache_patterns)} cache-related patterns")
```

---

## VERIFIED Layer

Facts with confidence scores. Confidence decays over time. Write-protected by governance gate.

### Use Cases
- Model benchmark results with uncertainty
- External API SLAs (99.9% uptime)
- Hardware specs (GPU memory, CPU cores)
- Regulatory facts (token limits, pricing)

### Example

```python
# Record a verified fact (governance gated)
memory.put(MemoryEntry(
    key="verified_mercury2_latency_p95_sep2026",
    layer=MemoryLayer.VERIFIED,
    entry_type=MemoryEntryType.BENCHMARK,
    value={
        "model": "mercury-2",
        "metric": "latency_p95_ms",
        "value": 847,
        "temperature": 0.1,
        "max_tokens": 4096,
        "sample_size": 1000,
        "measured_date": "2026-09-26"
    },
    agent_id="benchmark_runner",
    task_id="benchmark_mercury2_sep2026",
    metadata={"confidence": 0.95}  # High confidence: large N
))

# Query verified facts with uncertainty threshold
high_confidence_benchmarks = memory.query(
    layer=MemoryLayer.VERIFIED,
    entry_type=MemoryEntryType.BENCHMARK,
    limit=50
)

# Filter by confidence
for entry in high_confidence_benchmarks:
    if entry.confidence >= 0.90:
        print(f"{entry.key}: {entry.value['metric']}={entry.value['value']}")
```

---

## API Reference

### Write (put)

```python
memory.put(MemoryEntry(
    key="unique_identifier",           # Required: globally unique key
    layer=MemoryLayer.SESSION,          # Required: which layer
    entry_type=MemoryEntryType.FACT,   # Required: type of entry
    value={...},                        # Required: JSON-serializable dict
    agent_id="agent_123",               # Optional: which agent
    task_id="task_456",                 # Optional: which task
    metadata={...},                     # Optional: extra fields
    confidence=0.95                     # Optional: [0.0, 1.0]
))
```

### Read (get)

```python
entry = memory.get("unique_identifier")
if entry:
    print(entry.value)
    print(entry.layer)
    print(entry.confidence)
```

### Query

```python
# Query with optional filters
results = memory.query(
    layer=MemoryLayer.ORGANIZATIONAL,      # Optional filter
    task_id="task_456",                    # Optional filter
    agent_id="agent_123",                  # Optional filter
    entry_type=MemoryEntryType.PATTERN,   # Optional filter
    limit=100                              # Max results (default 100)
)

# Results are sorted by creation time (newest first)
for entry in results:
    print(f"{entry.created_at}: {entry.key} = {entry.value}")
```

### Delete

```python
# Delete single entry
deleted = memory.delete("key_to_remove")
print(f"Deleted: {deleted}")

# Clear entire layer (use with caution)
count = memory.clear_layer(MemoryLayer.SESSION)
print(f"Cleared {count} entries from SESSION")
```

### Introspection

```python
# Count entries in a layer
session_count = memory.count(MemoryLayer.SESSION)
org_count = memory.count(MemoryLayer.ORGANIZATIONAL)

# List all keys in a layer
all_keys = memory.keys(MemoryLayer.ORGANIZATIONAL)

# Get a key for a specific task
task_keys = memory.keys(layer=MemoryLayer.TASK)  # All TASK entries
```

---

## Entry Types

Choose the type that best describes your data:

| Type | Use When | Example |
|------|----------|---------|
| `TOOL_CALL` | Calling an external tool | "Called search_web with query='AI trends'" |
| `TOOL_RESULT` | Tool returned a result | "search_web returned 42 results" |
| `REASONING_STEP` | Recording intermediate reasoning | "Considered option A vs B, chose B" |
| `GOAL_STATE` | Recording task goal/objective | "Goal: optimize cache hit rate" |
| `ERROR` | Recording failures/exceptions | "Model timeout after 60s" |
| `PATTERN` | Discovered generalizable pattern | "Cache thrashing happens when..." |
| `FACT` | Static knowledge | "Mercury-2 max context: 32K tokens" |
| `BENCHMARK` | Performance measurement | "Mercury-2 latency: 847ms P95" |

---

## Thread Safety

`MemoryStore` is thread-safe:
- Uses SQLite with WAL mode
- Locks protect schema mutations
- Multiple readers concurrent; writers serialized
- Safe for concurrent agents

```python
# Safe to use from multiple threads
import threading

memory = MemoryStore("./data/memory.db")

def worker(agent_id, task_id):
    for i in range(10):
        memory.put(MemoryEntry(
            key=f"work_{agent_id}_{i}",
            layer=MemoryLayer.SESSION,
            entry_type=MemoryEntryType.REASONING_STEP,
            value={"step": i},
            agent_id=agent_id,
            task_id=task_id
        ))

threads = [
    threading.Thread(target=worker, args=(f"agent_{j}", f"task_{j}"))
    for j in range(5)
]

for t in threads:
    t.start()
    t.join()

print(f"Total entries: {memory.count()}")  # Safe to read while others write
```

---

## Organizational Memory Best Practices

1. **Use UUIDs for patterns** — Never overwrite. Generate unique keys:
   ```python
   import uuid
   key = f"pattern_cache_{uuid.uuid4().hex[:8]}"
   ```

2. **Include evidence count** — Patterns with more evidence are stronger:
   ```python
   "evidence_count": 47,  # Observed this pattern 47 times
   "confidence": 0.94
   ```

3. **Document mitigation** — Don't just record problems:
   ```python
   "pattern": "cache thrashing",
   "mitigation": "reduce batch size or increase memory"
   ```

4. **Timestamp findings** — Benchmark results age:
   ```python
   "measured_date": "2026-09-26",
   "confidence": 0.95  # High for recent data, lower for stale
   ```

5. **Link back to tasks** — Enable tracing:
   ```python
   "agent_id": agent_id,
   "task_id": task_id  # Which task discovered this?
   ```

---

## Committed Memory Seeds (rehydrate on any machine)

The SQLite memory store (`data/thinkboxmd/db/memory_layers.db`) is gitignored
and local to one machine. What makes lessons outlive a machine or a session
is two committed tables in `thinkbox/memory_layers.py`, loaded by
`ingest_markdown()`:

| Seed | Layer | Written when |
|------|-------|--------------|
| `CHRONICLE_PATTERNS` | Organizational | every listed evidence file exists |
| `CHRONICLE_FACTS` | Verified Knowledge | every evidence file exists **and** each JSON artifact still carries the `proof_hash` the fact was recorded against |

The proof-hash rule fails closed: if an artifact changes, ingest raises
`MemoryLayerError("fact_evidence_mismatch")` instead of quietly keeping or
dropping the fact. Update the fact deliberately, or don't claim it.

```bash
python3 scripts/ingest_memory_layers.py \
  --session-id <session> --task-id <task> --agent-id <agent>
# markdown_files=… patterns=12 … organizational=12 verified=4 live_verified=False
```

Two tests keep the seeds honest against the real repository:
`TestRepoChronicle.test_all_chronicle_patterns_have_evidence_in_repo` and
`test_all_chronicle_facts_verify_in_repo`. A seed whose evidence goes missing
fails CI instead of silently disappearing from memory.

**Adding a lesson:** add a `(pattern_id, description, evidence_paths)` row to
`CHRONICLE_PATTERNS`, citing the committed files that prove it. **Adding a
fact:** add an entry to `CHRONICLE_FACTS` with `fact`, `how`, `evidence`,
`confidence`, and `proof_hash` when the evidence is a proof artifact. Nothing
seeded may set `live_verified: true`.

