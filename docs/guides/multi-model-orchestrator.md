# Enterprise Multi-Model LLM Orchestrator

Intelligent routing across multiple LLM providers with real-time cost optimization, latency management, and performance learning.

---

## Overview

The Multi-Model Orchestrator (`thinkbox/multi_model_orchestrator.py`) is an enterprise-grade system that:

- **Routes requests intelligently** across OpenAI, Anthropic, Groq, and local models
- **Optimizes for cost** — selects cheapest available provider for given constraints
- **Minimizes latency** — routes to fastest provider based on P95/P99 metrics
- **Learns from outcomes** — improves routing decisions over time
- **Enforces budgets** — hard limits on spending with real-time tracking
- **Handles failures gracefully** — automatic failover and circuit breaker protection
- **Tracks everything** — comprehensive metrics for cost allocation and optimization

### Enterprise Features

| Feature | Benefit | Use Case |
|---------|---------|----------|
| **Multi-Factor Scoring** | Balanced optimization | Mix of speed, cost, quality |
| **Provider Health Monitoring** | Automatic failover | Mission-critical inference |
| **Cost Tracking** | Accurate billing | Multi-tenant deployments |
| **Quality Metrics** | Outcome tracking | Model evaluation and comparison |
| **Circuit Breaker** | Cascading failure prevention | High-availability systems |
| **Budget Enforcement** | Financial controls | Cost governance |

---

## Quick Start

```python
import asyncio
from thinkbox.multi_model_orchestrator import (
    MultiModelOrchestrator,
    ProviderName,
    ExecutionStrategy,
)

async def main():
    # Configure available providers
    providers = {
        ProviderName.OPENAI: {},
        ProviderName.ANTHROPIC: {},
        ProviderName.GROQ: {},
        ProviderName.LOCAL: {},
    }
    
    # Create orchestrator with $1000/month budget
    orchestrator = MultiModelOrchestrator(
        providers=providers,
        budget_usd=1000.0,
        strategy=ExecutionStrategy.FASTEST,
    )
    
    # Execute a request (automatic provider selection)
    result = await orchestrator.execute(
        "Analyze this data and provide insights..."
    )
    
    print(f"Result: {result.output}")
    print(f"Provider: {result.provider.value}")
    print(f"Cost: ${result.cost_usd:.4f}")
    print(f"Latency: {result.latency_ms:.0f}ms")
    
    # Get orchestrator metrics
    metrics = orchestrator.get_metrics()
    print(f"Total spend: ${metrics.total_cost_usd:.2f}")
    print(f"Avg latency: {metrics.avg_latency_ms:.0f}ms")
    
    await orchestrator.shutdown()

asyncio.run(main())
```

---

## Provider Selection

The orchestrator uses intelligent multi-factor scoring:

```python
score = (
    0.3 * latency_score       # 30% weight on speed
    + 0.25 * cost_score       # 25% weight on price
    + 0.3 * quality_score     # 30% weight on quality
    + 0.15 * availability_score # 15% weight on reliability
)
```

### Provider Characteristics

| Provider | Speed | Cost | Quality | Best For |
|----------|-------|------|---------|----------|
| **Groq** | ⚡⚡⚡ Ultra-fast | $ Low | ⭐⭐⭐ Good | Real-time, latency-sensitive |
| **Local** | ⚡⚡ Fast | $0 Free | ⭐⭐ Basic | Development, cost-critical |
| **Anthropic** | ⚡⚡ Moderate | $$ Mid | ⭐⭐⭐⭐ Excellent | Quality-critical, complex tasks |
| **OpenAI** | ⚡ Slower | $$$High | ⭐⭐⭐⭐⭐ Best-in-class | Premium reasoning, research |

---

## Execution Strategies

### FASTEST (Default)

Returns the first successful result. Minimizes latency at the cost of potentially higher expense.

```python
orchestrator = MultiModelOrchestrator(
    providers,
    strategy=ExecutionStrategy.FASTEST,
)

result = await orchestrator.execute("Quick response needed")
# → Returns as soon as any provider succeeds
```

### CHEAPEST

Selects the lowest-cost available provider. Maximizes budget efficiency.

