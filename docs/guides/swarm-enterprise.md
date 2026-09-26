# Enterprise-Grade Swarm Orchestration

Production-ready concurrent task execution with resilience, observability, and adaptive performance tuning.

---

## Overview

The Enterprise Swarm Pool provides:

- **Resilience:** Circuit breaker pattern, exponential backoff, intelligent retries
- **Efficiency:** Adaptive rate limiting, priority scheduling, resource pooling
- **Observability:** Comprehensive metrics, health checks, distributed tracing
- **Safety:** Timeout enforcement, graceful degradation, fair queuing

---

## Quick Start

```python
import asyncio
from thinkbox.swarm_enterprise import EnterpriseSwarmPool, TaskConfig, TaskPriority

async def main():
    pool = EnterpriseSwarmPool(max_workers=32)
    
    # Execute a single task
    result = await pool.execute_task("task1", "Solve: what is 2+2?")
    print(f"Success: {result.success}, Latency: {result.latency_ms}ms")
    
    # Execute batch
    tasks = [
        ("t1", "Problem 1"),
        ("t2", "Problem 2"),
        ("t3", "Problem 3"),
    ]
    results = await pool.execute_batch(tasks)
    print(f"Completed {len([r for r in results if r.success])}/{len(results)} tasks")
    
    # Get metrics
    metrics = pool.metrics
    print(f"Success rate: {metrics.success_rate:.1%}")
    print(f"P95 latency: {metrics.p95_latency_ms:.0f}ms")
    
    await pool.shutdown()

asyncio.run(main())
```

---

## Circuit Breaker Pattern

Automatically stops sending requests when the backend is degraded.

```python
from thinkbox.swarm_enterprise import CircuitBreaker, CircuitState

# Configure circuit breaker
circuit = CircuitBreaker(
    failure_threshold=5,      # Open after 5 failures
    recovery_timeout_s=60,    # Try recovery after 60s
)

# During normal operation: CLOSED
# After 5 failures: OPEN (rejects all requests)
# After timeout: HALF_OPEN (allows test request)
# If test succeeds: returns to CLOSED

# Manually record outcomes
circuit.record_success()  # Decrement failure count
circuit.record_failure()  # Increment and potentially open

# Check availability
if circuit.is_available():
    # Safe to send request
    pass
else:
    # Circuit is open, fail fast
    pass
```

---

## Adaptive Rate Limiting

Automatically scales throughput based on success rate.

```python
from thinkbox.swarm_enterprise import AdaptiveRateLimiter

limiter = AdaptiveRateLimiter(initial_rate=100)  # 100 req/s

# During task execution
await limiter.acquire()  # Wait if necessary to maintain rate

# Update based on success rate
limiter.update_rate(success_rate=0.95)  # High success → increase rate
limiter.update_rate(success_rate=0.5)   # Low success → decrease rate

# Current rate adapts in real-time
print(f"Current rate: {limiter.current_rate}")
```

---

## Task Configuration

Customize execution behavior per task.

```python
from thinkbox.swarm_enterprise import TaskConfig, TaskPriority

# Default configuration
config = TaskConfig()

# Custom configuration
config = TaskConfig(
    max_retries=5,              # Retry up to 5 times
    timeout_ms=60000,           # 60 second timeout
    priority=TaskPriority.HIGH, # High priority
    speculation_enabled=True,   # Enable speculative execution
    trace_id="custom-trace-123" # Custom trace ID for distributed tracing
)

# Use in execution
result = await pool.execute_task("task1", "prompt", config)
```

---

## Execution Metrics

Track every task execution.

```python
from thinkbox.swarm_enterprise import ExecutionMetrics

# Each task returns detailed metrics
result: ExecutionMetrics = await pool.execute_task("task1", "prompt")

print(f"Task ID: {result.task_id}")
print(f"Success: {result.success}")
print(f"Latency: {result.latency_ms}ms")
print(f"Tokens: {result.tokens_used}")
print(f"Attempts: {result.retry_count}")
print(f"Error: {result.error_type}")
print(f"Trace ID: {result.timestamp}")
```

---

## Pool Metrics

Get aggregate metrics for monitoring.

```python
pool = EnterpriseSwarmPool(max_workers=32)

# ... execute many tasks ...

metrics = pool.metrics
print(f"Total tasks: {metrics.total_tasks}")
print(f"Successful: {metrics.successful_tasks}")
print(f"Failed: {metrics.failed_tasks}")
print(f"Success rate: {metrics.success_rate:.1%}")
print(f"Avg latency: {metrics.avg_latency_ms:.0f}ms")
print(f"P95 latency: {metrics.p95_latency_ms:.0f}ms")
print(f"P99 latency: {metrics.p99_latency_ms:.0f}ms")
print(f"Total tokens: {metrics.total_tokens}")
print(f"Circuit trips: {metrics.circuit_breaker_trips}")
```

---

