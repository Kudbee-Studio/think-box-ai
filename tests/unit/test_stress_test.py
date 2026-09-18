"""Stress testing framework tests."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from thinkbox.concurrent_goals import (
    StressTestConfig, StressTestResult, StressTestRunner,
    ConcurrentGoalSpec, ConcurrentGoalsConfig, ConcurrentGoalsRunner,
    BudgetContentionPolicy, compute_jain_fairness_index,
    compute_gini_coefficient, compute_coefficient_of_variation,
    compute_fairness_metrics,
)
from thinkbox.pop_arena import VerifiedRetryConfig, system_prompt_for_v2
from thinkbox.concurrent_goals import ConcurrentGoalSpec


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


class TestStressTestConfig(unittest.TestCase):
    """Test StressTestConfig dataclass."""

    def test_default_config(self):
        config = StressTestConfig()
        self.assertEqual(config.num_goals, 10)
        self.assertEqual(config.max_calls_global, 50)
        self.assertEqual(config.max_retries_global, 1)
        self.assertEqual(config.contention_policy, BudgetContentionPolicy.FAIR_SHARE)

    def test_custom_config(self):
        config = StressTestConfig(
            num_goals=20,
            max_calls_global=100,
            contention_policy=BudgetContentionPolicy.PRIORITY,
        )
        self.assertEqual(config.num_goals, 20)
        self.assertEqual(config.max_calls_global, 100)
        self.assertEqual(config.contention_policy, BudgetContentionPolicy.PRIORITY)


class TestStressTestResult(unittest.TestCase):
    """Test StressTestResult dataclass."""

    def test_default_result(self):
        config = StressTestConfig()
        result = StressTestResult(config=config)
        self.assertEqual(result.config.num_goals, 10)
        self.assertEqual(result.total_calls, 0)

    def test_result_with_values(self):
        config = StressTestConfig()
        result = StressTestResult(
            config=config,
            total_calls=100,
            total_retries=5,
            fairness_index=0.95,
        )
        self.assertEqual(result.total_calls, 100)
        self.assertEqual(result.total_retries, 5)
        self.assertEqual(result.fairness_index, 0.95)


class TestFairnessMetrics(unittest.TestCase):
    """Test fairness metrics computation."""

    def test_jain_fairness_perfect(self):
        values = [10, 10, 10, 10]
        fi = compute_jain_fairness_index(values)
        self.assertAlmostEqual(fi, 1.0, places=4)

    def test_jain_fairness_unequal(self):
        values = [10, 0, 0, 0]
        fi = compute_jain_fairness_index(values)
        self.assertAlmostEqual(fi, 0.25, places=2)

    def test_gini_coefficient_perfect(self):
        values = [10, 10, 10, 10]
        gini = compute_gini_coefficient(values)
        self.assertAlmostEqual(gini, 0.0, places=4)

    def test_gini_coefficient_unequal(self):
        values = [10, 0, 0, 0]
        gini = compute_gini_coefficient(values)
        self.assertAlmostEqual(gini, 0.75, places=2)

    def test_cv_perfect(self):
        values = [10, 10, 10, 10]
        cv = compute_coefficient_of_variation(values)
        self.assertAlmostEqual(cv, 0.0, places=4)

    def test_fairness_metrics_complete(self):
        values = [10, 10, 10, 10]
        metrics = compute_fairness_metrics(values)
        self.assertIn("jain_fairness_index", metrics)
        self.assertIn("gini_coefficient", metrics)
        self.assertIn("coefficient_of_variation", metrics)
        self.assertEqual(metrics["jain_fairness_index"], 1.0)
        self.assertEqual(metrics["gini_coefficient"], 0.0)


class TestStressTestRunner(unittest.TestCase):
    """Test StressTestRunner."""

    @staticmethod
    def _run(coro):
        return asyncio.run(coro)

    def test_stress_test_runner_creation(self):
        runner = StressTestRunner()
        self.assertIsNotNone(runner.concurrent_runner)

    def test_default_goal_factory(self):
        runner = StressTestRunner()
        goal = runner._default_goal_factory(0)
        self.assertIsInstance(goal, ConcurrentGoalSpec)
        self.assertEqual(goal.goal, "stress-goal-0")
        self.assertEqual(len(goal.subtasks), 1)
        self.assertIsNotNone(goal.budget_config)

    def test_aggregate_results(self):
        runner = StressTestRunner()
        config = StressTestConfig(num_goals=2)
        # Mock ConcurrentGoalsResult
        from thinkbox.concurrent_goals import ConcurrentGoalsResult
        mock_result = ConcurrentGoalsResult(
            goal_results={},
            per_goal_accounting={
                "goal-0": {"calls_spent": 5, "retries_fired": 1, "execution_status": "verified"},
                "goal-1": {"calls_spent": 3, "retries_fired": 0, "execution_status": "verified"},
            },
            cross_goal_summary={
                "global_calls_spent": 8,
                "global_retries_fired": 1,
                "shared_session_calls_spent": 8,
            },
            layer_telemetry_aggregate=[],
            global_calls_spent=8,
            global_retries_fired=1,
            global_budget_remaining=10,
            shared_session_used=True,
            proof_paths=[],
        )
        result = runner._aggregate_results(
            StressTestConfig(num_goals=2), mock_result, 1.5
        )
        self.assertEqual(result.total_calls, 8)
        self.assertEqual(result.total_retries, 1)
        self.assertEqual(result.completed_goals, 2)
        self.assertEqual(result.failed_goals, 0)
        self.assertGreater(result.fairness_index, 0)


class TestStressTestRunnerIntegration(unittest.TestCase):
    """Integration tests for StressTestRunner."""

    @staticmethod
    def _run(coro):
        return asyncio.run(coro)

    def test_run_stress_test_mock(self):
        """Test running a stress test with mocked complete_async."""
        from thinkbox.concurrent_goals import StressTestRunner, StressTestConfig
        from thinkbox.pop_arena import system_prompt_for_v2, VerifiedRetryConfig

        def _sub(family: str, variant: str):
            prompt, spec = system_prompt_for_v2(family, variant)
            return {"description": prompt, "family": family, "variant": variant,
                    "spec": spec, "depends_on": []}

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
                raise AssertionError(behavior)
            return complete, calls

        async def test():
            g1 = [_sub("compute", "add_small")]
            g2 = [_sub("compute", "mul_small")]
            complete, calls = _router(g1 + g2, {})
            specs = [
                ConcurrentGoalSpec(goal="goal-a", subtasks=g1, budget_config=VerifiedRetryConfig(max_calls=5, max_retries=1)),
                ConcurrentGoalSpec(goal="goal-b", subtasks=g2, budget_config=VerifiedRetryConfig(max_calls=5, max_retries=1)),
            ]
            cfg = ConcurrentGoalsConfig(independent_goals=False, max_calls_global=10, max_retries_global=1)
            runner = StressTestRunner()
            result = await runner.concurrent_runner.run_concurrent(specs, complete, config=ConcurrentGoalsConfig(
                independent_goals=False, max_calls_global=10, max_retries_global=1
            ))
            return result

        result = self._run(test())
        self.assertEqual(result.global_calls_spent, 2)

    def test_run_stress_test_method(self):
        """Test the run_stress_test method directly."""
        from thinkbox.concurrent_goals import StressTestRunner, StressTestConfig
        from thinkbox.pop_arena import system_prompt_for_v2, VerifiedRetryConfig

        def _sub(family: str, variant: str):
            prompt, spec = system_prompt_for_v2(family, variant)
            return {"description": prompt, "family": family, "variant": variant,
                    "spec": spec, "depends_on": []}

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
                raise AssertionError(behavior)
            return complete, calls

        async def test():
            g1 = [_sub("compute", "add_small")]
            g2 = [_sub("compute", "mul_small")]
            complete, calls = _router(g1 + g2, {})
            config = StressTestConfig(
                num_goals=2,
                max_calls_global=10,
                contention_policy=BudgetContentionPolicy.FAIR_SHARE,
                goal_factory=lambda i: ConcurrentGoalSpec(
                    goal=f"goal-{i}",
                    subtasks=[_sub("compute", "add_small")],
                    budget_config=VerifiedRetryConfig(max_calls=5, max_retries=1),
                ),
            )
            runner = StressTestRunner()
            result = await runner.run_stress_test(config, complete)
            return result

        result = self._run(test())
        self.assertEqual(result.total_calls, 2)


if __name__ == "__main__":
    unittest.main()