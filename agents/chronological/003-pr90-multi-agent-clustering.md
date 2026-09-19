# PR90: Multi-Agent Clustering — Implementation Plan

**Date:** Planned (Post-PR89)  
**Status:** PLANNED  
**Branch:** `feat/kilo-agent-clustering-pr90` (to be created)  
**PR:** #90 (to be created)  

---

## Objective

Implement multi-agent coordination: SUPERVISOR_AGENT for lifecycle management, ROUTER_AGENT for work distribution, and ENSEMBLE_AGENT for consensus/parallel execution. Enable agent pools, dynamic scaling, and inter-agent communication.

---

## Scope

### New Agent Types (Implemented in PR90)

| Agent | Category | Purpose | Key Capabilities |
|-------|----------|---------|------------------|
| **SUPERVISOR_AGENT** | Coordination | Manage agent pools | Spawn, monitor, restart, scale, health, drain |
| **ROUTER_AGENT** | Coordination | Route work to agents | Capability matching, load balancing, failover |
| **ENSEMBLE_AGENT** | Coordination | Multi-agent coordination | Consensus, parallel execution, result aggregation |

### Infrastructure Components

| Component | Description |
|-----------|-------------|
| **Agent Registry** | Central registry (registration, discovery, health, metadata) |
| **Inter-Agent Communication** | gRPC-based agent-to-agent protocol |
| **Pool Manager** | Manages agent pools per category/tenant |
| **Scaling Controller** | Implements scaling policies (HPA-like for agents) |
| **Consensus Engine** | Raft-based consensus for ENSEMBLE_AGENT |

---

## SUPERVISOR_AGENT

### Responsibilities
1. **Pool Management** — Maintain target agent count per category
2. **Health Monitoring** — Poll `/health/ready`, track liveness
3. **Auto-Scaling** — Scale up/down based on queue depth, latency, errors
4. **Failure Recovery** — Restart failed agents, replace unhealthy
5. **Graceful Drain** — Progressive drain on scale-down/termination
6. **Configuration Push** — Distribute config updates to pool

### Architecture
```
SUPERVISOR_AGENT
├── Pool Controller (per category/tenant)
│   ├── Target Replicas
│   ├── Scaling Policy
│   └── Health Monitor
├── Agent Spawner
│   ├── Launch Config
│   ├── Resource Request
│   └── Bootstrap
├── Health Aggregator
│   ├── /health/ready polling
│   ├── Liveness tracking
│   └── Metrics collection
└── Command Dispatcher
    ├── Preempt
    ├── Pause/Resume
    ├── Config Update
    └── Terminate
```

### Scaling Policies
```python
class ScalingPolicy:
    # Reactive scaling
    min_replicas: int = 2
    max_replicas: int = 100
    target_queue_depth_per_agent: int = 10
    target_latency_p99_ms: int = 5000
    target_error_rate: float = 0.01
    
    # Stabilization
    scale_up_stabilization_seconds: int = 60
    scale_down_stabilization_seconds: int = 300
    
    # Predictive scaling (PR91+)
    # predictive_enabled: bool = False
```

### Spawn Flow
```
1. SUPERVISOR decides to scale up
2. Request capacity from Orchestration (CapacityRequest)
3. Orchestration grants allocation (CapacityResponse)
4. SUPERVISOR launches agent process/container
5. Agent initializes → registers with Scheduler + Registry
6. SUPERVISOR verifies health → adds to pool
```

---

## ROUTER_AGENT

### Responsibilities
1. **Capability Matching** — Route tasks to agents with required capabilities
2. **Load Balancing** — Distribute work evenly (weighted by capacity)
3. **Failover** — Re-route from unhealthy agents
4. **Affinity** — Respect task/agent affinity hints
5. **Priority Handling** — Higher priority tasks first

### Routing Algorithm
```python
class Router:
    async def route(self, task: TaskSpec) -> AgentSelection:
        # 1. Filter agents by capability match
        candidates = registry.find_agents(
            capabilities=task.required_capabilities,
            governance_tier=task.required_tier
        )
        
        # 2. Filter by health
        healthy = [a for a in candidates if a.health == HEALTHY]
        
        # 3. Score by capacity + affinity + latency
        scored = []
        for agent in healthy:
            score = (
                agent.available_capacity * 0.4 +
                agent.affinity_score(task) * 0.3 +
                (1 / agent.avg_latency_ms) * 0.3
            )
            scored.append((score, agent))
        
        # 4. Select highest (with jitter for fairness)
        return max(scored, key=lambda x: x[0] + random.uniform(0, 0.1))[1]
```

### Integration with Scheduler
- Scheduler assigns tasks to ROUTER_AGENT (not directly to workers)
- ROUTER_AGENT acts as "virtual agent" with unlimited capacity
- ROUTER_AGENT forwards to actual workers via inter-agent protocol

---

## ENSEMBLE_AGENT

### Responsibilities
1. **Consensus** — Multi-agent agreement on results (Byzantine fault tolerant)
2. **Parallel Execution** — Fan-out to multiple agents, aggregate results
3. **Result Aggregation** — Voting, averaging, custom reducers
4. **Partial Failure Handling** — Quorum requirements, timeout handling

### Consensus Patterns
| Pattern | Use Case | Quorum |
|---------|----------|--------|
| **Majority Vote** | Classification, verification | > 50% |
| **Unanimous** | Safety-critical, financial | 100% |
| **Weighted Vote** | Heterogeneous agents | Configurable |
| **Median/Average** | Numeric estimation | N/A |

