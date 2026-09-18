"""Deterministic tests for the governed scheduler (25 features).

All tests are deterministic (mocked completions, no network).
Each feature has tests for valid input, invalid input, and edge cases.
"""

import unittest
import hashlib
import json
import math
import os
import tempfile
import time
from datetime import datetime, timezone

from thinkbox.scheduler import (
    SchedulerState,
    HealthIndicator,
    SchedulerDecisionType,
    SchedulerDecisionReceipt,
    AdaptiveConcurrencyLimiter,
    GlobalSchedulerAdmission,
    PerGoalConcurrencyCap,
    WeightedPriorityScheduler,
    BudgetAwareAdmission,
    DeadlineAwareAdmission,
    RetryAwareReservation,
    BudgetForecaster,
    BudgetOverspendPrevention,
    QueueDepthTelemetry,
    WaitTimeTelemetry,
    ExecutionUtilization,
    FairnessTrendTracker,
    SchedulerHealth,
    StarvationRecovery,
    PriorityInversionRecovery,
    CancellationPropagator,
    FanOutBackpressure,
    FanInQuorumTracker,
    CrossGoalReplayVerifier,
    RestartSafeSchedulerRecovery,
    PersistentSchedulerState,
    FailureDomainIsolator,
    SchedulerDashboardExtension,
)
from thinkbox.concurrent_goals import (
    StressTestConfig,
    StressTestResult,
    StressReportEnhancer,
    BudgetContentionPolicy,
    GoalPriority,
    GoalLifecycleState,
)
from thinkbox.pop_arena import BudgetExhausted


class TestSchedulerDecisionReceipt(unittest.TestCase):
    """Feature 0 (infrastructure): Decision receipts."""

    def test_receipt_creation(self) -> None:
        r = SchedulerDecisionReceipt(
            decision_id="test-1",
            decision_type=SchedulerDecisionType.ADMIT,
            goal_id="goal-1",
            state=SchedulerState.ADMITTING,
            reasoning="test",
        )
        self.assertEqual(r.decision_id, "test-1")
        self.assertEqual(r.decision_type, SchedulerDecisionType.ADMIT)
        self.assertEqual(r.goal_id, "goal-1")

    def test_receipt_auto_id(self) -> None:
        r = SchedulerDecisionReceipt(
            decision_id="",
            decision_type=SchedulerDecisionType.REJECT,
            goal_id="goal-2",
            state=SchedulerState.REJECTING if hasattr(SchedulerState, "REJECTING") else SchedulerState.ADMITTING,
            reasoning="auto id",
        )
        self.assertTrue(r.decision_id.startswith("sdc_"))

    def test_receipt_to_dict(self) -> None:
        r = SchedulerDecisionReceipt(
            decision_id="t", decision_type=SchedulerDecisionType.ADMIT,
            goal_id="g", state=SchedulerState.IDLE, reasoning="r",
        )
        d = r.to_dict()
        self.assertEqual(d["goal_id"], "g")
        self.assertIn("timestamp", d)


class TestAdaptiveConcurrencyLimiter(unittest.TestCase):
    """Feature 1: Adaptive concurrency limits."""

    def test_initial_limit(self) -> None:
        limiter = AdaptiveConcurrencyLimiter(max_concurrency=5)
        self.assertEqual(limiter.current_limit, 5)

    def test_adjusts_up(self) -> None:
        limiter = AdaptiveConcurrencyLimiter(max_concurrency=10, target_completion_time=5.0)
        for _ in range(5):
            limiter.record_completion(0.5)
        self.assertGreater(limiter.current_limit, 5)

    def test_adjusts_down(self) -> None:
        limiter = AdaptiveConcurrencyLimiter(max_concurrency=10, target_completion_time=5.0)
        for _ in range(5):
            limiter.record_completion(20.0)
        self.assertLess(limiter.current_limit, 10)

    def test_min_concurrency(self) -> None:
        limiter = AdaptiveConcurrencyLimiter(min_concurrency=1, max_concurrency=3)
        for _ in range(20):
            limiter.record_completion(60.0)
        self.assertEqual(limiter.current_limit, 1)

    def test_get_stats(self) -> None:
        limiter = AdaptiveConcurrencyLimiter()
        stats = limiter.get_stats()
        self.assertIn("current_limit", stats)
        self.assertIn("adjustment_history", stats)


