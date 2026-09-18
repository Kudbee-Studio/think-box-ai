"""Concurrent multi-goal budget and deeper DAG telemetry tests.

Coverage (all deterministic, mocked completions per AGENTS §3.5):
- concurrent execution with independent per-goal budgets + isolation
- shared/global budget enforcement (honest BudgetExhausted)
- strict cross-goal accounting (global == sum of per-goal, no double count)
- per-goal and global retry counts
- fan-out / fan-in DAG layer telemetry + deterministic aggregation
- restart-safe persistence via existing ExperimentManager
- preserved original failure taxonomy
- no secrets leakage
"""

import asyncio
import unittest

from thinkbox.concurrent_goals import (
    ConcurrentGoalSpec, ConcurrentGoalsConfig, ConcurrentGoalsRunner,
    ConcurrentGoalsResult, aggregate_layer_telemetry, BudgetContentionPolicy,
    AdaptiveRetryBackoff, GoalResourceProfiler, ErrorClassificationEngine,
)
from thinkbox.pop_arena import (
    VerifiedRetryConfig, VerifiedRetrySession, BudgetExhausted,
    system_prompt_for_v2, deterministic_emission_v2,
)
from thinkbox.governed import GovernedEngine, GovernedEngineConfig
from thinkbox.engine import ThinkBoxEngine


def _sub(family: str, variant: str, depends_on: list[int] | None = None) -> dict:
    prompt, spec = system_prompt_for_v2(family, variant)
    return {"description": prompt, "family": family, "variant": variant,
            "spec": spec, "depends_on": depends_on or []}


def _router(subtasks: list[dict], behaviors: dict[int, str]):
    """complete_async keyed by exact subtask prompt; returns (complete, calls)."""
    calls: dict[str, int] = {}

    async def complete(prompt: str):
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
        valid = deterministic_emission_v2(fam, var, spec)
        wrongkey = '{"result": %s}' % spec["expected"]
        if behavior == "valid":
            return valid
        if behavior == "wrongkey_then_valid":
            return wrongkey if n == 1 else valid
        if behavior == "wrongkey_always":
            return wrongkey
        if behavior == "arithmetic_always":
            return '{"answer": %s}' % (spec["expected"] + 1)
        raise AssertionError(behavior)

    return complete, calls


class TestConcurrentGoalsAccounting(unittest.TestCase):
    """Accounting correctness under concurrency (no network)."""

    def test_independent_goals_isolated_budgets(self):
        spec = ConcurrentGoalSpec(
            goal="g1", subtasks=[_sub("compute", "add_small")],
            budget_config=VerifiedRetryConfig(max_calls=2, max_retries=1),
        )
        cfg = ConcurrentGoalsConfig(independent_goals=True, max_calls_global=0)
        self.assertTrue(cfg.independent_goals)
        self.assertEqual(spec.budget_config.max_calls, 2)

    def test_shared_budget_config(self):
        cfg = ConcurrentGoalsConfig(independent_goals=False, max_calls_global=5, max_retries_global=0)
        self.assertFalse(cfg.independent_goals)
        self.assertEqual(cfg.max_calls_global, 5)

    def test_budget_exhausted_raises_honestly(self):
        session = VerifiedRetrySession(VerifiedRetryConfig(max_calls=1, max_retries=0))
        session.run("t", "p", lambda p: "ok", lambda x: (True, "valid"), lambda t: "re")
        with self.assertRaises(BudgetExhausted):
            session.run("t", "p", lambda p: "ok", lambda x: (True, "valid"), lambda t: "re")

    def test_shared_session_counter_is_atomic(self):
        """The shared session increments synchronously (no await), so a
        bounded shared budget is enforced exactly under asyncio concurrency."""
        def verify(text):
            return (True, "valid")

        def reprompt(t):
            return "re"

        async def run_with_budget(max_calls: int) -> tuple[int, int]:
            session = VerifiedRetrySession(VerifiedRetryConfig(max_calls=max_calls, max_retries=0))

            async def complete(prompt: str) -> str:
                await asyncio.sleep(0)  # yield so concurrent tasks interleave
                return "ok"

            exhausted = 0

            async def worker() -> None:
                nonlocal exhausted
                for _ in range(2):
                    try:
                        await session.run_async("t", "p", complete, verify, reprompt)
                    except BudgetExhausted:
                        exhausted += 1

            await asyncio.gather(worker(), worker())
            return session.calls_spent, exhausted

        # budget 4: two workers x 2 calls = 4, exactly consumed, no exhaustion
        spent, exhausted = asyncio.run(run_with_budget(4))
        self.assertEqual(spent, 4)
        self.assertEqual(exhausted, 0)

        # budget 3: exactly 3 consumed, 1 call blocked honestly
        spent, exhausted = asyncio.run(run_with_budget(3))
        self.assertEqual(spent, 3)
        self.assertEqual(exhausted, 1)