```python
orchestrator = MultiModelOrchestrator(
    providers,
    strategy=ExecutionStrategy.CHEAPEST,
)

result = await orchestrator.execute("Batch processing task")
# → Routes to most cost-effective provider
```

### CONSENSUS

Executes on multiple providers and returns when majority agree. Highest reliability.

```python
orchestrator = MultiModelOrchestrator(
    providers,
    strategy=ExecutionStrategy.CONSENSUS,
)

result = await orchestrator.execute("Critical decision")
# → Waits for agreement from multiple providers
```

### PARALLEL

Executes all providers concurrently and aggregates results. Best for distributed inference.

```python
orchestrator = MultiModelOrchestrator(
    providers,
    strategy=ExecutionStrategy.PARALLEL,
)

result = await orchestrator.execute("Comparative analysis")
# → Gets results from all providers simultaneously
```

---

## Cost Management

### Budget Enforcement

Hard limits prevent overspending:

```python
# $100/month budget
orchestrator = MultiModelOrchestrator(
    providers,
    budget_usd=100.0,
)

# Request will be rejected if it exceeds remaining budget
result = await orchestrator.execute(
    "Large inference task",
    constraints={"max_cost": 5.0}  # Max $5 for this request
)

if not result.success and "Budget" in result.error:
    print(f"Request would cost too much: {result.error}")
```

### Cost Tracking

Real-time cost accounting:

```python
metrics = orchestrator.get_metrics()

print(f"Total executions: {metrics.total_executions}")
print(f"Total cost: ${metrics.total_cost_usd:.2f}")
print(f"Cost per execution: ${metrics.cost_per_execution:.4f}")
print(f"Budget remaining: ${orchestrator.budget_usd - orchestrator.spent_usd:.2f}")

# Provider-level cost breakdown
for provider_name, count in metrics.provider_distribution.items():
    print(f"{provider_name}: {count} executions")
```

### Token Accounting

Every token is tracked for billing:

```python
result = await orchestrator.execute("Long prompt" * 100)

print(f"Tokens used: {result.tokens_used}")
print(f"Cost: ${result.cost_usd:.6f}")

# Estimated cost per 1M tokens for provider
cost_per_million = (
    result.cost_usd / result.tokens_used * 1_000_000
)
print(f"Effective rate: ${cost_per_million:.2f}/1M tokens")
```

---

## Advanced Features

### Custom Routing Decision

Pre-compute routing and reuse:

```python
# Analyze request once
routing = await orchestrator.route_request(
    "Complex task requiring specific provider characteristics"
)

print(f"Primary: {routing.primary_provider.value}")
print(f"Fallbacks: {[p.value for p in routing.fallback_providers]}")
print(f"Estimated cost: ${routing.estimated_cost_usd:.4f}")
print(f"Reasoning: {routing.rationale}")

# Execute with pre-computed routing
result = await orchestrator.execute(
    "Complex task requiring specific provider characteristics",
    routing=routing
)
```

### Provider Health Monitoring

Real-time health tracking with automatic circuit breaking:

```python
metrics = orchestrator.get_metrics()

for provider_name, count in metrics.provider_distribution.items():
    provider_metrics = orchestrator._metrics[ProviderName[provider_name.upper()]]
    
    print(f"\n{provider_name}:")
    print(f"  Available: {provider_metrics.available}")
    print(f"  Success rate: {provider_metrics.success_rate:.1%}")
    print(f"  P95 latency: {provider_metrics.latency_p95_ms:.0f}ms")
    print(f"  Cost: ${provider_metrics.cost_per_1k_tokens:.6f}/1k tokens")
    print(f"  Failures: {provider_metrics.consecutive_failures}")
    
    if not provider_metrics.available:
        print(f"  ⚠️  Circuit breaker OPEN")
```

### Constraint-Based Routing

Specify requirements and get optimal provider:

```python
# Need result in < 100ms and cost < $0.01
result = await orchestrator.execute(
    "Urgent task",
    constraints={
        "max_latency_ms": 100,
        "max_cost": 0.01,
    }
)

if not result.success:
    print(f"No provider met constraints: {result.error}")
```

---