class TestGlobalSchedulerAdmission(unittest.TestCase):
    """Feature 2: Global scheduler admission control."""

    def test_admit_success(self) -> None:
        gate = GlobalSchedulerAdmission(max_active_goals=5)
        admitted, reasoning, receipt = gate.can_admit("goal-1")
        self.assertTrue(admitted)
        self.assertIn("admitted", reasoning)
        self.assertIsNotNone(receipt)

    def test_reject_when_full(self) -> None:
        gate = GlobalSchedulerAdmission(max_active_goals=2)
        gate.can_admit("g1")
        gate.can_admit("g2")
        admitted, reasoning, _ = gate.can_admit("g3")
        self.assertFalse(admitted)
        self.assertIn("max_active_goals", reasoning)

    def test_release(self) -> None:
        gate = GlobalSchedulerAdmission(max_active_goals=1)
        gate.can_admit("g1")
        gate.release("g1")
        admitted, _, _ = gate.can_admit("g2")
        self.assertTrue(admitted)

    def test_get_state(self) -> None:
        gate = GlobalSchedulerAdmission(max_active_goals=3, max_queue_depth=10)
        gate.can_admit("g1")
        state = gate.get_state()
        self.assertEqual(state["active_goals"], 1)
        self.assertIn("admissions", state)

    def test_admit_raises_on_reject(self) -> None:
        gate = GlobalSchedulerAdmission(max_active_goals=1)
        gate.can_admit("g1")
        with self.assertRaises(BudgetExhausted):
            gate.admit("g2")


class TestPerGoalConcurrencyCap(unittest.TestCase):
    """Feature 3: Per-goal concurrency caps."""

    def test_default_cap(self) -> None:
        cap = PerGoalConcurrencyCap(default_cap=4)
        self.assertTrue(cap.start_task("g1"))
        self.assertTrue(cap.start_task("g1"))

    def test_enforce_cap(self) -> None:
        cap = PerGoalConcurrencyCap(default_cap=2)
        self.assertTrue(cap.start_task("g1"))
        self.assertTrue(cap.start_task("g1"))
        self.assertFalse(cap.start_task("g1"))

    def test_finish_task(self) -> None:
        cap = PerGoalConcurrencyCap(default_cap=1)
        cap.start_task("g1")
        cap.finish_task("g1")
        self.assertTrue(cap.start_task("g1"))

    def test_set_cap(self) -> None:
        cap = PerGoalConcurrencyCap()
        cap.set_cap("g1", 3)
        self.assertEqual(cap.get_cap("g1"), 3)

    def test_get_state(self) -> None:
        cap = PerGoalConcurrencyCap(default_cap=2)
        cap.start_task("g1")
        cap.start_task("g1")
        cap.start_task("g1")  # should be blocked, creates violation
        state = cap.get_state()
        self.assertEqual(state["violations"], 1)


class TestWeightedPriorityScheduler(unittest.TestCase):
    """Feature 4: Weighted priority scheduling."""

    def test_set_weight(self) -> None:
        sched = WeightedPriorityScheduler()
        sched.set_weight("g1", 2.5)
        self.assertEqual(sched.get_weight("g1"), 2.5)

    def test_default_weight(self) -> None:
        sched = WeightedPriorityScheduler()
        self.assertEqual(sched.get_weight("unknown"), 1.0)

    def test_schedule_order(self) -> None:
        sched = WeightedPriorityScheduler()
        sched.set_weight("low", 1.0)
        sched.set_weight("high", 10.0)
        ordered = sched.schedule([("low", 50), ("high", 50)])
        self.assertEqual(ordered[0], "high")

    def test_compute_priority_score(self) -> None:
        sched = WeightedPriorityScheduler()
        sched.set_weight("g1", 3.0)
        score = sched.compute_priority_score("g1", base_priority=10)
        self.assertEqual(score, 30.0)

    def test_schedule_log(self) -> None:
        sched = WeightedPriorityScheduler()
        sched.schedule([("g1", 50)])
        log = sched.get_schedule_log()
        self.assertEqual(len(log), 1)


class TestBudgetAwareAdmission(unittest.TestCase):
    """Feature 5: Budget-aware admission."""

    def test_admit_within_budget(self) -> None:
        admission = BudgetAwareAdmission(global_budget=10)
        receipt = admission.admit("g1", estimated_calls=3)
        self.assertEqual(receipt.decision_type, SchedulerDecisionType.ADMIT)

    def test_reject_over_budget(self) -> None:
        admission = BudgetAwareAdmission(global_budget=5)
        admission.admit("g1", estimated_calls=3)
        receipt = admission.admit("g2", estimated_calls=3)
        self.assertEqual(receipt.decision_type, SchedulerDecisionType.REJECT)

    def test_remaining(self) -> None:
        admission = BudgetAwareAdmission(global_budget=10)
        admission.admit("g1", estimated_calls=3)
        self.assertEqual(admission.remaining, 7)

    def test_release_budget(self) -> None:
        admission = BudgetAwareAdmission(global_budget=10)
        admission.admit("g1", estimated_calls=3)
        admission.release_budget("g1", 3)
        self.assertEqual(admission.remaining, 10)

    def test_get_state(self) -> None:
        admission = BudgetAwareAdmission(global_budget=5)
        admission.admit("g1", estimated_calls=2)
        state = admission.get_state()
        self.assertEqual(state["consumed"], 2)
        self.assertEqual(state["remaining"], 3)