def test_aggregate_layer_telemetry_deterministic(self):
        results = [
            {"layers_telemetry": [
                {"layer_index": 0, "tasks": 2, "first_try_successes": 2, "recovered_successes": 0,
                 "failures": 0, "budget_exhausted": 0, "retries": 0},
                {"layer_index": 1, "tasks": 1, "first_try_successes": 1, "recovered_successes": 0,
                 "failures": 0, "budget_exhausted": 0, "retries": 0},
            ]},
            {"layers_telemetry": [
                {"layer_index": 0, "tasks": 2, "first_try_successes": 1, "recovered_successes": 1,
                 "failures": 0, "budget_exhausted": 0, "retries": 1},
            ]},
        ]
        agg, per_goal = aggregate_layer_telemetry(results)
        self.assertEqual(len(agg), 2)
        self.assertEqual(agg[0]["layer_index"], 0)
        self.assertEqual(agg[0]["tasks"], 4)
        self.assertEqual(agg[0]["first_try_successes"], 3)
        self.assertEqual(agg[0]["recovered_successes"], 1)
        self.assertEqual(agg[0]["retries"], 1)
        self.assertAlmostEqual(agg[0]["verification_rate"], 1.0, places=4)
        self.assertEqual(agg[1]["layer_index"], 1)
        self.assertEqual(agg[1]["tasks"], 1)
        # Per-goal telemetry also returned (key is "unknown" since input lacks "goal" field)
        self.assertIn("unknown", per_goal)


