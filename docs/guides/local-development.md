# Local Development — Autonomous Workflow

## Quick Start (5 minutes)

Clone the repo and run the proof:

```bash
git clone https://github.com/Kudbee-Studio/think-box-ai.git
cd think-box-ai

# Set up environment (copy from your phone/cloud session)
export INCEPTION_API_KEY=sk_xxxxxxx
export UPSTASH_REDIS_REST_URL=https://...
export UPSTASH_REDIS_REST_TOKEN=...

# Run proof script
python3 scripts/prove_autonomous_workflow.py
```

**Expected output:** 4/4 PASS
- ✅ Model execution (Mercury-2)
- ✅ Redis persistence
- ✅ Autonomous loop (Sense→Decide→Act→Learn)
- ✅ Dashboard state tracking

---

## Full Setup

### Prerequisites

- Python 3.10+
- Git
- Virtual environment (optional but recommended)

### 1. Clone & Environment

```bash
git clone https://github.com/Kudbee-Studio/think-box-ai.git
cd think-box-ai

# Optional: create virtual environment
python3 -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate (Windows)
```

### 2. Environment Variables

Copy from your cloud session:

```bash
# Model execution
export THINKBOX_DEFAULT_PROVIDER=inception
export INCEPTION_API_KEY=sk_xxxxxxx

# Persistence
export UPSTASH_REDIS_REST_URL=https://certain-mongrel-303351.upstash.io
export UPSTASH_REDIS_REST_TOKEN=gQAAAA...

# Memory storage (optional, defaults to ./data/memory.db)
export THINKBOX_MEMORY_DB_PATH=./data/memory.db
```

Verify setup:

```bash
python3 docs/guides/environment-variables.md  # See verification commands
```

### 3. Proof Script

The proof script validates all cloud components work locally:

```bash
python3 scripts/prove_autonomous_workflow.py
```

This tests:
1. **Model execution** — real Mercury-2 API call to Inception
2. **Redis persistence** — write/read via Upstash REST API
3. **Autonomous loop** — full Sense→Decide→Act→Learn cycle
4. **Dashboard state** — event tracking and categorization

---

## Development Workflow

### Run Tests

```bash
# Full test suite
python3 -m unittest discover tests/ -v

# Specific module
python3 -m unittest tests.unit.test_autonomous_loop_dashboard -v

# Proof script (integrationish)
python3 scripts/prove_autonomous_workflow.py
```

### Memory Layer Usage

Working with the four memory layers:

```python
from core.memory.store import MemoryStore
from core.memory.schema import MemoryEntry, MemoryLayer, MemoryEntryType

# Initialize store
memory = MemoryStore("./data/memory.db")

# Store a reasoning step (SESSION layer)
memory.put(MemoryEntry(
    key="my_reasoning_001",
    layer=MemoryLayer.SESSION,
    entry_type=MemoryEntryType.REASONING_STEP,
    value={"step": "evaluate options", "choice": "option_b"},
    agent_id="agent_123",
    task_id="task_456"
))

# Query organizational patterns
patterns = memory.query(
    layer=MemoryLayer.ORGANIZATIONAL,
    entry_type=MemoryEntryType.PATTERN,
    limit=10
)

# List all keys in a layer
session_keys = memory.keys(layer=MemoryLayer.SESSION)
```

### Model Execution

Testing model execution locally:

```python
import asyncio
from thinkbox.model_client import AsyncModelClient, ModelConfig

async def test_model():
    config = ModelConfig.from_env()
    client = AsyncModelClient(config)
    
    try:
        response = await client.generate(
            "Return only a JSON object: {\"status\": \"ok\"}"
        )
        print(f"Model response: {response}")
    finally:
        await client.close()

asyncio.run(test_model())
```

### Dashboard State

Track events in the autonomous workflow:

```python
import asyncio
from thinkbox.dashboard_state import DashboardState, DashboardCategory, DashboardEvent

async def track_event():
    state = DashboardState()
    
    await state.emit(
        category=DashboardCategory.AUTONOMOUS_LOOP,
        event_type=DashboardEvent.LOOP_STARTED,
        data={"loop_id": "my_loop_001"},
        evidence_label="verified"
    )
    
    # Get current state summary
    summary = state.get_state_summary()
    print(f"Dashboard: {summary}")

asyncio.run(track_event())
```

---

## Troubleshooting

### "INCEPTION_API_KEY not configured"

```bash
# Check if environment variable is set
echo $INCEPTION_API_KEY

# Re-export if needed
export INCEPTION_API_KEY=sk_xxxxxxx

# Verify it's in the environment
python3 -c "import os; print('Set' if os.getenv('INCEPTION_API_KEY') else 'Not set')"
```

### "Redis connection refused"

```bash
# Check Upstash credentials
curl -H "Authorization: Bearer $UPSTASH_REDIS_REST_TOKEN" \
  "$UPSTASH_REDIS_REST_URL/ping"

# Should return: "PONG"
```

### Memory DB file permission error

```bash
# Ensure data directory exists and is writable
mkdir -p ./data
chmod 755 ./data

# Or set explicit path
export THINKBOX_MEMORY_DB_PATH=/tmp/memory.db
```

### Model returns empty response

Model is a reasoning model requiring 3500+ tokens for reasoning budget:

```python
# Use explicit max_tokens
response = await client.generate(
    prompt="...",
    max_tokens=4096  # explicitly set
)
```

---

## Architecture Files (Read-First Order)

1. **`AGENTS.md`** — Standing rules, phases, processes
2. **`docs/architecture-v1.md`** — System layers and design
3. **`docs/CONTINUITY.md`** — Latest state and decisions
4. **`thinkbox/engine.py`** — Core ThinkBoxEngine runtime
5. **`thinkbox/memory_layers.py`** — Memory layer integration
6. **`thinkbox/dashboard_state.py`** — Event tracking

---

## Next Steps

After proving the workflow locally:

1. **Extend proof script** — Add your own test cases
2. **Build on memory** — Use memory layers in your own agents
3. **Model experimentation** — Try different prompts/temperatures
4. **Dashboard integration** — Track your own autonomous loops
5. **Local contributions** — Make changes, push to branches

---

## Cloud Environment Reference

The autonomous workflow is proven LIVE VERIFIED against:

- **Model:** Mercury-2 (reasoning model via Inception Labs API)
- **Persistence:** Upstash Redis (REST API)
- **Memory:** SQLite (four-layer store)
- **Dashboard:** In-process event tracking

All these work identically locally when environment variables are configured.