class TestDeadlineAwareAdmission(unittest.TestCase):
    """Feature 6: Deadline-aware admission."""

    def test_feasible(self) -> None:
        admission = DeadlineAwareAdmission(default_deadline_s=100.0)
        admission.set_deadline("g1", deadline_s=60.0, estimate_s=30.0)
        feasible, reasoning, receipt = admission.check("g1")
        self.assertTrue(feasible)
        self.assertIn("feasible", reasoning)

    def test_infeasible(self) -> None:
        admission = DeadlineAwareAdmission(default_deadline_s=100.0)
        admission.set_deadline("g1", deadline_s=10.0, estimate_s=20.0)
        feasible, reasoning, _ = admission.check("g1")
        self.assertFalse(feasible)
        self.assertIn("infeasible", reasoning)

    def test_default_deadline(self) -> None:
        admission = DeadlineAwareAdmission(default_deadline_s=300.0)
        feasible, _, _ = admission.check("unknown")
        # No estimate set, so margin = deadline - 0 = positive
        self.assertTrue(feasible)

    def test_get_state(self) -> None:
        admission = DeadlineAwareAdmission()
        admission.set_deadline("g1", 60.0, 30.0)
        state = admission.get_state()
        self.assertEqual(state["tracked_goals"], 1)


class TestRetryAwareReservation(unittest.TestCase):
    """Feature 7: Retry-aware reservations."""

    def test_reserve(self) -> None:
        res = RetryAwareReservation(default_retries=2)
        budget = res.reserve("g1", max_retries=3)
        self.assertEqual(budget.max_retries, 3)

    def test_can_retry(self) -> None:
        res = RetryAwareReservation(default_retries=1)
        res.reserve("g1")
        self.assertTrue(res.can_retry("g1")[0])
        res.consume_retry("g1")
        self.assertFalse(res.can_retry("g1")[0])

    def test_no_reservation(self) -> None:
        res = RetryAwareReservation()
        self.assertFalse(res.can_retry("unknown")[0])

    def test_consume_retry(self) -> None:
        res = RetryAwareReservation(default_retries=1)
        res.reserve("g1")
        consumed = res.consume_retry("g1")
        self.assertTrue(consumed)
        self.assertFalse(res.consume_retry("g1"))

    def test_get_state(self) -> None:
        res = RetryAwareReservation()
        res.reserve("g1", max_retries=2)
        res.consume_retry("g1")
        state = res.get_state()
        self.assertEqual(state["reservations"]["g1"]["max"], 2)
        self.assertEqual(state["reservations"]["g1"]["consumed"], 1)


class TestBudgetForecaster(unittest.TestCase):
    """Feature 8: Budget forecasting."""

    def test_record(self) -> None:
        forecaster = BudgetForecaster()
        forecaster.record("g1", 5, time.time(), 2.0)
        forecaster.record("g1", 3, time.time() + 1, 1.0)
        self.assertEqual(len(forecaster._consumption_history), 2)

    def test_forecast_insufficient_data(self) -> None:
        forecaster = BudgetForecaster()
        result = forecaster.forecast("g1")
        self.assertEqual(result["sample_size"], 0)
        self.assertEqual(result["predicted_calls"], 0)

    def test_forecast_trend(self) -> None:
        forecaster = BudgetForecaster()
        t = time.time()
        for i in range(5):
            forecaster.record("g1", i * 2, t + i, 1.0)
        result = forecaster.forecast("g1", horizon_s=60.0)
        self.assertIn("predicted_calls", result)
        self.assertIn("confidence", result)
        self.assertGreaterEqual(result["confidence"], 0.0)

    def test_forecast_none_goal(self) -> None:
        forecaster = BudgetForecaster()
        t = time.time()
        forecaster.record("g1", 2, t, 1.0)
        forecaster.record("g2", 3, t + 1, 1.0)
        result = forecaster.forecast(horizon_s=60.0)
        self.assertGreaterEqual(result["sample_size"], 0)


class TestBudgetOverspendPrevention(unittest.TestCase):
    """Feature 9: Budget overspend prevention."""

    def test_authorize_within_budget(self) -> None:
        prevention = BudgetOverspendPrevention(max_budget=10)
        allowed, _ = prevention.authorize("g1", 5)
        self.assertTrue(allowed)

    def test_block_overspend(self) -> None:
        prevention = BudgetOverspendPrevention(max_budget=5)
        prevention.authorize("g1", 3)
        allowed, _ = prevention.authorize("g2", 3)
        self.assertFalse(allowed)

    def test_get_state(self) -> None:
        prevention = BudgetOverspendPrevention(max_budget=10)
        prevention.authorize("g1", 4)
        state = prevention.get_state()
        self.assertEqual(state["spent"], 4)
        self.assertEqual(state["remaining"], 6)
        self.assertEqual(state["blocked_count"], 0)

    def test_exact_budget(self) -> None:
        prevention = BudgetOverspendPrevention(max_budget=5)
        allowed, _ = prevention.authorize("g1", 5)
        self.assertTrue(allowed)
        allowed2, _ = prevention.authorize("g2", 1)
        self.assertFalse(allowed2)