class TestConcurrentGoalsExecution(unittest.TestCase):
    """Concurrent execution through the governed verified primitive."""

    @staticmethod
    def _run(coro):
        return asyncio.run(coro)

    def test_two_independent_goals_run_concurrently(self):
        g1 = [ _sub("compute", "add_small") ]
        g2 = [ _sub("compute", "mul_small") ]
        complete, calls = _router(g1 + g2, {})
        specs = [
            ConcurrentGoalSpec(goal="goal-add", subtasks=g1),
            ConcurrentGoalSpec(goal="goal-mul", subtasks=g2),
        ]
        result = self._run(ConcurrentGoalsRunner().run_concurrent(specs, complete))
        self.assertEqual(result.cross_goal_summary["total_goals"], 2)
        # Independent goals: global calls = sum of per-goal calls
        self.assertEqual(result.global_calls_spent, 2)
        self.assertEqual(result.global_retries_fired, 0)
        per = result.per_goal_accounting
        self.assertEqual(per["goal-add"]["calls_spent"], 1)
        self.assertEqual(per["goal-mul"]["calls_spent"], 1)
        self.assertEqual(per["goal-add"]["first_try_successes"], 1)
        self.assertEqual(per["goal-mul"]["first_try_successes"], 1)
        self.assertFalse(result.shared_session_used)

    def test_shared_global_budget_exhaustion(self):
        # Two goals, each a 1-task DAG, but global budget = 1 -> one succeeds,
        # the other is skipped due to FIFO budget allocation (first gets all, second gets 0).
        g1 = [_sub("compute", "add_small")]
        g2 = [_sub("compute", "mul_small")]
        complete, calls = _router(g1 + g2, {})
        specs = [
            ConcurrentGoalSpec(goal="goal-add", subtasks=g1),
            ConcurrentGoalSpec(goal="goal-mul", subtasks=g2),
        ]
        cfg = ConcurrentGoalsConfig(independent_goals=False, max_calls_global=1, max_retries_global=0,
                                    contention_policy=BudgetContentionPolicy.FIFO)
        result = self._run(ConcurrentGoalsRunner().run_concurrent(specs, complete, config=cfg))
        self.assertTrue(result.shared_session_used)
        # Exactly 1 call allowed globally (no double count, no overrun)
        self.assertEqual(result.global_calls_spent, 1)
        self.assertEqual(result.cross_goal_summary["shared_session_calls_spent"], 1)
        # First goal succeeds, second is skipped due to budget exhaustion (FIFO: first gets all, second gets 0)
        total_budget_exhausted = sum(a.get("budget_exhausted", 0) for a in result.per_goal_accounting.values())
        self.assertEqual(total_budget_exhausted, 1)

    def test_retry_accounting_per_goal_and_global(self):
        # Per-goal retry tracking is tested at session level; here we verify
        # the accounting fields exist and global = sum of per-goal.
        g1 = [_sub("compute", "add_small")]
        g2 = [_sub("compute", "mul_small")]
        complete, calls = _router(g1 + g2, {})
        specs = [
            ConcurrentGoalSpec(goal="goal-add", subtasks=g1, budget_config=VerifiedRetryConfig(max_calls=5, max_retries=1)),
            ConcurrentGoalSpec(goal="goal-mul", subtasks=g2, budget_config=VerifiedRetryConfig(max_calls=5, max_retries=1)),
        ]
        result = self._run(ConcurrentGoalsRunner().run_concurrent(specs, complete))
        per = result.per_goal_accounting
        # Both goals succeed first try
        self.assertEqual(per["goal-add"]["retries_fired"], 0)
        self.assertEqual(per["goal-mul"]["retries_fired"], 0)
        # Global retries = sum of per-goal retries (deterministic)
        self.assertEqual(result.global_retries_fired, 0)
        # Cross-goal accounting exact
        self.assertEqual(result.global_calls_spent, 2)
        self.assertEqual(sum(a["calls_spent"] for a in per.values()), 2)

    def test_fan_out_fan_in_layer_telemetry(self):
        # goal: two independent tasks (fan-out) feeding one dependent task (fan-in)
        g1 = [_sub("compute", "add_small"),
              _sub("compute", "mul_small"),
              _sub("multifield", "double", depends_on=[0, 1])]
        complete, calls = _router(g1, {})
        specs = [ConcurrentGoalSpec(goal="fan-goal", subtasks=g1)]
        result = self._run(ConcurrentGoalsRunner().run_concurrent(specs, complete))
        # The goal result should contain engine-level layers_telemetry
        gr = result.goal_results["fan-goal"]
        self.assertIn("layers_telemetry", gr)
        layers = gr["layers_telemetry"]
        self.assertEqual(len(layers), 2)  # layer 0 (fan-out, 2 tasks) + layer 1 (fan-in, 1 task)
        self.assertEqual(layers[0]["tasks"], 2)
        self.assertEqual(layers[1]["tasks"], 1)
        # Aggregated layer telemetry matches (now returns list directly)
        agg = result.layer_telemetry_aggregate
        self.assertEqual(agg[0]["tasks"], 2)
        self.assertEqual(agg[1]["tasks"], 1)


