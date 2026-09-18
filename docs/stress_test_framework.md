# Concurrency Stress Testing Framework

The `thinkbox.concurrent_goals` module now includes a comprehensive stress testing framework for evaluating concurrent goal execution under various budget contention policies.

## Overview

The stress testing framework allows you to:

1. **Run concurrent goals under controlled budgets** - Test how the system behaves when multiple goals compete for a shared call budget
2. **Evaluate budget contention policies** - Compare FAIR_SHARE, PRIORITY, and FIFO allocation strategies
3. **Measure fairness** - Quantify how fairly budget is distributed across goals using Jain's fairness index, Gini coefficient, and coefficient of variation
3. **Rate limiting** - Control the rate of concurrent calls using QPS limiting
4. **Persistence** - Automatically persist results via ExperimentManager for later analysis
5. **Dashboard integration** - View stress test results in the KUDBEE dashboard

## Quick Start

```python
from thinkbox.concurrent_goals import (
    ConcurrentGoalsRunner, StressTestConfig, StressTestRunner,
    BudgetContentionPolicy
)
from thinkbox.pop_arena import VerifiedRetryConfig, system_prompt_for_v2

# Create a stress test configuration
config = StressTestConfig(
    num_goals=20,
    max_calls_global=100,
    max_retries_global=1,
    contention_policy=BudgetContentionPolicy.PRIORITY,
    max_duration_seconds=120.0,
    target_qps=10.0,  # Optional rate limiting
)

# Define a goal factory
def goal_factory(index: int) -> ConcurrentGoalSpec:
    prompt, spec = system_prompt_for_v2("compute", "add_small")
    return ConcurrentGoalSpec(
        goal=f"compute-goal-{index}",
        subtasks=[{"description": prompt, "family": "compute", "variant": "add_small",
                  "spec": spec, "depends_on": []}],
        budget_config=VerifiedRetryConfig(max_calls=10, max_retries=1),
        priority=index % 5,
    )

# Run the stress test
config = StressTestConfig(
    num_goals=50,
    max_calls_global=200,
    contention_policy=BudgetContentionPolicy.FAIR_SHARE,
    goal_factory=my_goal_factory,
    target_qps=20.0,
)

runner = StressTestRunner(ConcurrentGoalsRunner())
result = await runner.run_stress_test(config, my_complete_async)

print(f"Fairness Index: {result.fairness_index}")
print(f"Total Calls: {result.total_calls}")
print(f"Per-Goal Calls: {result.per_goal_calls}")
```

## Configuration Options

### StressTestConfig

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `num_goals` | int | 10 | Number of concurrent goals to run |
| `max_calls_global` | int | 50 | Global call budget (shared across all goals) |
| `max_retries_global` | int | 1 | Maximum retries per task |
| `contention_policy` | BudgetContentionPolicy | FAIR_SHARE | Budget allocation policy |
| `goal_factory` | Callable[[int], ConcurrentGoalSpec] | None | Factory function to create goals |
| `max_duration_seconds` | float | 60.0 | Maximum test duration |
| `target_qps` | float | None | Optional rate limit (calls/second) |

### BudgetContentionPolicy

| Policy | Description |
|--------|-------------|
| `FAIR_SHARE` | Equal budget shares per goal |
| `PRIORITY` | Higher priority goals consume budget first |
| `FIFO` | First-in-first-out allocation |

## Running Stress Tests

### Using the CLI

```bash
# Run a stress test with default settings
thinkbox stress --num-goals 20 --max-calls 100 --policy fair_share

# Run with custom parameters
thinkbox stress --num-goals 50 --max-calls 500 --policy priority --duration 120 --output results.json
```

### Programmatic Usage

```python
async def run_stress_test():
    config = StressTestConfig(
        num_goals=20,
        max_calls_global=100,
        contention_policy=BudgetContentionPolicy.PRIORITY,
        target_qps=20.0,
    )
    
    runner = StressTestRunner(ConcurrentGoalsRunner())
    result = await runner.run_stress_test(
        config=config,
        complete_async=my_complete_async,
    )
    
    print(f"Fairness Index: {result.fairness_index}")
    print(f"Total Calls: {result.total_calls}")
    print(f"Per-Goal Calls: {result.per_goal_calls}")

# Or use the ConcurrentGoalsRunner directly
runner = ConcurrentGoalsRunner()
result = await runner.run_stress_test(config, complete_async)
```

## Budget Contention Policies

### FAIR_SHARE
Divides the global budget equally among all goals. Unused budget from completed goals is redistributed equally.