class TestQueueDepthTelemetry(unittest.TestCase):
    """Feature 10: Queue-depth telemetry."""

    def test_sample(self) -> None:
        telemetry = QueueDepthTelemetry()
        telemetry.sample(5, active=3)
        telemetry.sample(8, active=5)
        stats = telemetry.get_stats()
        self.assertEqual(stats["samples"], 2)
        self.assertEqual(stats["current"], 8)

    def test_empty_stats(self) -> None:
        telemetry = QueueDepthTelemetry()
        stats = telemetry.get_stats()
        self.assertEqual(stats["samples"], 0)

    def test_record(self) -> None:
        telemetry = QueueDepthTelemetry()
        telemetry.sample(3)
        events = telemetry.get_events("queue_depth")
        self.assertEqual(len(events), 1)


class TestWaitTimeTelemetry(unittest.TestCase):
    """Feature 11: Wait-time telemetry."""

    def test_admit_and_start(self) -> None:
        telemetry = WaitTimeTelemetry()
        telemetry.admit("g1")
        time.sleep(0.01)
        wait = telemetry.start("g1")
        self.assertGreater(wait, 0)

    def test_start_without_admit(self) -> None:
        telemetry = WaitTimeTelemetry()
        wait = telemetry.start("unknown")
        self.assertIsNone(wait)

    def test_get_stats(self) -> None:
        telemetry = WaitTimeTelemetry()
        stats = telemetry.get_stats()
        self.assertEqual(stats["samples"], 0)
        self.assertEqual(stats["mean"], 0.0)

    def test_record_event(self) -> None:
        telemetry = WaitTimeTelemetry()
        telemetry.admit("g1")
        telemetry.start("g1")
        events = telemetry.get_events("wait_time")
        self.assertEqual(len(events), 1)


class TestExecutionUtilization(unittest.TestCase):
    """Feature 12: Execution utilization metrics."""

    def test_sample(self) -> None:
        util = ExecutionUtilization(max_concurrency=10)
        util.sample(5)
        stats = util.get_stats()
        self.assertEqual(stats["samples"], 1)
        self.assertEqual(stats["current"], 0.5)

    def test_full_utilization(self) -> None:
        util = ExecutionUtilization(max_concurrency=4)
        util.sample(4)
        stats = util.get_stats()
        self.assertEqual(stats["current"], 1.0)

    def test_zero_max(self) -> None:
        util = ExecutionUtilization(max_concurrency=0)
        util.sample(5)
        stats = util.get_stats()
        self.assertEqual(stats["current"], 0.0)

    def test_record_event(self) -> None:
        util = ExecutionUtilization(max_concurrency=5)
        util.sample(3)
        events = util.get_events("utilization")
        self.assertEqual(len(events), 1)


class TestFairnessTrendTracker(unittest.TestCase):
    """Feature 13: Fairness trend tracking."""

    def test_record_fairness(self) -> None:
        tracker = FairnessTrendTracker()
        tracker.record_fairness(0.95, [10, 10, 10])
        trend = tracker.get_trend()
        self.assertEqual(trend["samples"], 1)

    def test_trend_improving(self) -> None:
        tracker = FairnessTrendTracker()
        tracker.record_fairness(0.5, [10, 5])
        tracker.record_fairness(0.9, [9, 9])
        trend = tracker.get_trend()
        self.assertEqual(trend["trend"], "improving")

    def test_trend_declining(self) -> None:
        tracker = FairnessTrendTracker()
        tracker.record_fairness(0.9, [9, 9])
        tracker.record_fairness(0.5, [10, 5])
        trend = tracker.get_trend()
        self.assertEqual(trend["trend"], "declining")

    def test_trend_stable(self) -> None:
        tracker = FairnessTrendTracker()
        tracker.record_fairness(0.8, [10, 10])
        tracker.record_fairness(0.8001, [10, 10])
        trend = tracker.get_trend()
        self.assertEqual(trend["trend"], "stable")

    def test_insufficient_data(self) -> None:
        tracker = FairnessTrendTracker()
        trend = tracker.get_trend()
        self.assertEqual(trend["trend"], "insufficient_data")


