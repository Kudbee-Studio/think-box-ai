#!/usr/bin/env python3
"""
Example: Running a Concurrency Stress Test

This example demonstrates how to use the StressTestRunner to run
a concurrency stress test with different budget contention policies.
"""

import asyncio
import json
from thinkbox.concurrent_goals import (
    ConcurrentGoalsRunner, ConcurrentGoalSpec, ConcurrentGoalsConfig,
    StressTestConfig, StressTestRunner, BudgetContentionPolicy,
)
from thinkbox.pop_arena import system_prompt_for_v2, VerifiedRetryConfig


def _sub(family: str, variant: str, depends_on=None):
    prompt, spec = system_prompt_for_v2(family, variant)
    return {"description": prompt, "family": family, "variant": variant,
            "spec": spec, "depends_on": depends_on or []}


def _router(subtasks, behaviors):
    calls = {}
    async def complete(prompt):
        for i, st in enumerate(subtasks):
            if prompt.startswith(st["description"]):
                break
        else:
            raise AssertionError("unrouted prompt")
        key = st["description"]
        calls[key] = calls.get(key, 0) + 1
        n = calls[key]
        fam, var, spec = st["family"], st["variant"], st["spec"]
        behavior = behaviors.get(i, "valid")
        from thinkbox.pop_arena import deterministic_emission_v2
        valid = deterministic_emission_v2(fam, var, spec)
        wrongkey = '{"result": %s}' % spec["expected"]
        if behavior == "valid":
            return valid
        if behavior == "wrongkey_then_valid":
            return wrongkey if n == 1 else valid
        raise AssertionError(behavior)
    return complete, calls


async def run_stress_example():
    """Run a comprehensive stress test example."""
    
    # Define subtasks
    g1 = [_sub("compute", "add_small")]
    g2 = [_sub("compute", "mul_small")]
    g3 = [_sub("compute", "sub_neg")]
    g4 = [_sub("distractor", "wrongkey")]
    complete, _ = _router(g1 + g2 + g3 + g4, {3: "wrongkey_then_valid"})
    
    # Example 1: FAIR_SHARE policy
    print("=" * 60)
    print("Example 1: FAIR_SHARE policy")
    print("=" * 60)
    
    config = StressTestConfig(
        num_goals=10,
        max_calls_global=50,
        max_retries_global=1,
        contention_policy=BudgetContentionPolicy.FAIR_SHARE,
        target_qps=20.0,
    )
    
    runner = StressTestRunner(ConcurrentGoalsRunner())
    result = await runner.run_stress_test(config, lambda p: asyncio.sleep(0.001) or '{"answer": 42}')
    
    print(f"Total Calls: {result.total_calls}")
    print(f"Fairness Index: {result.fairness_index}")
    print(f"Duration: {result.duration_seconds:.3f}s")
    print(f"Peak Concurrency: {result.peak_concurrency}")
    print(f"Per-Goal Calls: {result.per_goal_calls}")
    
    # Example 2: PRIORITY policy
    print("\n" + "=" * 60)
    print("Example 2: PRIORITY policy")
    print("=" * 60)
    
    config2 = StressTestConfig(
        num_goals=5,
        max_calls_global=20,
        contention_policy=BudgetContentionPolicy.PRIORITY,
        goal_factory=lambda i: ConcurrentGoalSpec(
            goal=f"priority-goal-{i}",
            subtasks=[{"description": _sub("compute", "add_small")["description"],
                      "family": "compute", "variant": "add_small",
                      "spec": _sub("compute", "add_small")["spec"],
                      "depends_on": []}],
            budget_config=VerifiedRetryConfig(max_calls=10, max_retries=1),
            priority=10 - i,  # Higher priority for lower index
        ),
    )
    
    result2 = await StressTestRunner(ConcurrentGoalsRunner()).run_stress_test(
        config2, lambda p: asyncio.sleep(0.001) or '{"answer": 42}')
    
    print(f"Total Calls: {result2.total_calls}")
    print(f"Fairness Index: {result2.fairness_index}")
    print(f"Per-Goal Calls: {result2.per_goal_calls}")
    
    # Example 3: FIFO policy
    print("\n" + "=" * 60)
    print("Example 3: FIFO policy")
    print("=" * 60)
    
    config3 = StressTestConfig(
        num_goals=5,
        max_calls_global=15,
        contention_policy=BudgetContentionPolicy.FIFO,
        goal_factory=lambda i: ConcurrentGoalSpec(
            goal=f"fifo-goal-{i}",
            subtasks=[{"description": _sub("compute", "add_small")["description"],
                      "family": "compute", "variant": "add_small",
                      "spec": _sub("compute", "add_small")["spec"],
                      "depends_on": []}],
            budget_config=VerifiedRetryConfig(max_calls=10, max_retries=1),
        ),
    )
    
    result3 = await StressTestRunner(ConcurrentGoalsRunner()).run_stress_test(
        config3, lambda p: asyncio.sleep(0.001) or '{"answer": 42}')
    
    print(f"Total Calls: {result3.total_calls}")
    print(f"Fairness Index: {result3.fairness_index}")
    print(f"Per-Goal Calls: {result3.per_goal_calls}")
    
    # Compare results
    print("\n" + "=" * 60)
    print("Comparison")
    print("=" * 60)
    
    runner = StressTestRunner()
    comparison = runner.compare_results(result, result2)
    print(f"FAIR_SHARE vs PRIORITY:")
    print(f"  Fairness diff: {comparison['fairness_difference']}")
    print(f"  Calls diff: {comparison['calls_difference']}")
    print(f"  Fairness winner: {comparison['fairness_winner']}")
    print(f"  Efficiency winner: {comparison['efficiency_winner']}")
    
    # Save results
    output = {
        "fair_share": result.to_dict(),
        "priority": result2.to_dict(),
        "fifo": result3.to_dict(),
    }
    
    with open("stress_test_results.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print("\nResults saved to stress_test_results.json")


if __name__ == "__main__":
    asyncio.run(run_stress_example())