## Health Checks

Monitor pool health for observability systems.

```python
health = pool.get_health_status()

# Health status for Kubernetes liveness probes
print(f"Healthy: {health['healthy']}")  # Boolean
print(f"Circuit state: {health['circuit_breaker']}")  # 'closed', 'open', 'half_open'
print(f"Success rate: {health['success_rate']}")  # '95.2%'
print(f"Avg latency: {health['avg_latency_ms']}")  # '120ms'
print(f"Active workers: {health['active_workers']}")  # 12/32
```

Use in Prometheus/Kubernetes:

```python
from prometheus_client import Gauge

pool_health = Gauge('swarm_pool_healthy', 'Whether swarm pool is healthy')

while True:
    health = pool.get_health_status()
    pool_health.set(1 if health['healthy'] else 0)
    await asyncio.sleep(5)
```

---

## Batch Processing

Execute multiple tasks with optimal concurrency.

```python
tasks = [
    ("task1", "Analyze data A"),
    ("task2", "Analyze data B"),
    ("task3", "Analyze data C"),
    ("task4", "Analyze data D"),
]

# Execute all concurrently
results = await pool.execute_batch(tasks)

# Process results
for result in results:
    if result.success:
        print(f"✅ {result.task_id}: {result.latency_ms:.0f}ms")
    else:
        print(f"❌ {result.task_id}: {result.error_type}")
```

---

## Metrics Callbacks

React to execution in real-time.

```python
def on_task_complete(metric: ExecutionMetrics):
    """Called after every task execution."""
    if not metric.success:
        logger.error(f"Task {metric.task_id} failed: {metric.error_type}")
    
    if metric.latency_ms > 1000:
        logger.warning(f"Task {metric.task_id} was slow: {metric.latency_ms}ms")

pool.on_metric(on_task_complete)

# Async callback also supported
async def on_task_complete_async(metric: ExecutionMetrics):
    await db.log_execution(metric)

pool.on_metric(on_task_complete_async)
```

---

## Production Deployment

### Configuration

```python
# For development/testing
dev_pool = EnterpriseSwarmPool(
    max_workers=4,
    max_tasks_per_second=10,
)

# For production (high throughput)
prod_pool = EnterpriseSwarmPool(
    max_workers=64,
    max_tasks_per_second=1000,
)
```

### Monitoring

```python
import logging

# Enable debug logging for troubleshooting
logging.basicConfig(level=logging.DEBUG)

# Or for production, log only warnings
logging.getLogger("thinkbox.swarm_enterprise").setLevel(logging.WARNING)
```

### Graceful Shutdown

```python
# Always shutdown gracefully
try:
    # ... execute tasks ...
finally:
    await pool.shutdown()
```

---

## Resilience Guarantees

### Circuit Breaker

- **Automatic degradation:** Opens after 5 consecutive failures
- **Recovery window:** Attempts recovery every 60 seconds
- **Fast failure:** Returns error immediately when open

### Retry Logic

- **Exponential backoff:** 2^attempt seconds delay
- **Max retries:** Configurable (default 3)
- **Retryable errors:** Only transient errors are retried
- **Timeout protection:** Never retries past configured timeout

### Rate Limiting

- **Adaptive:** Scales based on success rate
- **Backpressure:** Enforces upper limit on concurrency
- **Fair queueing:** FIFO with priority support

---

## SLA Tracking

Monitor against SLOs.

```python
LATENCY_SLO_MS = 500
SUCCESS_RATE_SLO = 0.99

metrics = pool.metrics

# Check latency SLO
if metrics.p95_latency_ms > LATENCY_SLO_MS:
    alert("Latency SLO violated")

# Check success SLO
if metrics.success_rate < SUCCESS_RATE_SLO:
    alert("Success rate SLO violated")
```

---

## Troubleshooting

### High Latency

```python
health = pool.get_health_status()

# Check if circuit is open
if health['circuit_breaker'] == 'open':
    logger.error("Circuit breaker open - backend is degraded")

# Check if rate limited
if health['circuit_breaker'] == 'half_open':
    logger.warn("Recovering from failure - requests may be slow")

# Check worker utilization
workers_active = int(health['active_workers'].split('/')[0])
if workers_active > 28:  # Out of 32
    logger.warn("Near full capacity - consider scaling up")
```

### High Failure Rate

```python
metrics = pool.metrics

if metrics.failed_tasks > metrics.total_tasks * 0.05:  # >5% failures
    # Check retry count
    for metric in pool._execution_metrics[-100:]:  # Last 100
        if not metric.success and metric.retry_count == 0:
            # Task failed immediately (not a transient error)
            logger.error(f"Task {metric.task_id} failed: {metric.error_type}")
```

---

## Testing

See `tests/unit/test_swarm_enterprise.py` for comprehensive test suite.

```bash
python3 -m unittest tests.unit.test_swarm_enterprise -v
```