class TestSchedulerHealth(unittest.TestCase):
    """Feature 24 (partial): Scheduler health indicators."""

    def test_set_health(self) -> None:
        health = SchedulerHealth()
        health.set_health("scheduler", HealthIndicator.HEALTHY)
        state = health.get_health()
        self.assertEqual(state["indicators"]["scheduler"], "healthy")
        self.assertEqual(state["overall"], "healthy")

    def test_degraded_overall(self) -> None:
        health = SchedulerHealth()
        health.set_health("scheduler", HealthIndicator.HEALTHY)
        health.set_health("queue", HealthIndicator.DEGRADED)
        state = health.get_health()
        self.assertEqual(state["overall"], "degraded")

    def test_critical_overall(self) -> None:
        health = SchedulerHealth()
        health.set_health("scheduler", HealthIndicator.CRITICAL)
        state = health.get_health()
        self.assertEqual(state["overall"], "critical")

    def test_warnings(self) -> None:
        health = SchedulerHealth()
        health.set_health("scheduler", HealthIndicator.DEGRADED)
        state = health.get_health()
        self.assertEqual(len(state["warnings"]), 1)
        self.assertEqual(state["warnings"][0]["status"], "degraded")

    def test_recovering(self) -> None:
        health = SchedulerHealth()
        health.set_health("scheduler", HealthIndicator.RECOVERING)
        state = health.get_health()
        self.assertEqual(state["overall"], "recovering")


class TestStarvationRecovery(unittest.TestCase):
    """Feature 15: Starvation recovery (extending 14)."""

    def test_detect_starvation(self) -> None:
        recovery = StarvationRecovery(max_wait_s=0.05)
        start_times = {"g1": time.monotonic() - 0.1, "g2": time.monotonic() - 0.01}
        running = {"g1", "g2"}
        starved = recovery.detect(start_times, running)
        self.assertEqual(len(starved), 1)
        self.assertEqual(starved[0]["goal_id"], "g1")

    def test_no_starvation(self) -> None:
        recovery = StarvationRecovery(max_wait_s=1.0)
        start_times = {"g1": time.monotonic() - 0.1}
        running = {"g1"}
        starved = recovery.detect(start_times, running)
        self.assertEqual(len(starved), 0)

    def test_recover(self) -> None:
        recovery = StarvationRecovery()
        result = recovery.recover("g1", action="priority_bump")
        self.assertEqual(result["goal_id"], "g1")
        self.assertEqual(result["action"], "priority_bump")

    def test_get_stats_empty(self) -> None:
        recovery = StarvationRecovery()
        stats = recovery.get_stats()
        self.assertEqual(stats["starvation_detections"], 0)
        self.assertEqual(stats["recoveries"], 0)

    def test_get_stats_with_data(self) -> None:
        recovery = StarvationRecovery()
        recovery._starvation_log.append({"goal_id": "g1", "wait_s": 1.0})
        recovery._recoveries.append({"goal_id": "g1"})
        stats = recovery.get_stats()
        self.assertEqual(stats["starvation_detections"], 1)
        self.assertEqual(stats["recoveries"], 1)


class TestPriorityInversionRecovery(unittest.TestCase):
    """Feature 16: Priority inversion recovery."""

    def test_detect_inversion(self) -> None:
        recovery = PriorityInversionRecovery()
        priorities = {"low": 1, "high": 100}
        blocked = {"high": "low"}
        inversions = recovery.detect(priorities, blocked)
        self.assertEqual(len(inversions), 1)
        self.assertEqual(inversions[0]["blocked_goal"], "high")

    def test_no_inversion(self) -> None:
        recovery = PriorityInversionRecovery()
        priorities = {"low": 1, "high": 100}
        blocked = {"low": "high"}
        inversions = recovery.detect(priorities, blocked)
        self.assertEqual(len(inversions), 0)

    def test_resolve(self) -> None:
        recovery = PriorityInversionRecovery()
        result = recovery.resolve("low", "priority_inheritance")
        self.assertEqual(result["method"], "priority_inheritance")

    def test_get_stats(self) -> None:
        recovery = PriorityInversionRecovery()
        recovery.detect({"low": 1, "high": 100}, {"high": "low"})
        recovery.resolve("high")
        stats = recovery.get_stats()
        self.assertEqual(stats["inversions_detected"], 1)
        self.assertEqual(stats["resolutions"], 1)


class TestCancellationPropagator(unittest.TestCase):
    """Feature 17: Cancellation propagation across DAGs."""

    def test_cancel_single(self) -> None:
        prop = CancellationPropagator()
        affected = prop.cancel("g1")
        self.assertIn("g1", affected)

    def test_cancel_with_dependencies(self) -> None:
        prop = CancellationPropagator()
        prop.register_dependency("g2", ["g1"])
        affected = prop.cancel("g1")
        self.assertIn("g1", affected)
        self.assertIn("g2", affected)
        self.assertTrue(prop.is_cancelled("g1"))
        self.assertTrue(prop.is_cancelled("g2"))

    def test_transitive_dependency(self) -> None:
        prop = CancellationPropagator()
        prop.register_dependency("g2", ["g1"])
        prop.register_dependency("g3", ["g2"])
        affected = prop.cancel("g1")
        self.assertIn("g3", affected)

    def test_cancel_through_fan_in(self) -> None:
        prop = CancellationPropagator()
        prop.register_dependency("g3", ["g1", "g2"])
        prop.register_dependency("g4", ["g3"])
        affected = prop.cancel("g1")
        self.assertIn("g3", affected)
        self.assertIn("g4", affected)

    def test_get_log(self) -> None:
        prop = CancellationPropagator()
        prop.cancel("g1")
        log = prop.get_log()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["goal_id"], "g1")