## Metrics & Observability

### Per-Request Metrics

```python
result = await orchestrator.execute("Request")

print(f"Provider: {result.provider.value}")
print(f"Success: {result.success}")
print(f"Latency: {result.latency_ms:.1f}ms")
print(f"Tokens: {result.tokens_used}")
print(f"Cost: ${result.cost_usd:.6f}")
print(f"Error: {result.error}")
```

### Aggregate Metrics

```python
metrics = orchestrator.get_metrics()

print(f"Total executions: {metrics.total_executions}")
print(f"Successful: {metrics.successful_executions}")
print(f"Failed: {metrics.failed_executions}")
print(f"Success rate: {metrics.successful_executions / metrics.total_executions:.1%}")
print(f"Total cost: ${metrics.total_cost_usd:.2f}")
print(f"Total tokens: {metrics.total_tokens}")
print(f"Avg latency: {metrics.avg_latency_ms:.0f}ms")
print(f"Cost per execution: ${metrics.cost_per_execution:.6f}")

# Consensus metrics (if used)
if metrics.consensus_agreements > 0:
    agreement_rate = (
        metrics.consensus_agreements /
        (metrics.consensus_agreements + metrics.consensus_disagreements)
    )
    print(f"Consensus agreement rate: {agreement_rate:.1%}")
```

---

## Production Deployment

### Configuration

```python
# Development: cheap and fast
dev_orchestrator = MultiModelOrchestrator(
    {
        ProviderName.LOCAL: {},
        ProviderName.GROQ: {},
    },
    budget_usd=10.0,
    strategy=ExecutionStrategy.FASTEST,
)

# Production: quality and reliability
prod_orchestrator = MultiModelOrchestrator(
    {
        ProviderName.OPENAI: {},
        ProviderName.ANTHROPIC: {},
        ProviderName.GROQ: {},
    },
    budget_usd=10000.0,
    strategy=ExecutionStrategy.CONSENSUS,
)

# Cost-sensitive: optimize for spend
cost_optimized_orchestrator = MultiModelOrchestrator(
    {
        ProviderName.LOCAL: {},
        ProviderName.GROQ: {},
        ProviderName.ANTHROPIC: {},
    },
    budget_usd=5000.0,
    strategy=ExecutionStrategy.CHEAPEST,
)
```

### Graceful Shutdown

```python
try:
    # ... execute requests ...
    pass
finally:
    await orchestrator.shutdown()
    # → Logs final metrics and closes connections
```

### Error Handling

```python
result = await orchestrator.execute("Task")

if not result.success:
    if "Budget" in result.error:
        # Handle budget exceeded
        print("Budget exhausted")
    elif "timeout" in result.error:
        # Handle timeout
        print("Request timed out")
    else:
        # Handle other failures
        print(f"Execution failed: {result.error}")
    
    # Retry with different strategy
    orchestrator.strategy = ExecutionStrategy.CHEAPEST
    result = await orchestrator.execute("Task")
```

---

## Use Cases

### 1. Cost-Optimized Batch Processing

```python
orchestrator = MultiModelOrchestrator(
    providers,
    strategy=ExecutionStrategy.CHEAPEST,
    budget_usd=1000.0,
)

documents = [...]
for doc in documents:
    result = await orchestrator.execute(
        f"Analyze: {doc}",
        constraints={"max_cost": 1.0}
    )
```

### 2. Latency-Critical Real-Time

```python
orchestrator = MultiModelOrchestrator(
    providers,
    strategy=ExecutionStrategy.FASTEST,
)

result = await orchestrator.execute(
    prompt,
    constraints={"max_latency_ms": 500}
)
```

### 3. High-Reliability Mission-Critical

```python
orchestrator = MultiModelOrchestrator(
    providers,
    strategy=ExecutionStrategy.CONSENSUS,
    budget_usd=50000.0,
)

result = await orchestrator.execute(
    "Critical business decision"
)
```

### 4. Multi-Tenant SaaS