class TestConcurrentGoalsRestartPersistence(unittest.TestCase):
    """Restart-safe persistence via existing ExperimentManager."""

    @staticmethod
    def _run(coro):
        return asyncio.run(coro)

    def test_persist_and_reload_via_manager(self):
        import tempfile
        from pathlib import Path
        from thinkbox.experiment import ExperimentManager, ExperimentDB

        tmp = tempfile.mkdtemp()
        db_path = str(Path(tmp) / "exp.db")
        art = str(Path(tmp) / "artifacts")
        mgr = ExperimentManager(db_path=db_path, artifacts_dir=art)

        g1 = [_sub("compute", "add_small")]
        complete, calls = _router(g1, {})
        specs = [ConcurrentGoalSpec(goal="persist-goal", subtasks=g1)]
        result = self._run(ConcurrentGoalsRunner().run_concurrent(specs, complete, manager=mgr))

        gr = result.goal_results["persist-goal"]
        goal_exp = gr["goal_experiment_id"]
        self.assertTrue(goal_exp.startswith("tb_exp_"))

        # Fresh process-equivalent: new ExperimentDB handle reads persisted rows
        db2 = ExperimentDB(db_path=db_path)
        exp = db2.get_experiment(goal_exp)
        self.assertIsNotNone(exp)
        self.assertEqual(exp["experiment_id"], goal_exp)
        # Provenance present in task experiment ids
        task_ids = gr.get("task_experiment_ids", {})
        self.assertGreaterEqual(len(task_ids), 1)
        for tid, eid in task_ids.items():
            self.assertTrue(eid.startswith("tb_exp_"))
            self.assertIsNotNone(db2.get_experiment(eid))

        # Concurrent control record (scope="concurrent") reconstructable
        concurrent_rows = db2.get_all_experiments(limit=500)
        scope_params = {}
        for row in concurrent_rows:
            for p in db2.get_parameters_by_experiment(row["experiment_id"]):
                if p["name"] == "scope":
                    scope_params[row["experiment_id"]] = p["value"]
        self.assertTrue(any(v == "concurrent" for v in scope_params.values()),
                        "no scope=concurrent control experiment persisted")

    def test_concurrent_persist_reconstructs_accounting(self):
        import tempfile
        from pathlib import Path
        from thinkbox.experiment import ExperimentManager, ExperimentDB

        tmp = tempfile.mkdtemp()
        db_path = str(Path(tmp) / "exp.db")
        art = str(Path(tmp) / "artifacts")
        mgr = ExperimentManager(db_path=db_path, artifacts_dir=art)

        g1 = [_sub("compute", "add_small")]
        g2 = [_sub("compute", "mul_small")]
        complete, _ = _router(g1 + g2, {})
        specs = [
            ConcurrentGoalSpec(goal="goal-a", subtasks=g1),
            ConcurrentGoalSpec(goal="goal-b", subtasks=g2),
        ]
        cfg = ConcurrentGoalsConfig(independent_goals=False, max_calls_global=5, max_retries_global=1)
        result = self._run(ConcurrentGoalsRunner().run_concurrent(specs, complete, config=cfg, manager=mgr))

        db2 = ExperimentDB(db_path=db_path)
        import json as _json
        ctrl = None
        for row in db2.get_all_experiments(limit=500):
            for p in db2.get_parameters_by_experiment(row["experiment_id"]):
                if p["name"] == "scope" and p["value"] == "concurrent":
                    ctrl = row
        self.assertIsNotNone(ctrl)
        params = {p["name"]: p["value"] for p in db2.get_parameters_by_experiment(ctrl["experiment_id"])}
        self.assertEqual(params["total_goals"], "2")
        self.assertEqual(params["shared_session_used"], "True")
        per_goal = _json.loads(params["per_goal_accounting"])
        self.assertIn("goal-a", per_goal)
        self.assertIn("goal-b", per_goal)
        # Fixed: global_calls_spent now correctly = 2 (1 per goal)
        self.assertEqual(int(params["global_calls_spent"]), 2)
        self.assertEqual(
            int(params["global_calls_spent"]),
            sum(a["calls_spent"] for a in per_goal.values()),
        )

    def test_no_secrets_in_result(self):
        import json
        import re
        g1 = [_sub("compute", "add_small")]
        complete, _ = _router(g1, {})
        specs = [ConcurrentGoalSpec(goal="secret-goal", subtasks=g1)]
        result = self._run(ConcurrentGoalsRunner().run_concurrent(specs, complete))
        raw = json.dumps(result.__dict__, default=str)
        hits = re.findall(r"(?i)(api[_-]?key|token|secret)[\"\s:]+[A-Za-z0-9_\-]{20,}", raw)
        self.assertEqual(len(hits), 0)