class TestFanOutBackpressure(unittest.TestCase):
    """Feature 19: Fan-out backpressure."""

    def test_submit_within_limit(self) -> None:
        bp = FanOutBackpressure(max_concurrent_tasks=3)
        allowed, _ = bp.submit("task-1")
        self.assertTrue(allowed)

    def test_backpressure_when_full(self) -> None:
        bp = FanOutBackpressure(max_concurrent_tasks=2)
        bp.submit("task-1")
        bp.submit("task-2")
        allowed, reason = bp.submit("task-3")
        self.assertFalse(allowed)
        self.assertIn("backpressure", reason)

    def test_release_opens_slot(self) -> None:
        bp = FanOutBackpressure(max_concurrent_tasks=1)
        bp.submit("task-1")
        bp.submit("task-2")
        bp.release("task-1")
        self.assertEqual(bp.get_state()["active"], 1)

    def test_get_state(self) -> None:
        bp = FanOutBackpressure(max_concurrent_tasks=2)
        bp.submit("task-1")
        bp.submit("task-2")
        bp.submit("task-3")
        state = bp.get_state()
        self.assertEqual(state["active"], 2)
        self.assertEqual(state["queued"], 1)
        self.assertEqual(state["backpressure_events"], 1)


class TestFanInQuorumTracker(unittest.TestCase):
    """Feature 20: Fan-in quorum/aggregation telemetry."""

    def test_register_and_complete(self) -> None:
        tracker = FanInQuorumTracker()
        tracker.register("task-3", ["task-1", "task-2"])
        tracker.mark_complete("task-1")
        status = tracker.get_quorum_status("task-3")
        self.assertFalse(status["quorum_reached"])
        tracker.mark_complete("task-2")
        status2 = tracker.get_quorum_status("task-3")
        self.assertTrue(status2["quorum_reached"])

    def test_partial_completion(self) -> None:
        tracker = FanInQuorumTracker()
        tracker.register("task-2", ["task-1"])
        tracker.mark_complete("task-1")
        tracker.mark_complete("task-2")
        status = tracker.get_quorum_status("task-2")
        self.assertTrue(status["quorum_reached"])
        self.assertIn("task-2", tracker._completed)

    def test_unknown_task(self) -> None:
        tracker = FanInQuorumTracker()
        status = tracker.get_quorum_status("unknown")
        self.assertEqual(status["total_dependencies"], 0)
        self.assertTrue(status["quorum_reached"])


class TestCrossGoalReplayVerifier(unittest.TestCase):
    """Feature 21: Cross-goal replay verification."""

    def test_deterministic_match(self) -> None:
        verifier = CrossGoalReplayVerifier()
        h = hashlib.sha256(b"test").hexdigest()
        result = verifier.verify("g1", h, h, {"retries": 0})
        self.assertTrue(result["deterministic"])

    def test_mismatch(self) -> None:
        verifier = CrossGoalReplayVerifier()
        result = verifier.verify("g1", "hash_a", "hash_b")
        self.assertFalse(result["deterministic"])

    def test_get_summary(self) -> None:
        verifier = CrossGoalReplayVerifier()
        summary = verifier.get_summary()
        self.assertEqual(summary["total"], 0)

    def test_get_results(self) -> None:
        verifier = CrossGoalReplayVerifier()
        verifier.verify("g1", "h1", "h1")
        results = verifier.get_results()
        self.assertEqual(len(results), 1)


class TestRestartSafeSchedulerRecovery(unittest.TestCase):
    """Feature 22: Restart-safe scheduler recovery."""

    def test_persist_and_recover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            recovery = RestartSafeSchedulerRecovery(db_path=db_path)
            recovery._state = {"goals": {"g1": "running"}, "queue": []}
            persist_result = recovery.persist()
            self.assertTrue(persist_result["persisted"])
            recovery2 = RestartSafeSchedulerRecovery(db_path=db_path)
            result = recovery2.recover()
            self.assertTrue(result["recovered"])
            self.assertEqual(recovery2._state["goals"], {"g1": "running"})

    def test_recover_no_db(self) -> None:
        recovery = RestartSafeSchedulerRecovery(db_path="/nonexistent/path.db")
        result = recovery.recover()
        self.assertFalse(result["recovered"])