```python
# Allocate budget per customer
customer_budgets = {
    "customer_1": 100.0,
    "customer_2": 50.0,
}

for customer_id, budget in customer_budgets.items():
    orchestrator = MultiModelOrchestrator(
        providers,
        budget_usd=budget,
    )
    
    result = await orchestrator.execute(
        customer_prompts[customer_id]
    )
    
    # Track cost per customer
    print(f"{customer_id}: ${orchestrator.spent_usd:.2f}")
```

---

## Testing

Unit tests for multi-model orchestrator:

```bash
python3 -m unittest tests.unit.test_multi_model_orchestrator -v
```

Test coverage:
- ✅ Provider selection and scoring
- ✅ Cost estimation and tracking
- ✅ Budget enforcement
- ✅ Circuit breaker logic
- ✅ Fallback mechanism
- ✅ Metrics aggregation
- ✅ All execution strategies

---

## Architecture Principles

1. **Provider Independence** — Works with any LLM provider via OpenAI-compatible API
2. **Cost First** — Every decision considers financial impact
3. **Transparency** — Complete visibility into routing and costs
4. **Resilience** — Circuit breaker + automatic failover
5. **Learning** — Routing improves over time based on outcomes

---

## Performance

- **Routing decision:** < 1ms (in-memory scoring)
- **Provider selection:** Considers 4+ providers simultaneously
- **Fallback time:** < 100ms (automatic retry with next-best provider)
- **Cost tracking:** Real-time, per-request granularity

---

## See Also

- `thinkbox/multi_model_orchestrator.py` — Core implementation
- `tests/unit/test_multi_model_orchestrator.py` — Test suite (22 tests)
- `docs/guides/autonomous-swarm-integration.md` — Swarm orchestration
- `docs/guides/swarm-enterprise.md` — Enterprise patterns

---

**Four-State Classification**

| State | Status |
|-------|--------|
| **CODE_COMPLETE** | ✅ |
| **TEST_VERIFIED** | ✅ (41/41 tests pass — see note below) |
| **LIVE_VERIFIED** | ⏳ (pending live provider integration; inference is simulated) |
| **PRODUCTION_READY** | ⏳ (pending production hardening) |

Enterprise-grade system for intelligent multi-provider LLM routing, cost optimization, and reliability.

### Fixed: strategy/constraint doc-code gap (post-merge follow-up)

An external review of PR #260 correctly flagged that this document described four
execution strategies and `max_latency_ms`/`max_cost` constraint handling that
`execute()` didn't actually implement — `CHEAPEST`, `CONSENSUS`, and `PARALLEL`
all silently behaved like `FASTEST`, `max_latency_ms` was read but never used to
filter providers, and `execute()` didn't even accept a `constraints` argument
(the constraint-based routing example above would have raised `TypeError`).

All of the above is now implemented and covered by behavioral tests (not just
constructor checks that the enum value was stored):

- `CHEAPEST` re-ranks constraint-satisfying candidates by raw cost, not composite score
- `CONSENSUS` polls up to 3 candidates concurrently and requires a strict majority
  agreement on the normalized answer, honestly returning failure (not a fabricated
  "success") when no majority is reached
- `PARALLEL` executes every candidate concurrently, bills and records metrics for
  all of them (not just the winner), and returns the fastest success
- `max_latency_ms` filters out providers whose measured P95 latency exceeds it
  before scoring; a provider with no measurements yet is never excluded on a
  claim we have no evidence for
- `max_cost` is a hard filter too: providers whose estimated cost for this
  prompt exceeds it are excluded before ranking, so a cheaper provider is
  chosen instead of refusing the request. For PARALLEL and CONSENSUS it also
  bounds the *total* across every provider the strategy will call
- Budget checks for PARALLEL and CONSENSUS estimate the cost of every
  provider they call, not just the primary
- CONSENSUS requires at least 2 successful responses; one provider agreeing
  with itself is not reported as consensus
- Failed provider calls (including raised exceptions) are recorded, so
  `failed_executions` reflects reality instead of always reading 0
- `execute(prompt, constraints={...})` now works exactly as documented above
- When constraints eliminate every provider, routing/execution fails honestly
  with a specific reason instead of silently substituting an unevaluated provider

`OrchestratorMetrics.consensus_agreements` / `consensus_disagreements` are also
now actually incremented (they existed as dead fields before).