### PRIORITY
Goals with higher priority values consume budget first. Lower priority goals only get budget if higher priority goals don't use their full allocation.

### FIFO
Goals consume budget in submission order. Earlier goals get priority access to the shared budget.

## Fairness Metrics

The framework computes several fairness metrics:

- **Jain's Fairness Index** (0-1): 1 = perfectly fair, lower = less fair
- **Gini Coefficient** (0-1): 0 = perfectly equal, 1 = maximally unequal
- **Coefficient of Variation**: Standard deviation / mean

## Persistence

Stress test results are automatically persisted via the ExperimentManager when a manager is provided:

```python
from thinkbox.experiment import ExperimentManager

manager = ExperimentManager()
result = await runner.run_stress_test(config, complete_async, manager=manager)
# Results are automatically persisted
```

## Dashboard Integration

Stress test results appear in the KUDBEE dashboard under the "Stress" tab, showing:

- Total runs and goals
- Total calls and retries
- Fairness index trends
- Per-goal call distribution
- Duration and peak concurrency

## Dynamic Budget Reallocation

The `BudgetReallocator` class enables dynamic reallocation of unused budget:

```python
from thinkbox.concurrent_goals import BudgetReallocator, BudgetContentionPolicy

reallocator = BudgetReallocator(
    policy=BudgetContentionPolicy.FAIR_SHARE,
    min_reallocation=2,
)

# Reallocate unused budget from completed goals
updated_limits = reallocator.reallocate(
    global_session=session,
    goal_budget_limits=limits,
    goal_budget_consumed=consumed,
    goal_status={"goal-1": "completed", "goal-2": "running"},
)
```

## Fairness Metrics

The framework provides several fairness metrics:

```python
from thinkbox.concurrent_goals import compute_fairness_metrics

metrics = compute_fairness_metrics([10, 10, 10, 10])  # Perfect fairness
# {'jain_fairness_index': 1.0, 'gini_coefficient': 0.0, ...}

metrics = compute_fairness_metrics([100, 1, 1, 1])  # Unequal
# {'jain_fairness_index': 0.25, 'gini_coefficient': 0.75, ...}
```

Available metrics:
- `jain_fairness_index`: 0-1, higher is fairer
- `gini_coefficient`: 0-1, lower is more equal
- `coefficient_of_variation`: std/mean ratio
- `min`, `max`, `mean`: Basic statistics

## Persistence

Stress test results are automatically persisted via `persist_stress_test()` or `StressTestRunner.persist()`:

```python
from thinkbox.experiment import ExperimentManager

manager = ExperimentManager()
result = await runner.run_stress_test(config, complete_async)
persisted = runner.persist(manager, result)
print(f"Persisted as: {persisted['run_experiment_id']}")
```

## Dashboard Integration

The KUDBEE dashboard (`/api/pipeline` and Pipeline HTML tab) now includes a "Stress" block showing:
- All stress test runs
- Per-run fairness metrics
- Per-goal call distribution
- Duration and peak concurrency

## API Reference

### StressTestConfig
```python
StressTestConfig(
    num_goals=10,
    max_calls_global=50,
    max_retries_global=1,
    contention_policy=BudgetContentionPolicy.FAIR_SHARE,
    goal_factory=None,
    max_duration_seconds=60.0,
    target_qps=None,
)
```

### StressTestResult
```python
StressTestResult(
    config=StressTestConfig(...),
    total_calls=100,
    total_retries=5,
    total_budget_exhausted=0,
    goal_results={},
    per_goal_calls={"goal-1": 5, "goal-2": 3},
    per_goal_retries={"goal-1": 1, "goal-2": 0},
    fairness_index=0.95,
    duration_seconds=5.2,
    peak_concurrency=5,
    completed_goals=10,
    failed_goals=0,
)
```

### StressTestRunner
```python
runner = StressTestRunner(ConcurrentGoalsRunner())
result = await runner.run_stress_test(config, complete_async, manager=manager)
runner.persist(manager, result)

# Or use context manager
async with StressTestRunner() as runner:
    result = await runner.run_stress_test(config, complete_async)
```

### StressTestConfig Serialization
```python
config = StressTestConfig(num_goals=20, max_calls_global=100)
data = config.to_dict()
config2 = StressTestConfig.from_dict(data)
```

### StressTestResult Serialization
```python
result = StressTestResult(config=config, total_calls=100, ...)
data = result.to_dict()
result2 = StressTestResult.from_dict(data)

# Compare results
if result.is_better_than(other_result):
    print("This result is better!")
```