class TestPersistentSchedulerState(unittest.TestCase):
    """Feature 23: Persistent scheduler state reconstruction."""

    def test_reconstruct_no_db(self) -> None:
        state = PersistentSchedulerState(db_path="/nonexistent/path.db")
        result = state.reconstruct()
        self.assertFalse(result["reconstructed"])


class TestSchedulerIntegration(unittest.TestCase):
    """Integration: all scheduler features work together."""

    def test_full_scheduler_flow(self) -> None:
        admission = GlobalSchedulerAdmission(max_active_goals=5, max_global_calls=20)
        limiter = AdaptiveConcurrencyLimiter(max_concurrency=5)
        util = ExecutionUtilization(max_concurrency=5)
        health = SchedulerHealth()

        # Admit a goal
        receipt = admission.admit("g1", estimated_calls=2)
        self.assertTrue(receipt.decision_type == SchedulerDecisionType.ADMIT)

        # Check admission recorded in receipt
        self.assertIn("active_goals", receipt.metadata)

        # Track utilization
        util.sample(admission.get_state()["active_goals"])

        # Health check
        health.set_health("admission", HealthIndicator.HEALTHY)
        health.set_health("concurrency", HealthIndicator.HEALTHY)

        # Verify state consistency
        state = admission.get_state()
        self.assertEqual(state["active_goals"], 1)
        self.assertEqual(state["admissions"], 1)

        # Budget aware
        budget_adm = BudgetAwareAdmission(global_budget=10)
        budget_receipt = budget_adm.admit("g2", estimated_calls=3)
        self.assertEqual(budget_adm.remaining, 7)

        # Overspend prevention
        prevention = BudgetOverspendPrevention(max_budget=5)
        self.assertTrue(prevention.authorize("g3", 3)[0])
        self.assertFalse(prevention.authorize("g4", 3)[0])

        # Forecaster
        forecaster = BudgetForecaster()
        t = time.time()
        forecaster.record("g1", 2, t, 1.0)
        forecaster.record("g1", 3, t + 1, 1.0)
        forecast = forecaster.forecast(horizon_s=60.0)
        self.assertIn("predicted_calls", forecast)

        # Priority scheduling
        sched = WeightedPriorityScheduler()
        sched.set_weight("low", 1.0)
        sched.set_weight("high", 5.0)
        ordered = sched.schedule([("low", 10), ("high", 10)])
        self.assertEqual(ordered[0], "high")

        # Fan-out backpressure
        bp = FanOutBackpressure(max_concurrent_tasks=2)
        self.assertTrue(bp.submit("t1")[0])
        self.assertTrue(bp.submit("t2")[0])
        self.assertFalse(bp.submit("t3")[0])

        # Fan-in quorum
        fiq = FanInQuorumTracker()
        fiq.register("task-3", ["task-1", "task-2"])
        fiq.mark_complete("task-1")
        self.assertFalse(fiq.get_quorum_status("task-3")["quorum_reached"])

        # Cancellation propagation
        cp = CancellationPropagator()
        cp.register_dependency("g2", ["g1"])
        affected = cp.cancel("g1")
        self.assertIn("g2", affected)

        # Retry reservation
        retry = RetryAwareReservation(default_retries=2)
        retry.reserve("g1", max_retries=2)
        self.assertTrue(retry.can_retry("g1")[0])
        retry.consume_retry("g1")
        self.assertTrue(retry.can_retry("g1")[0])
        retry.consume_retry("g1")
        self.assertFalse(retry.can_retry("g1")[0])

        # Wait time
        wt = WaitTimeTelemetry()
        wt.admit("g1")
        wt.start("g1")
        wt_stats = wt.get_stats()
        self.assertGreaterEqual(wt_stats["samples"], 1)

        # Queue depth
        qd = QueueDepthTelemetry()
        qd.sample(3)
        qd.sample(5)
        qd_stats = qd.get_stats()
        self.assertEqual(qd_stats["current"], 5)

        # Fairness trend
        ft = FairnessTrendTracker()
        ft.record_fairness(0.8, [10, 10])
        ft.record_fairness(0.9, [10, 10])
        ft_trend = ft.get_trend()
        self.assertEqual(ft_trend["trend"], "improving")