### Architecture
```
ENSEMBLE_AGENT
├── Consensus Coordinator
│   ├── Quorum Manager
│   ├── Timeout Manager
│   └── Result Aggregator
├── Agent Pool Selector
│   ├── Capability Filter
│   ├── Diversity Selector (for Byzantine resistance)
│   └── Load Balancer
└── Communication Layer
    ├── Broadcast (fan-out)
    ├── Collect (fan-in)
    └── Aggregation
```

### Execution Flow
```
1. ENSEMBLE receives task
2. Select N agents (diverse, healthy, capable)
3. Broadcast task to all N (with consensus config)
4. Collect responses (with timeout)
5. Apply consensus algorithm
6. Emit aggregated result
7. Report outcome to scheduler
```

---

## Agent Registry

### Features
| Feature | Description |
|---------|-------------|
| **Registration** | Agent registers at startup (TTL-based) |
| **Discovery** | Query by capability, type, health, tenant |
| **Health Tracking** | Aggregates `/health/ready` + heartbeats |
| **Metadata** | Version, config, resource profile, tags |
| **Watch** | Subscribe to registry changes |

### API
```python
class AgentRegistry:
    async def register(self, agent: AgentRegistration) -> RegistrationReceipt: ...
    async def deregister(self, agent_id: str) -> None: ...
    async def heartbeat(self, agent_id: str, health: HealthStatus) -> None: ...
    async def find_agents(self, query: AgentQuery) -> list[AgentInfo]: ...
    async def watch(self, query: AgentQuery) -> AsyncIterator[RegistryEvent]: ...
```

---

## Inter-Agent Communication

### Protocol
- **Transport:** gRPC (bidirectional streaming for long-lived)
- **Auth:** mTLS (SPIFFE identities from mesh)
- **Serialization:** Protobuf (defined in `protocol/agent_to_agent.proto`)

### Message Types
```protobuf
message AgentMessage {
  string from_agent_id = 1;
  string to_agent_id = 2;
  string correlation_id = 3;
  MessageType type = 4;
  google.protobuf.Any payload = 5;
  string timestamp = 6;
}

enum MessageType {
  TASK_FORWARD = 0;      // ROUTER → WORKER
  TASK_RESULT = 1;       // WORKER → ROUTER/ENSEMBLE
  CONSENSUS_PROPOSE = 2; // ENSEMBLE → WORKERS
  CONSENSUS_VOTE = 3;    // WORKERS → ENSEMBLE
  HEALTH_UPDATE = 4;     // WORKER → SUPERVISOR
  CONFIG_PUSH = 5;       // SUPERVISOR → WORKERS
  SHUTDOWN_SIGNAL = 6;   // SUPERVISOR → WORKER
}
```

---

## Implementation Order

### Phase 1: Registry & Communication (Week 1)
1. Agent Registry service (SQLite + in-memory cache)
2. Inter-agent gRPC protocol (`protocol/agent_to_agent.proto`)
3. Registration/deregistration/heartbeat flow
4. Watch/notification mechanism

### Phase 2: SUPERVISOR_AGENT (Week 1-2)
5. Pool controller with scaling policies
6. Agent spawner (via OrchestrationClient)
7. Health monitor (polling + heartbeat aggregation)
8. Command dispatcher (preempt, pause, terminate)
9. Graceful drain implementation

### Phase 3: ROUTER_AGENT (Week 2)
10. Capability-based routing logic
11. Load balancing algorithms
12. Failover handling
13. Integration with Scheduler (as virtual agent)

### Phase 4: ENSEMBLE_AGENT (Week 2-3)
14. Consensus coordinator (pluggable algorithms)
15. Agent pool selection (diversity-aware)
16. Broadcast/collect communication pattern
17. Result aggregation (voting, averaging, custom)

### Phase 5: Integration & Testing (Week 3-4)
18. End-to-end: SUPERVISOR spawns pool → ROUTER routes → ENSEMBLE coordinates
19. Chaos testing: agent failures, network partitions, scheduler failover
20. Scale testing: 100+ agents, rapid scale up/down
21. Integration with Governed Scheduler (preemption, capacity)
22. Integration with KUDBEE Mesh (multi-node)

---

## FourState Target

| Phase | Target |
|-------|--------|
| **CODE_COMPLETE** | ✅ All 3 agent types + registry + communication |
| **TEST_VERIFIED** | ✅ Unit + integration + chaos tests |
| **LIVE_VERIFIED** | ✅ Multi-agent pool on Upstash Box |
| **PRODUCTION_READY** | ⏳ After PR91 (distributed governance) |

---

## Dependencies

### Requires PR89
- `AgentKernel` base class
- `SchedulerClient`, `GovernanceClient`, `TelemetryEmitter`, `OrchestrationClient`
- Protocol infrastructure (gRPC, health, telemetry)

### New Dependencies
```toml
dependencies = [
    # ... PR89 deps ...
    "consensus-engine>=0.1",  # or implement Raft
    "asyncio-mqtt>=0.10",     # optional for alt transport
]
```

---

## References

- `agents/core/agent-categories.md` — SUPERVISOR, ROUTER, ENSEMBLE definitions
- `agents/core/agent-lifecycle.md` — Lifecycle for coordination agents
- `agents/integration/scheduler-integration.md` — Scheduler integration
- `agents/integration/cloud-orchestration.md` — Capacity requests for scaling
- `agents/integration/protocol-responsibilities.md` — Inter-agent protocol
- `docs/kudbee-control-fabric.md` — Mesh compromise containment