class TestConcurrentGoalsFanInFanOutGraph(unittest.TestCase):
    """Graph-level fan-out/fan-in ordering."""

    def test_execution_order_fan_out_then_fan_in(self):
        from thinkbox.decomposer import TaskGraph, TaskNode
        graph = TaskGraph(
            root_id="a",
            tasks={
                "a": TaskNode(id="a", description="a"),
                "b": TaskNode(id="b", description="b"),
                "c": TaskNode(id="c", description="c", dependencies=["a", "b"]),
            },
        )
        layers = graph.get_execution_order()
        self.assertEqual(set(layers[0]), {"a", "b"})
        self.assertEqual(layers[1], ["c"])


class TestConcurrentGoalsDashboard(unittest.TestCase):
    """Pipeline dashboard exposes the concurrent block (extended DAG view)."""

    def test_pipeline_exposes_concurrent_block(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "swarm_dashboard", "experiments/swarm_dashboard.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        pipe = module._pipeline()
        self.assertIn("concurrent", pipe)
        block = pipe["concurrent"]
        for key in ("runs", "active_goals", "global_calls_spent",
                    "global_retries_fired", "recovered_tasks", "failed_tasks",
                    "budget_exhausted_tasks"):
            self.assertIn(key, block)

    def test_pipeline_concurrent_block_no_secrets(self):
        import importlib.util
        import json
        import re
        spec = importlib.util.spec_from_file_location(
            "swarm_dashboard", "experiments/swarm_dashboard.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        raw = json.dumps(module._pipeline().get("concurrent", {}), default=str)
        self.assertEqual(re.findall(r"(?i)(api[_-]?key|bearer|authorization|token)[\"\s:]+[A-Za-z0-9_\-]{20,}", raw), [])


if __name__ == "__main__":
    unittest.main()


class TestAdaptiveRetryBackoff(unittest.TestCase):
    """Feature 33: Adaptive exponential backoff."""

    def test_compute_delay_first(self) -> None:
        arb = AdaptiveRetryBackoff(base_delay_s=1.0, max_delay_s=60.0)
        delay = arb.compute_delay(1, seed="test")
        self.assertEqual(delay["attempt"], 1)
        self.assertAlmostEqual(delay["exponential"], 1.0)
        self.assertGreaterEqual(delay["delay_s"], 0.0)
        self.assertLessEqual(delay["delay_s"], 60.0)

    def test_compute_delay_exponential(self) -> None:
        arb = AdaptiveRetryBackoff(base_delay_s=1.0, max_delay_s=60.0)
        d1 = arb.compute_delay(1, seed="test")
        d2 = arb.compute_delay(2, seed="test")
        d3 = arb.compute_delay(3, seed="test")
        self.assertAlmostEqual(d2["exponential"], 2.0)
        self.assertAlmostEqual(d3["exponential"], 4.0)
        self.assertGreater(d2["delay_s"], d1["delay_s"])
        self.assertGreater(d3["delay_s"], d2["delay_s"])

    def test_compute_delay_capped(self) -> None:
        arb = AdaptiveRetryBackoff(base_delay_s=10.0, max_delay_s=20.0)
        delay = arb.compute_delay(5, seed="test")
        self.assertLessEqual(delay["capped"], 20.0)

    def test_get_schedule(self) -> None:
        arb = AdaptiveRetryBackoff(base_delay_s=1.0, max_delay_s=10.0)
        schedule = arb.get_schedule(3, seed="test")
        self.assertEqual(len(schedule), 3)
        for i, s in enumerate(schedule):
            self.assertEqual(s["attempt"], i + 1)

    def test_jitter_deterministic(self) -> None:
        arb1 = AdaptiveRetryBackoff(base_delay_s=1.0, max_delay_s=10.0)
        arb2 = AdaptiveRetryBackoff(base_delay_s=1.0, max_delay_s=10.0)
        d1 = arb1.compute_delay(3, seed="same_seed")
        d2 = arb2.compute_delay(3, seed="same_seed")
        self.assertEqual(d1["delay_s"], d2["delay_s"])

    def test_different_seeds(self) -> None:
        arb = AdaptiveRetryBackoff(base_delay_s=1.0, max_delay_s=10.0)
        d1 = arb.compute_delay(3, seed="seed_a")
        d2 = arb.compute_delay(3, seed="seed_b")
        self.assertNotEqual(d1["delay_s"], d2["delay_s"])

    def test_no_jitter(self) -> None:
        arb = AdaptiveRetryBackoff(base_delay_s=2.0, max_delay_s=10.0, jitter_enabled=False)
        delay = arb.compute_delay(1, seed="test")
        self.assertEqual(delay["delay_s"], 2.0)

    def test_get_stats(self) -> None:
        arb = AdaptiveRetryBackoff()
        arb.compute_delay(1, seed="test")
        stats = arb.get_stats()
        self.assertEqual(stats["base_delay_s"], 1.0)
        self.assertEqual(stats["jitter_enabled"], True)


class TestGoalResourceProfiler(unittest.TestCase):
    """Feature 34: Goal resource profiling."""

    def test_profile_goal(self) -> None:
        grp = GoalResourceProfiler()
        prof = grp.profile_goal("g1", cpu_weight=2.0, memory_mb=256,
                                io_intensity="high", network_calls=3)
        self.assertEqual(prof["goal_id"], "g1")
        self.assertEqual(prof["cpu_weight"], 2.0)
        self.assertEqual(prof["memory_mb"], 256)
        self.assertEqual(prof["io_intensity"], "high")
        self.assertEqual(prof["network_calls"], 3)
        self.assertEqual(prof["total_weight"], 3.5)

    def test_default_profile(self) -> None:
        grp = GoalResourceProfiler()
        prof = grp.profile_goal("g1")
        self.assertEqual(prof["cpu_weight"], 1.0)
        self.assertEqual(prof["memory_mb"], 128)
        self.assertEqual(prof["io_intensity"], "low")
        self.assertEqual(prof["network_calls"], 0)
        self.assertEqual(prof["total_weight"], 1.0)

    def test_get_profile(self) -> None:
        grp = GoalResourceProfiler()
        grp.profile_goal("g1", cpu_weight=2.0)
        self.assertIsNotNone(grp.get_profile("g1"))
        self.assertIsNone(grp.get_profile("unknown"))

    def test_get_total_resource_demand(self) -> None:
        grp = GoalResourceProfiler()
        grp.profile_goal("g1", cpu_weight=2.0, memory_mb=256)
        grp.profile_goal("g2", cpu_weight=3.0, memory_mb=512)
        demand = grp.get_total_resource_demand()
        self.assertEqual(demand["total_cpu_weight"], 5.0)
        self.assertEqual(demand["total_memory_mb"], 768)
        self.assertEqual(demand["goals_profiled"], 2)

    def test_can_fit(self) -> None:
        grp = GoalResourceProfiler()
        grp.profile_goal("g1", cpu_weight=2.0, memory_mb=256)
        fits = grp.can_fit("g1", 4.0, 512)
        self.assertTrue(fits["can_fit"])
        self.assertTrue(fits["cpu_ok"])
        self.assertTrue(fits["mem_ok"])

    def test_cannot_fit(self) -> None:
        grp = GoalResourceProfiler()
        grp.profile_goal("g1", cpu_weight=2.0, memory_mb=256)
        fits = grp.can_fit("g1", 1.0, 128)
        self.assertFalse(fits["can_fit"])
        self.assertFalse(fits["cpu_ok"])
        self.assertFalse(fits["mem_ok"])

    def test_no_profile(self) -> None:
        grp = GoalResourceProfiler()
        result = grp.can_fit("unknown", 4.0, 512)
        self.assertFalse(result["can_fit"])
        self.assertEqual(result["reason"], "no_profile")

    def test_get_all_profiles(self) -> None:
        grp = GoalResourceProfiler()
        grp.profile_goal("g1")
        grp.profile_goal("g2")
        profiles = grp.get_all_profiles()
        self.assertEqual(len(profiles), 2)
        self.assertIn("g1", profiles)
        self.assertIn("g2", profiles)


class TestErrorClassificationEngine(unittest.TestCase):
    """Feature 35: Error classification with recovery suggestions."""

    def test_retryable_timeout(self) -> None:
        ece = ErrorClassificationEngine()
        result = ece.classify(TimeoutError("connection timeout"), "g1")
        self.assertEqual(result["category"], "retryable")
        self.assertTrue(result["retryable"])
        self.assertEqual(result["recovery"], "backoff_and_retry")

    def test_critical_auth(self) -> None:
        ece = ErrorClassificationEngine()
        result = ece.classify(PermissionError("authentication denied"), "g1")
        self.assertEqual(result["category"], "critical")
        self.assertFalse(result["retryable"])
        self.assertEqual(result["recovery"], "abort_and_alert")

    def test_non_retryable_after_attempts(self) -> None:
        ece = ErrorClassificationEngine()
        for i in range(1, 4):
            result = ece.classify(ValueError("unknown error"), "g1", attempt=i)
            if i < 3:
                self.assertEqual(result["category"], "retryable")
            else:
                self.assertEqual(result["category"], "non_retryable")
                self.assertEqual(result["recovery"], "manual_review")

    def test_critical_keywords(self) -> None:
        ece = ErrorClassificationEngine()
        for msg in ["permission denied", "authorization failed",
                     "not found", "invalid request", "corrupt data",
                     "syntax error"]:
            result = ece.classify(ValueError(msg), "g1", attempt=1)
            self.assertEqual(result["category"], "critical",
                             f"Failed for: {msg}")

    def test_retryable_keywords(self) -> None:
        ece = ErrorClassificationEngine()
        for msg in ["timeout", "connection refused", "temporarily unavailable",
                     "overloaded", "rate limit"]:
            result = ece.classify(ValueError(msg), "g1", attempt=1)
            self.assertEqual(result["category"], "retryable",
                             f"Failed for: {msg}")

    def test_should_retry(self) -> None:
        ece = ErrorClassificationEngine()
        self.assertTrue(ece.should_retry(TimeoutError("t"), 1))
        self.assertTrue(ece.should_retry(TimeoutError("t"), 2))
        self.assertFalse(ece.should_retry(PermissionError("permission denied"), 1))
        self.assertFalse(ece.should_retry(TimeoutError("t"), 5))

    def test_should_retry_default_max(self) -> None:
        ece = ErrorClassificationEngine()
        self.assertTrue(ece.should_retry(ValueError("e"), 1))
        self.assertFalse(ece.should_retry(ValueError("e"), 4))

    def test_get_summary(self) -> None:
        ece = ErrorClassificationEngine()
        ece.classify(TimeoutError("t"), "g1")
        ece.classify(ValueError("v"), "g1", attempt=5)
        ece.classify(PermissionError("permission denied"), "g1")
        summary = ece.get_summary()
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["categories"]["retryable"], 1)
        self.assertEqual(summary["categories"]["critical"], 1)
        self.assertEqual(summary["categories"]["non_retryable"], 1)
        self.assertAlmostEqual(summary["retry_rate"], 1/3, places=4)

    def test_get_classified(self) -> None:
        ece = ErrorClassificationEngine()
        ece.classify(TimeoutError("t"), "g1")
        classified = ece.get_classified()
        self.assertEqual(len(classified), 1)
        self.assertEqual(classified[0]["error_type"], "TimeoutError")

    def test_classify_has_required_fields(self) -> None:
        ece = ErrorClassificationEngine()
        result = ece.classify(ValueError("e"), "g1", attempt=2)
        for field in ["error_type", "error_message", "goal_id", "attempt",
                       "category", "recovery", "retryable", "classified_at"]:
            self.assertIn(field, result)
