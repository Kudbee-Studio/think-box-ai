# Autonomous Swarm Integration — Production Workflows

Bind autonomous workflow loops to the enterprise swarm pool for concurrent execution with production-grade resilience, metrics, and circuit breaker protection.

---

## Overview

The Autonomous Swarm Integration (`thinkbox/autonomous_swarm_integration.py`) combines:

- **Autonomous Workflow Logic** — Multi-iteration loops with Sense → Decide → Act → Learn cycle
- **Enterprise Swarm Pool** — Concurrent task execution with circuit breaker and adaptive rate limiting
- **Metrics Aggregation** — Per-workflow and pool-wide metrics tracking

This binding enables running multiple autonomous loops in parallel with hard resource limits, automatic failure handling, and comprehensive observability.

---

## Quick Start

```python
import asyncio
from thinkbox.autonomous_swarm_integration import (
    AutonomousSwarmPool,
    AutonomousWorkflowSpec,
)

async def main():
    # Create swarm pool for autonomous workflows
    pool = AutonomousSwarmPool(max_concurrent_workflows=8)
    
    # Define workflows to execute
    workflows = [
        AutonomousWorkflowSpec(
            workflow_id="optimize_cache",
            goal="Optimize system cache hit rate",
            initial_observations=[
                "Current hit rate: 75%",
                "Memory pressure: moderate",
            ],
        ),
        AutonomousWorkflowSpec(
            workflow_id="reduce_latency",
            goal="Reduce P95 latency to < 100ms",
            initial_observations=[
                "Current P95: 250ms",
                "Load: 60%",
            ],
        ),
    ]
    
    # Execute all workflows concurrently
    results = await pool.execute_workflows_concurrently(workflows)
    
    # Check results
    for result in results:
        print(f"{result.workflow_id}: {'✅' if result.success else '❌'}")
        if result.success:
            print(f"  Decision: {result.final_decision}")
            print(f"  Iterations: {result.iterations}")
    
    # Get aggregate metrics
    metrics = pool.get_pool_metrics()
    print(f"\nPool success rate: {metrics['success_rate']:.1%}")
    print(f"Pool health: {metrics['health']}")
    
    await pool.shutdown()

asyncio.run(main())
```

---

## Workflow Specification

Define an autonomous workflow with `AutonomousWorkflowSpec`:

```python
from thinkbox.autonomous_swarm_integration import AutonomousWorkflowSpec
from thinkbox.swarm_enterprise import TaskPriority

spec = AutonomousWorkflowSpec(
    workflow_id="my_workflow",
    goal="Achieve specific outcome",
    initial_observations=[
        "Observation 1",
        "Observation 2",
        "Observation 3",
    ],
    max_iterations=10,              # Max loop iterations
    priority=TaskPriority.HIGH,     # Execution priority
    timeout_ms=600000,              # 10 minute timeout
)
```

### Fields

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `workflow_id` | str | Required | Unique identifier |
| `goal` | str | Required | What the workflow should achieve |
| `initial_observations` | list[str] | Required | Starting context |
| `max_iterations` | int | 10 | Maximum loop iterations |
| `priority` | TaskPriority | NORMAL | Execution priority (CRITICAL, HIGH, NORMAL, LOW, BACKGROUND) |
| `timeout_ms` | int | 300000 (5min) | Execution timeout in milliseconds |

---

## Execution Modes

### Single Workflow

Execute one workflow and wait for result:

```python
result = await pool.execute_workflow(spec)

print(f"Success: {result.success}")
print(f"Iterations: {result.iterations}")
print(f"Decision: {result.final_decision}")
```

### Concurrent Workflows

Execute multiple workflows in parallel:

```python
specs = [spec1, spec2, spec3, spec4]
results = await pool.execute_workflows_concurrently(specs)

successful = sum(1 for r in results if r.success)
print(f"Completed: {successful}/{len(results)}")
```

---

## Execution Results

Each workflow execution returns a `WorkflowExecutionResult`:

```python
@dataclass
class WorkflowExecutionResult:
    workflow_id: str                        # Workflow identifier
    success: bool                           # Execution succeeded
    iterations: int                         # Number of loop iterations
    final_decision: Optional[str] = None    # Last action taken
    metrics: Optional[ExecutionMetrics] = None  # Performance metrics
    error: Optional[str] = None             # Error message if failed
```

### Accessing Results

```python
# After execution
result = await pool.execute_workflow(spec)

# Check status
if result.success:
    print(f"✅ Completed in {result.iterations} iterations")
    print(f"Decision: {result.final_decision}")
else:
    print(f"❌ Failed: {result.error}")

# Access metrics
if result.metrics:
    print(f"Latency: {result.metrics.latency_ms}ms")
    print(f"Tokens: {result.metrics.tokens_used}")
```

### Retrieving Results Later

```python
# Store results during execution
results = await pool.execute_workflows_concurrently(specs)

# Retrieve individual result
result = pool.get_workflow_result("my_workflow_id")

# Get all results
all_results = pool.get_all_results()
for workflow_id, result in all_results.items():
    print(f"{workflow_id}: {result.success}")
```

---

## Workflow Execution Loop

Each autonomous workflow follows the loop:

```
SENSE → DECIDE → ACT → LEARN
```

The swarm executes this as a prompt to the model, which responds with:

```json
{
    "action": "Take this action",
    "reasoning": "Why we chose this",
    "confidence": 0.85,
    "next_observation_prompt": "What should we observe next?"
}
```

---

## Metrics & Observability

### Workflow Metrics

Each workflow execution includes detailed metrics:

```python
result = await pool.execute_workflow(spec)

if result.metrics:
    print(f"Task ID: {result.metrics.task_id}")
    print(f"Success: {result.metrics.success}")
    print(f"Latency: {result.metrics.latency_ms}ms")
    print(f"Tokens used: {result.metrics.tokens_used}")
    print(f"Attempts: {result.metrics.retry_count}")
    print(f"Error: {result.metrics.error_type}")
```

### Pool Metrics

Get aggregate metrics across all workflows:

```python
metrics = pool.get_pool_metrics()

print(f"Total workflows: {metrics['total_workflows']}")
print(f"Successful: {metrics['successful_workflows']}")
print(f"Success rate: {metrics['success_rate']:.1%}")
print(f"Pool health: {metrics['health']}")
print(f"  Circuit breaker: {metrics['health']['circuit_breaker']}")
print(f"  Active workers: {metrics['health']['active_workers']}")
```

---

## Priority Scheduling

Control execution priority:

```python
from thinkbox.swarm_enterprise import TaskPriority

# CRITICAL: Run immediately, bypass queues
critical_spec = AutonomousWorkflowSpec(
    workflow_id="urgent",
    goal="...",
    initial_observations=[...],
    priority=TaskPriority.CRITICAL,
)

# BACKGROUND: Run when resources available
background_spec = AutonomousWorkflowSpec(
    workflow_id="analysis",
    goal="...",
    initial_observations=[...],
    priority=TaskPriority.BACKGROUND,
)
```

---

## Timeout Management

Set per-workflow timeout:

```python
# 30 seconds
fast_spec = AutonomousWorkflowSpec(
    workflow_id="quick_decision",
    goal="...",
    initial_observations=[...],
    timeout_ms=30000,  # 30 seconds
)

# 10 minutes
long_spec = AutonomousWorkflowSpec(
    workflow_id="deep_analysis",
    goal="...",
    initial_observations=[...],
    timeout_ms=600000,  # 10 minutes
)
```

---

## Error Handling

Handle workflow failures gracefully:

```python
result = await pool.execute_workflow(spec)

if not result.success:
    # Determine cause
    if result.error:
        if "TimeoutError" in result.error:
            print("Workflow exceeded timeout")
        elif "CircuitBreakerOpen" in result.error:
            print("Service temporarily unavailable")
        else:
            print(f"Execution error: {result.error}")
    
    # Decide on retry
    if result.metrics and result.metrics.retry_count < 3:
        # Retry with longer timeout
        result = await pool.execute_workflow(
            spec
        )
```