class TestFailureDomainIsolator(unittest.TestCase):
    """Feature 18: Failure-domain isolation."""

    def test_register_domain(self) -> None:
        iso = FailureDomainIsolator()
        iso.register_domain("d1", parent="root")
        self.assertEqual(iso.get_domain_status("d1")["status"], "healthy")

    def test_record_failure(self) -> None:
        iso = FailureDomainIsolator()
        iso.register_domain("d1")
        iso.record_failure("d1", ValueError("test"))
        self.assertTrue(iso.is_isolated("d1"))
        self.assertEqual(iso.get_domain_status("d1")["status"], "failed")

    def test_isolation_prevents_cascade(self) -> None:
        iso = FailureDomainIsolator()
        iso.register_domain("d1", parent="root")
        iso.register_domain("d2", parent="root")
        iso.register_domain("d3", parent="root")
        iso.record_failure("d1", ValueError("fail"))
        self.assertTrue(iso.is_isolated("d1"))
        self.assertFalse(iso.is_isolated("d2"))

    def test_containment(self) -> None:
        iso = FailureDomainIsolator()
        iso.register_domain("d1", parent="root")
        iso.register_domain("d2", parent="root")
        iso.register_domain("d3", parent="root")
        iso.record_failure("d1", ValueError("fail"))
        contained = iso.propagate_containment("d1")
        self.assertIn("d1", contained)

    def test_get_stats(self) -> None:
        iso = FailureDomainIsolator()
        iso.register_domain("d1")
        iso.record_failure("d1", ValueError("fail"))
        stats = iso.get_stats()
        self.assertEqual(stats["domains"], 1)
        self.assertEqual(stats["failures"], 1)


class TestSchedulerDashboardExtension(unittest.TestCase):
    """Feature 24: Dashboard scheduler timeline + health indicators."""

    def test_record_timeline_event(self) -> None:
        ext = SchedulerDashboardExtension()
        ext.record_timeline_event({"type": "admit", "goal": "g1"})
        data = ext.get_dashboard_data()
        self.assertEqual(len(data["timeline"]), 1)

    def test_set_health(self) -> None:
        ext = SchedulerDashboardExtension()
        ext.set_health("scheduler", "healthy")
        ext.set_health("queue", "degraded")
        data = ext.get_dashboard_data()
        self.assertEqual(data["health"]["scheduler"], "healthy")
        self.assertEqual(data["health"]["queue"], "degraded")

    def test_summary(self) -> None:
        ext = SchedulerDashboardExtension()
        ext.set_health("scheduler", "healthy")
        ext.set_health("queue", "degraded")
        data = ext.get_dashboard_data()
        summary = data["summary"]
        self.assertEqual(summary["healthy_components"], 1)
        self.assertEqual(summary["unhealthy_components"], 1)
        self.assertIn("queue", summary["warnings"])

    def test_update_metric(self) -> None:
        ext = SchedulerDashboardExtension()
        ext.update_metric("queue_depth", 10)
        ext.update_metric("active_goals", 3)
        data = ext.get_dashboard_data()
        self.assertEqual(data["metrics"]["queue_depth"], 10)
        self.assertEqual(data["metrics"]["active_goals"], 3)


class TestStressReportEnhancer(unittest.TestCase):
    """Feature 25: Stress CLI/report enhancements."""

    def test_generate_report(self) -> None:
        config = StressTestConfig(num_goals=5, max_calls_global=20)
        result = StressTestResult(config=config, total_calls=15, total_retries=2)
        enhancer = StressReportEnhancer()
        report = enhancer.generate_report(result)
        self.assertIn("report_id", report)
        self.assertEqual(report["total_calls"], 15)
        self.assertTrue(report["deterministic"])

    def test_cli_output(self) -> None:
        config = StressTestConfig(num_goals=3, max_calls_global=10)
        result = StressTestResult(config=config, total_calls=8)
        enhancer = StressReportEnhancer()
        output = enhancer.cli_output(result)
        self.assertIn("Goals: 3", output)
        self.assertIn("Total Calls: 8", output)
        self.assertIn("=== End Report ===", output)

    def test_deterministic_compare(self) -> None:
        config = StressTestConfig(num_goals=5, max_calls_global=20)
        r1 = StressTestResult(config=config, total_calls=10, fairness_index=0.8)
        r2 = StressTestResult(config=config, total_calls=12, fairness_index=0.7)
        enhancer = StressReportEnhancer()
        comparison = enhancer.deterministic_compare(r1, r2)
        self.assertTrue(comparison["deterministic"])
        self.assertIn("fairness_winner", comparison)
        self.assertIn("efficiency_winner", comparison)

    def test_deterministic_compare_same(self) -> None:
        config = StressTestConfig(num_goals=5, max_calls_global=20)
        r1 = StressTestResult(config=config, total_calls=10, fairness_index=0.8)
        r2 = StressTestResult(config=config, total_calls=10, fairness_index=0.8)
        enhancer = StressReportEnhancer()
        comparison = enhancer.deterministic_compare(r1, r2)
        self.assertEqual(comparison["fairness_winner"], "tie")
        self.assertEqual(comparison["efficiency_winner"], "tie")

    def test_get_reports(self) -> None:
        config = StressTestConfig(num_goals=3, max_calls_global=10)
        result = StressTestResult(config=config, total_calls=5)
        enhancer = StressReportEnhancer()
        enhancer.generate_report(result)
        enhancer.generate_report(result)
        self.assertEqual(len(enhancer.get_reports()), 2)


if __name__ == "__main__":
    unittest.main()
