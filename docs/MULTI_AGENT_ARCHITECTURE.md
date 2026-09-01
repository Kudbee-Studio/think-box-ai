# Multi-Agent Orchestration & Sub-Agent Hierarchy

**Issue:** #12 — Phase 3: Multi-Agent Orchestration
**Status:** Architecture designed — implementation ready

## Architecture

```
Director Hat (orchestrator)
    ├── Researcher Hat (investigation)
    │   ├── HTTP Worker (fetch data)
    │   ├── Parser Worker (extract info)
    │   └── Validator Worker (verify claims)
    ├── Runner Hat (execution)
    │   ├── GPU Worker (model inference)
    │   ├── Storage Worker (persist data)
    │   └── Network Worker (API calls)
    └── Camera Hat (media)
        ├── Render Worker (generate images)
        ├── Audio Worker (voice/sound)
        └── Video Worker (animations)
```

## Implementation

### Director Agent
- Receives high-level goal
- Decomposes into sub-tasks
- Spawns child agents
- Aggregates results
- Produces final verdict

### Child Agents
- Run in parallel where possible
- Report progress to director
- Can spawn their own children (max depth: 3)
- Handle their own errors

### Communication
- Message passing via job queue
- Shared memory via SQLite
- Status updates via WebSocket

## File Structure

```
core/runtime/
  director.py      # Orchestrator
  child_agent.py   # Base child agent
  hierarchy.py     # Tree management
  communication.py # Message passing
```

## Example Flow

1. Director receives: "Research DOGI indexer split"
2. Spawns: HTTP Worker (fetch from 3 sources)
3. Spawns: Parser Worker (extract DRC-20 data)
4. Spawns: Validator Worker (compare results)
5. Aggregates: All workers report back
6. Verdict: unproven / succeeded / failed / blocked