---

## Production Deployment

### Configuration

```python
# Development
dev_pool = AutonomousSwarmPool(
    max_concurrent_workflows=4,
)

# Production (high throughput)
prod_pool = AutonomousSwarmPool(
    max_concurrent_workflows=64,
)
```

### Graceful Shutdown

```python
try:
    # ... execute workflows ...
finally:
    await pool.shutdown()
```

### Circuit Breaker Monitoring

The pool includes automatic circuit breaker for resilience:

```python
health = pool.get_pool_metrics()["health"]

if health["circuit_breaker"] == "open":
    # Service degraded, back off
    await asyncio.sleep(60)
    # Try again later
elif health["circuit_breaker"] == "half_open":
    # Recovering, limited traffic
    pass
```

---

## Integration with Memory Layers

Store workflow decisions in organizational memory:

```python
from core.memory.store import MemoryStore
from core.memory.schema import MemoryEntry, MemoryLayer, MemoryEntryType

memory = MemoryStore("./data/memory.db")

# After workflow completes
result = await pool.execute_workflow(spec)

if result.success:
    # Store the decision pattern
    memory.put(MemoryEntry(
        key=f"workflow_decision_{result.workflow_id}_{uuid.uuid4().hex[:8]}",
        layer=MemoryLayer.ORGANIZATIONAL,
        entry_type=MemoryEntryType.PATTERN,
        value={
            "workflow_id": result.workflow_id,
            "goal": spec.goal,
            "decision": result.final_decision,
            "iterations": result.iterations,
            "confidence": "high" if result.metrics.latency_ms < 500 else "medium",
        },
        agent_id="autonomous_agent",
        task_id=result.workflow_id,
    ))
```

---

## Testing

Unit tests for autonomous swarm integration:

```bash
python3 -m unittest tests.unit.test_autonomous_swarm_integration -v
```

See `tests/unit/test_autonomous_swarm_integration.py` for comprehensive test suite covering:
- Single and concurrent workflow execution
- Priority and timeout configuration
- Metrics aggregation
- Exception handling
- Result retrieval

---

## Four-State Classification

| State | Status |
|-------|--------|
| **CODE_COMPLETE** | ✅ Implementation done |
| **TEST_VERIFIED** | ✅ 14/14 unit tests passing |
| **LIVE_VERIFIED** | ⏳ Pending integration with live Mercury-2 |
| **PRODUCTION_READY** | ⏳ Pending production hardening |

---

## Example: Multi-Goal Optimization

Run multiple optimization workflows concurrently:

```python
async def multi_goal_optimization():
    pool = AutonomousSwarmPool(max_concurrent_workflows=16)
    
    goals = [
        ("optimize_cpu", "Reduce CPU usage by 20%"),
        ("optimize_memory", "Reduce memory footprint by 15%"),
        ("optimize_io", "Reduce disk I/O by 30%"),
        ("optimize_network", "Reduce network latency by 25%"),
    ]
    
    specs = [
        AutonomousWorkflowSpec(
            workflow_id=goal_id,
            goal=goal_desc,
            initial_observations=[
                "Current system metrics available",
                "Historical patterns loaded",
                "Constraints enforced",
            ],
            priority=TaskPriority.HIGH,
        )
        for goal_id, goal_desc in goals
    ]
    
    results = await pool.execute_workflows_concurrently(specs)
    
    # Aggregate results
    successful = sum(1 for r in results if r.success)
    print(f"Achieved {successful}/{len(goals)} optimization goals")
    
    # Print decisions
    for result in results:
        if result.success:
            print(f"✅ {result.workflow_id}: {result.final_decision}")
    
    await pool.shutdown()

asyncio.run(multi_goal_optimization())
```

---

## See Also

- `thinkbox/swarm_enterprise.py` — Enterprise swarm pool implementation
- `docs/guides/swarm-enterprise.md` — Swarm pool guide
- `docs/guides/local-development.md` — Local setup and testing
