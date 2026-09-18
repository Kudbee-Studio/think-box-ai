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
    GoalTimeoutEnforcer,
    GoalDependencyResolver,
    SchedulerPerformanceAnalytics,
    CapacityPredictor,
    WorkStealingQueue,
    SLAComplianceTracker,
    CheckpointManager,
    DAGVisualizer,
    GoalPriorityBoost,
    SchedulerLatencyTracker,
    DeadlineExtensionPolicy,
    GoalGroupManager,
    AdmissionPolicyChain,
    GoalRetryBudgetResolver,
    GoalProgressTracker,
    ConfigurableRetryPolicy,
    SubtaskFailureAggregator,
    CriticalPathHighlight,
    PriorityAging,
    DeadlineMode,
    JobGroupFanInGate,
    TenantFairShare,
    RetryBudgetWithJitter,
    IdempotencyStore,
    QueuePauseResume,
    SLABreachEmitter,
    SchedulerPolicyPackV2,
    MultiQueueRouting,
    BackpressureAdmissionV2,
    DurableJobCheckpoints,
    DAGExecutionEngine,
    ObservabilityExportPack,
)
from thinkbox.concurrent_goals import (
    StressTestConfig,
    StressTestResult,
    StressReportEnhancer,
    BudgetContentionPolicy,
    GoalPriority,
    GoalLifecycleState,
    AdaptiveRetryBackoff,
    GoalResourceProfiler,
    ErrorClassificationEngine,
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


class TestGoalTimeoutEnforcer(unittest.TestCase):
    """Feature 26: Goal timeout enforcement."""

    def test_register_and_check(self) -> None:
        enforcer = GoalTimeoutEnforcer(default_timeout_s=10.0)
        enforcer.register("goal-1", timeout_s=5.0)
        result = enforcer.check("goal-1")
        self.assertFalse(result["timed_out"])
        self.assertIn("elapsed", result)

    def test_not_registered(self) -> None:
        enforcer = GoalTimeoutEnforcer()
        result = enforcer.check("unknown")
        self.assertFalse(result["timed_out"])
        self.assertEqual(result["reason"], "not_registered")

    def test_is_timed_out(self) -> None:
        enforcer = GoalTimeoutEnforcer(default_timeout_s=0.001)
        enforcer.register("goal-1", timeout_s=0.001)
        time.sleep(0.01)
        self.assertTrue(enforcer.is_timed_out("goal-1"))

    def test_get_timed_out(self) -> None:
        enforcer = GoalTimeoutEnforcer(default_timeout_s=0.001)
        enforcer.register("goal-1", timeout_s=0.001)
        time.sleep(0.01)
        enforcer.check("goal-1")
        timed = enforcer.get_timed_out()
        self.assertEqual(len(timed), 1)
        self.assertEqual(timed[0]["goal_id"], "goal-1")
        self.assertGreater(timed[0]["elapsed"], timed[0]["limit"])

    def test_get_stats(self) -> None:
        enforcer = GoalTimeoutEnforcer()
        enforcer.register("g1", timeout_s=10.0)
        stats = enforcer.get_stats()
        self.assertEqual(stats["registered"], 1)
        self.assertEqual(stats["timed_out"], 0)
        self.assertEqual(stats["active"], 1)


class TestGoalDependencyResolver(unittest.TestCase):
    """Feature 27: Goal dependency resolution."""

    def test_topological_sort(self) -> None:
        resolver = GoalDependencyResolver()
        resolver.add_goal("a", ["b", "c"])
        resolver.add_goal("b")
        resolver.add_goal("c")
        result = resolver.topological_sort()
        self.assertIsNotNone(result)
        self.assertIn(result.index("b"), [0])
        self.assertIn(result.index("c"), [0, 1])
        self.assertGreater(result.index("a"), result.index("b"))
        self.assertGreater(result.index("a"), result.index("c"))

    def test_cycle_detection(self) -> None:
        resolver = GoalDependencyResolver()
        resolver.add_goal("a", ["b"])
        resolver.add_goal("b", ["a"])
        self.assertTrue(resolver.has_cycles())
        self.assertIsNone(resolver.topological_sort())

    def test_no_cycles(self) -> None:
        resolver = GoalDependencyResolver()
        resolver.add_goal("a", ["b"])
        resolver.add_goal("b")
        self.assertFalse(resolver.has_cycles())
        self.assertIsNotNone(resolver.topological_sort())

    def test_parallel_schedule(self) -> None:
        resolver = GoalDependencyResolver()
        resolver.add_goal("a", ["b", "c"])
        resolver.add_goal("b")
        resolver.add_goal("c")
        levels = resolver.parallel_schedule()
        self.assertEqual(len(levels), 2)
        self.assertIn("b", levels[0])
        self.assertIn("c", levels[0])
        self.assertIn("a", levels[1])

    def test_critical_path(self) -> None:
        resolver = GoalDependencyResolver()
        resolver.add_goal("a", ["b"])
        resolver.add_goal("b", ["c"])
        resolver.add_goal("c")
        path, length = resolver.critical_path()
        self.assertEqual(path, ["c", "b", "a"])
        self.assertEqual(length, 3)
        resolver = GoalDependencyResolver()
        self.assertEqual(resolver.topological_sort(), [])
        self.assertFalse(resolver.has_cycles())
        self.assertEqual(resolver.parallel_schedule(), [])
        self.assertEqual(resolver.critical_path(), ([], 0))

    def test_get_stats(self) -> None:
        resolver = GoalDependencyResolver()
        resolver.add_goal("a", ["b"])
        resolver.add_goal("b")
        stats = resolver.get_stats()
        self.assertEqual(stats["goals"], 2)
        self.assertFalse(stats["has_cycles"])

    def test_empty(self) -> None:
        resolver = GoalDependencyResolver()
        self.assertEqual(resolver.topological_sort(), [])
        self.assertFalse(resolver.has_cycles())
        self.assertEqual(resolver.parallel_schedule(), [])
        self.assertEqual(resolver.critical_path(), ([], 0))


class TestSchedulerPerformanceAnalytics(unittest.TestCase):
    """Feature 28: Scheduler performance analytics."""

    def test_record_and_throughput(self) -> None:
        analytics = SchedulerPerformanceAnalytics()
        analytics.record_completion("g1", 1.0, 5)
        analytics.record_completion("g2", 2.0, 3)
        tp = analytics.get_throughput()
        self.assertEqual(tp["total_completed"], 2)
        self.assertEqual(tp["recent_completions"], 2)

    def test_latency_percentiles(self) -> None:
        analytics = SchedulerPerformanceAnalytics()
        analytics.record_completion("g1", 1.0, 1)
        analytics.record_completion("g2", 2.0, 1)
        analytics.record_completion("g3", 3.0, 1)
        pct = analytics.get_latency_percentiles()
        self.assertEqual(pct["p50"], 2.0)
        self.assertEqual(pct["samples"], 3)
        self.assertGreater(pct["p95"], 2.0)

    def test_cost_efficiency(self) -> None:
        analytics = SchedulerPerformanceAnalytics()
        analytics.record_completion("g1", 1.0, 5)
        analytics.record_completion("g2", 2.0, 3)
        cost = analytics.get_cost_efficiency()
        self.assertEqual(cost["total_calls"], 8)
        self.assertEqual(cost["total_goals"], 2)
        self.assertEqual(cost["avg_calls_per_goal"], 4.0)

    def test_summary(self) -> None:
        analytics = SchedulerPerformanceAnalytics()
        analytics.record_completion("g1", 1.0, 2)
        summary = analytics.get_summary()
        self.assertIn("throughput", summary)
        self.assertIn("latency_percentiles", summary)
        self.assertIn("cost_efficiency", summary)
        self.assertEqual(summary["total_completions"], 1)

    def test_empty(self) -> None:
        analytics = SchedulerPerformanceAnalytics()
        self.assertEqual(analytics.get_throughput()["total_completed"], 0)
        pct = analytics.get_latency_percentiles()
        self.assertEqual(pct["p50"], 0.0)
        cost = analytics.get_cost_efficiency()
        self.assertEqual(cost["calls_per_goal"], 0.0)


class TestCapacityPredictor(unittest.TestCase):
    """Feature 29: Capacity prediction."""

    def test_record_and_predict_congestion(self) -> None:
        predictor = CapacityPredictor()
        predictor.record_capacity(5, 10, 100)
        predictor.record_capacity(8, 15, 200)
        result = predictor.predict_congestion()
        self.assertIn(result["congestion_risk"], ["low", "medium", "high"])

    def test_predict_optimal_concurrency(self) -> None:
        predictor = CapacityPredictor()
        predictor.record_capacity(5, 10, 100)
        predictor.record_capacity(8, 15, 200)
        result = predictor.predict_optimal_concurrency()
        self.assertGreaterEqual(result["recommended_concurrency"], 1)
        self.assertIn(result["confidence"], ["low", "medium", "high"])

    def test_get_trend(self) -> None:
        predictor = CapacityPredictor()
        predictor.record_capacity(10, 20, 100)
        predictor.record_capacity(8, 15, 200)
        trend = predictor.get_trend()
        self.assertIn(trend["queue_trend"], ["improving", "worsening", "stable"])

    def test_insufficient_data(self) -> None:
        predictor = CapacityPredictor()
        result = predictor.predict_congestion()
        self.assertEqual(result["congestion_risk"], "unknown")
        result2 = predictor.predict_optimal_concurrency()
        self.assertEqual(result2["confidence"], "low")
        trend = predictor.get_trend()
        self.assertEqual(trend["queue_trend"], "insufficient_data")

    def test_improving_trend(self) -> None:
        predictor = CapacityPredictor()
        predictor.record_capacity(10, 20, 100)
        predictor.record_capacity(5, 10, 200)
        trend = predictor.get_trend()
        self.assertEqual(trend["queue_trend"], "improving")


class TestWorkStealingQueue(unittest.TestCase):
    """Feature 30: Dynamic work stealing."""

    def test_enqueue_dequeue(self) -> None:
        wsq = WorkStealingQueue()
        wsq.enqueue("g1", "task1")
        wsq.enqueue("g1", "task2")
        self.assertEqual(wsq.dequeue("g1"), "task1")
        self.assertEqual(wsq.dequeue("g1"), "task2")
        self.assertIsNone(wsq.dequeue("g1"))

    def test_steal(self) -> None:
        wsq = WorkStealingQueue(imbalance_threshold=1.5)
        wsq.enqueue("donor", "t1")
        wsq.enqueue("donor", "t2")
        wsq.enqueue("recipient", "t3")
        result = wsq.steal("donor", "recipient")
        self.assertIsNotNone(result)
        self.assertEqual(result["donor"], "donor")
        self.assertEqual(result["recipient"], "recipient")
        self.assertEqual(wsq.get_load("donor"), 1)
        self.assertEqual(wsq.get_load("recipient"), 2)

    def test_no_steal_when_balanced(self) -> None:
        wsq = WorkStealingQueue(imbalance_threshold=2.0)
        wsq.enqueue("g1", "t1")
        wsq.enqueue("g2", "t2")
        result = wsq.steal("g1", "g2")
        self.assertIsNone(result)

    def test_rebalance(self) -> None:
        wsq = WorkStealingQueue(imbalance_threshold=1.5)
        for i in range(5):
            wsq.enqueue("g1", f"t{i}")
        wsq.enqueue("g2", "t5")
        steals = wsq.rebalance()
        self.assertTrue(wsq.get_balanced())

    def test_steal_same_goal(self) -> None:
        wsq = WorkStealingQueue()
        wsq.enqueue("g1", "t1")
        result = wsq.steal("g1", "g1")
        self.assertIsNone(result)

    def test_get_stats(self) -> None:
        wsq = WorkStealingQueue()
        wsq.enqueue("g1", "t1")
        wsq.enqueue("g2", "t2")
        stats = wsq.get_stats()
        self.assertEqual(stats["total_items"], 2)
        self.assertEqual(stats["goals"], 2)


class TestSLAComplianceTracker(unittest.TestCase):
    """Feature 31: SLA compliance tracking."""

    def test_set_and_check_compliant(self) -> None:
        tracker = SLAComplianceTracker()
        tracker.set_sla("g1", max_completion_s=10.0, min_success_rate=0.9)
        tracker.record_result("g1", 5.0, True)
        result = tracker.check_compliance("g1")
        self.assertTrue(result["compliant"])
        self.assertTrue(result["time_ok"])
        self.assertTrue(result["rate_ok"])

    def test_non_compliant(self) -> None:
        tracker = SLAComplianceTracker()
        tracker.set_sla("g1", max_completion_s=2.0, min_success_rate=0.95)
        tracker.record_result("g1", 5.0, True)
        result = tracker.check_compliance("g1")
        self.assertFalse(result["compliant"])
        self.assertFalse(result["time_ok"])

    def test_low_success_rate(self) -> None:
        tracker = SLAComplianceTracker()
        tracker.set_sla("g1", max_completion_s=10.0, min_success_rate=0.95)
        tracker.record_result("g1", 1.0, True)
        tracker.record_result("g1", 2.0, False)
        result = tracker.check_compliance("g1")
        self.assertFalse(result["compliant"])
        self.assertFalse(result["rate_ok"])

    def test_no_sla(self) -> None:
        tracker = SLAComplianceTracker()
        result = tracker.check_compliance("unknown")
        self.assertFalse(result["compliant"])
        self.assertEqual(result["reason"], "no_sla")

    def test_no_results(self) -> None:
        tracker = SLAComplianceTracker()
        tracker.set_sla("g1", max_completion_s=10.0)
        result = tracker.check_compliance("g1")
        self.assertFalse(result["compliant"])
        self.assertEqual(result["reason"], "no_results")

    def test_get_compliance_report(self) -> None:
        tracker = SLAComplianceTracker()
        tracker.set_sla("g1", max_completion_s=10.0, min_success_rate=0.9)
        tracker.record_result("g1", 5.0, True)
        report = tracker.get_compliance_report()
        self.assertEqual(report["total_goals"], 1)
        self.assertEqual(report["compliant"], 1)
        self.assertEqual(report["compliance_rate"], 1.0)


class TestCheckpointManager(unittest.TestCase):
    """Feature 32: Checkpoint management."""

    def test_save_and_restore(self) -> None:
        cm = CheckpointManager()
        checkpoint = cm.save("g1", {"step": 1, "data": "abc"})
        self.assertIn("checkpoint_id", checkpoint)
        restored = cm.restore(checkpoint["checkpoint_id"])
        self.assertIsNotNone(restored)
        self.assertEqual(restored["goal_id"], "g1")
        self.assertEqual(restored["state"], {"step": 1, "data": "abc"})

    def test_restore_nonexistent(self) -> None:
        cm = CheckpointManager()
        result = cm.restore("nonexistent")
        self.assertIsNone(result)

    def test_list_checkpoints(self) -> None:
        cm = CheckpointManager()
        cm.save("g1", {"step": 1})
        cm.save("g1", {"step": 2})
        cm.save("g2", {"step": 1})
        all_cps = cm.list_checkpoints()
        self.assertEqual(len(all_cps), 3)
        g1_cps = cm.list_checkpoints("g1")
        self.assertEqual(len(g1_cps), 2)
        g2_cps = cm.list_checkpoints("g2")
        self.assertEqual(len(g2_cps), 1)

    def test_delete(self) -> None:
        cm = CheckpointManager()
        cp = cm.save("g1", {"step": 1})
        self.assertTrue(cm.delete(cp["checkpoint_id"]))
        self.assertIsNone(cm.restore(cp["checkpoint_id"]))
        self.assertFalse(cm.delete("nonexistent"))

    def test_max_checkpoints(self) -> None:
        cm = CheckpointManager(max_checkpoints=3)
        for i in range(5):
            cm.save("g1", {"step": i})
        cps = cm.list_checkpoints("g1")
        self.assertEqual(len(cps), 3)

    def test_get_stats(self) -> None:
        cm = CheckpointManager()
        cm.save("g1", {"step": 1})
        cm.save("g2", {"step": 1})
        stats = cm.get_stats()
        self.assertEqual(stats["total_checkpoints"], 2)
        self.assertEqual(stats["goals_with_checkpoints"], 2)


class TestDAGVisualizer(unittest.TestCase):
    """Feature 36: DAG visualization."""

    def test_visualize_ascii(self) -> None:
        dv = DAGVisualizer()
        dv._resolver.add_goal("a", ["b"])
        dv._resolver.add_goal("b")
        out = dv.visualize_ascii()
        self.assertIn("Level 0", out)
        self.assertIn("Level 1", out)
        self.assertIn("b", out)
        self.assertIn("a", out)

    def test_visualize_dot(self) -> None:
        dv = DAGVisualizer()
        dv._resolver.add_goal("a", ["b"])
        dv._resolver.add_goal("b")
        dot = dv.visualize_dot()
        self.assertIn("digraph", dot)
        self.assertIn('"a"', dot)
        self.assertIn('"b"', dot)

    def test_get_depth_map(self) -> None:
        dv = DAGVisualizer()
        dv._resolver.add_goal("a", ["b"])
        dv._resolver.add_goal("b")
        dv._resolver.add_goal("c", ["a"])
        depth = dv.get_depth_map()
        self.assertEqual(depth["b"], 0)
        self.assertEqual(depth["a"], 1)
        self.assertEqual(depth["c"], 2)

    def test_get_width_at_level(self) -> None:
        dv = DAGVisualizer()
        dv._resolver.add_goal("a", ["b"])
        dv._resolver.add_goal("b")
        dv._resolver.add_goal("c")
        self.assertEqual(dv.get_width_at_level(0), 2)  # b, c

    def test_get_stats(self) -> None:
        dv = DAGVisualizer()
        dv._resolver.add_goal("a", ["b"])
        dv._resolver.add_goal("b")
        stats = dv.get_stats()
        self.assertEqual(stats["goals"], 2)
        self.assertFalse(stats["has_cycles"])

    def test_cycles(self) -> None:
        dv = DAGVisualizer()
        dv._resolver.add_goal("a", ["b"])
        dv._resolver.add_goal("b", ["a"])
        self.assertEqual(dv.visualize_ascii(), "DAG has cycles - cannot visualize")
        self.assertEqual(dv.visualize_dot(), 'digraph { error="cycles detected" }')
        self.assertEqual(dv.get_depth_map(), {})

    def test_empty(self) -> None:
        dv = DAGVisualizer()
        self.assertIn("empty", dv.visualize_ascii())
        self.assertEqual(dv.get_stats()["goals"], 0)


class TestGoalPriorityBoost(unittest.TestCase):
    """Feature 37: Dynamic priority boosting."""

    def test_no_boost_when_fresh(self) -> None:
        gp = GoalPriorityBoost(boost_threshold_s=10.0)
        gp.register("g1")
        result = gp.check("g1", current_priority=5)
        self.assertFalse(result["boosted"])

    def test_boost_after_threshold(self) -> None:
        gp = GoalPriorityBoost(boost_threshold_s=0.001, boost_amount=5)
        gp.register("g1")
        time.sleep(0.01)
        result = gp.check("g1", current_priority=5)
        self.assertTrue(result["boosted"])
        self.assertEqual(result["old_priority"], 5)
        self.assertEqual(result["new_priority"], 10)

    def test_max_boosts(self) -> None:
        gp = GoalPriorityBoost(boost_threshold_s=0.001, boost_amount=5, max_boosts=2)
        gp.register("g1")
        gp._boost_counts["g1"] = 2  # simulate 2 boosts
        gp._wait_start["g1"] = 0  # make waited
        result = gp.check("g1", current_priority=5)
        self.assertFalse(result["boosted"])
        self.assertTrue(gp.is_max_boosted("g1"))

    def test_reset(self) -> None:
        gp = GoalPriorityBoost()
        gp.register("g1")
        gp.reset("g1")
        result = gp.check("g1", current_priority=5)
        self.assertFalse(result["boosted"])

    def test_get_stats(self) -> None:
        gp = GoalPriorityBoost()
        gp.register("g1")
        gp.register("g2")
        stats = gp.get_stats()
        self.assertEqual(stats["registered"], 2)


class TestSchedulerLatencyTracker(unittest.TestCase):
    """Feature 38: Scheduler decision latency tracking."""

    def test_record_and_measure(self) -> None:
        slt = SchedulerLatencyTracker()
        slt.record_decision("g1", "admit")
        slt.record_execution_start("g1")
        result = slt.get_decisions("g1")
        self.assertEqual(len(result), 1)
        self.assertIn("latency_s", result[0])
        self.assertGreaterEqual(result[0]["latency_s"], 0.0)

    def test_avg_latency(self) -> None:
        slt = SchedulerLatencyTracker()
        slt.record_decision("g1", "admit")
        slt.record_execution_start("g1")
        avg = slt.get_avg_latency()
        self.assertGreaterEqual(avg, 0.0)

    def test_p95_latency(self) -> None:
        slt = SchedulerLatencyTracker()
        slt.record_decision("g1", "admit")
        slt.record_execution_start("g1")
        p95 = slt.get_p95_latency()
        self.assertGreaterEqual(p95, 0.0)

    def test_get_summary(self) -> None:
        slt = SchedulerLatencyTracker()
        slt.record_decision("g1", "admit")
        slt.record_execution_start("g1")
        summary = slt.get_summary()
        self.assertEqual(summary["total_decisions"], 1)
        self.assertEqual(summary["measured"], 1)
        self.assertIn("avg_latency_s", summary)

    def test_get_decisions_filter(self) -> None:
        slt = SchedulerLatencyTracker()
        slt.record_decision("g1", "admit")
        slt.record_execution_start("g1")
        slt.record_decision("g2", "admit")
        slt.record_execution_start("g2")
        g1_decisions = slt.get_decisions("g1")
        self.assertEqual(len(g1_decisions), 1)
        self.assertEqual(g1_decisions[0]["goal_id"], "g1")

    def test_unmeasured(self) -> None:
        slt = SchedulerLatencyTracker()
        slt.record_decision("g1", "admit")
        # no execution_start recorded
        self.assertEqual(slt.get_avg_latency(), 0.0)
        self.assertEqual(slt.get_summary()["measured"], 0)


class TestDeadlineExtensionPolicy(unittest.TestCase):
    """Feature 39: Smart deadline extension."""

    def test_should_extend(self) -> None:
        dep = DeadlineExtensionPolicy(progress_threshold=0.7)
        result = dep.should_extend("g1", 100.0, 85.0, 0.8)
        self.assertTrue(result["extend"])
        self.assertAlmostEqual(result["new_deadline_s"], 150.0)

    def test_should_not_extend_low_progress(self) -> None:
        dep = DeadlineExtensionPolicy(progress_threshold=0.7)
        result = dep.should_extend("g1", 100.0, 50.0, 0.3)
        self.assertFalse(result["extend"])

    def test_should_not_extend_under_threshold(self) -> None:
        dep = DeadlineExtensionPolicy(progress_threshold=0.7)
        result = dep.should_extend("g1", 100.0, 80.0, 0.6)
        self.assertFalse(result["extend"])

    def test_max_extensions(self) -> None:
        dep = DeadlineExtensionPolicy(progress_threshold=0.7, max_extensions=2)
        dep.should_extend("g1", 100.0, 85.0, 0.8)  # 1st
        dep.should_extend("g1", 150.0, 130.0, 0.8)  # 2nd
        result = dep.should_extend("g1", 225.0, 200.0, 0.8)  # would be 3rd
        self.assertFalse(result["extend"])
        self.assertEqual(result["reason"], "max_extensions_reached")

    def test_get_extensions(self) -> None:
        dep = DeadlineExtensionPolicy()
        dep.should_extend("g1", 100.0, 85.0, 0.8)
        exts = dep.get_extensions("g1")
        self.assertEqual(len(exts), 1)
        self.assertEqual(exts[0]["old_deadline_s"], 100.0)

    def test_get_stats(self) -> None:
        dep = DeadlineExtensionPolicy()
        dep.should_extend("g1", 100.0, 85.0, 0.8)
        dep.should_extend("g2", 200.0, 180.0, 0.9)
        stats = dep.get_stats()
        self.assertEqual(stats["total_extensions"], 2)
        self.assertEqual(stats["goals_extended"], 2)


class TestGoalGroupManager(unittest.TestCase):
    """Feature 40: Goal grouping for batch operations."""

    def test_create_group(self) -> None:
        ggm = GoalGroupManager()
        ggm.create_group("g1", ["a", "b", "c"])
        self.assertEqual(ggm.get_group("g1"), {"a", "b", "c"})

    def test_add_to_group(self) -> None:
        ggm = GoalGroupManager()
        ggm.create_group("g1", ["a"])
        ggm.add_to_group("g1", "b")
        self.assertEqual(ggm.get_group("g1"), {"a", "b"})

    def test_get_goal_group(self) -> None:
        ggm = GoalGroupManager()
        ggm.create_group("g1", ["a", "b"])
        self.assertEqual(ggm.get_goal_group("a"), "g1")
        self.assertIsNone(ggm.get_goal_group("c"))

    def test_get_goals_in_group(self) -> None:
        ggm = GoalGroupManager()
        ggm.create_group("g1", ["a", "b"])
        ggm.add_to_group("g1", "c")
        self.assertEqual(ggm.get_goals_in_group("a"), {"a", "b", "c"})

    def test_list_groups(self) -> None:
        ggm = GoalGroupManager()
        ggm.create_group("g1", ["a", "b"])
        ggm.create_group("g2", ["c"])
        groups = ggm.list_groups()
        self.assertEqual(groups["g1"], ["a", "b"])
        self.assertEqual(groups["g2"], ["c"])

    def test_get_stats(self) -> None:
        ggm = GoalGroupManager()
        ggm.create_group("g1", ["a", "b"])
        ggm.create_group("g2", ["c"])
        stats = ggm.get_stats()
        self.assertEqual(stats["groups"], 2)
        self.assertEqual(stats["goals_grouped"], 3)


class TestAdmissionPolicyChain(unittest.TestCase):
    """Feature 41: Chained admission policies."""

    def test_admit_all_pass(self) -> None:
        apc = AdmissionPolicyChain()
        class PassPolicy:
            def admit(self, goal_id):
                return {"admitted": True}
        apc.add_policy(PassPolicy(), "pass")
        result = apc.admit("g1")
        self.assertTrue(result["admitted"])

    def test_reject_by_policy(self) -> None:
        apc = AdmissionPolicyChain()
        class FailPolicy:
            def admit(self, goal_id):
                return {"admitted": False, "reason": "denied"}
        apc.add_policy(FailPolicy(), "fail")
        result = apc.admit("g1")
        self.assertFalse(result["admitted"])
        self.assertEqual(result["rejected_by"], "fail")
        self.assertEqual(result["reason"], "denied")

    def test_chain_order(self) -> None:
        apc = AdmissionPolicyChain()
        order = []
        class RecordingPolicy:
            def __init__(self, name: str, admit: bool):
                self._name = name
                self._admit = admit
            def admit(self, goal_id):
                order.append(self._name)
                return {"admitted": self._admit}
        apc.add_policy(RecordingPolicy("first", True), "first")
        apc.add_policy(RecordingPolicy("second", False), "second")
        apc.add_policy(RecordingPolicy("third", True), "third")
        result = apc.admit("g1")
        self.assertFalse(result["admitted"])
        self.assertEqual(result["rejected_by"], "second")
        self.assertEqual(order, ["first", "second"])

    def test_get_rejections(self) -> None:
        apc = AdmissionPolicyChain()
        class FailPolicy:
            def admit(self, goal_id):
                return {"admitted": False, "reason": "no"}
        apc.add_policy(FailPolicy(), "fail")
        apc.admit("g1")
        apc.admit("g2")
        rej = apc.get_rejections()
        self.assertEqual(len(rej), 2)
        g1_rej = apc.get_rejections("g1")
        self.assertEqual(len(g1_rej), 1)

    def test_no_policies(self) -> None:
        apc = AdmissionPolicyChain()
        result = apc.admit("g1")
        self.assertTrue(result["admitted"])
        self.assertEqual(result["policies_passed"], 0)

    def test_get_stats(self) -> None:
        apc = AdmissionPolicyChain()
        class P:
            def admit(self, goal_id):
                return {"admitted": True}
        apc.add_policy(P(), "p1")
        apc.add_policy(P(), "p2")
        stats = apc.get_stats()
        self.assertEqual(stats["policies"], 2)


class TestGoalRetryBudgetResolver(unittest.TestCase):
    """Feature 42: Retry budget allocation across goals."""

    def test_allocate(self) -> None:
        grb = GoalRetryBudgetResolver(total_budget=10)
        alloc = grb.allocate("g1", priority=1, max_retries=3)
        self.assertGreater(alloc, 0)
        self.assertLessEqual(alloc, 3)

    def test_allocate_multiple(self) -> None:
        grb = GoalRetryBudgetResolver(total_budget=10)
        grb.allocate("g1", max_retries=3)
        grb.allocate("g2", max_retries=3)
        budgets = grb.get_budgets()
        self.assertIn("g1", budgets)
        self.assertIn("g2", budgets)

    def test_consume(self) -> None:
        grb = GoalRetryBudgetResolver(total_budget=10)
        grb.allocate("g1", max_retries=3)
        consumed = grb.consume("g1", 1)
        self.assertTrue(consumed)
        remaining = grb.get_remaining("g1")
        self.assertEqual(remaining, 2)

    def test_consume_over_budget(self) -> None:
        grb = GoalRetryBudgetResolver(total_budget=3)
        grb.allocate("g1", max_retries=3)
        consumed = grb.consume("g1", 4)
        self.assertFalse(consumed)

    def test_total_remaining(self) -> None:
        grb = GoalRetryBudgetResolver(total_budget=10)
        grb.allocate("g1", max_retries=3)
        grb.consume("g1", 1)
        self.assertEqual(grb.get_total_remaining(), 9)
        self.assertEqual(grb.get_remaining("g1"), 2)

    def test_get_stats(self) -> None:
        grb = GoalRetryBudgetResolver(total_budget=10)
        grb.allocate("g1", max_retries=3)
        stats = grb.get_stats()
        self.assertEqual(stats["total_budget"], 10)
        self.assertEqual(stats["goals"], 1)


class TestGoalProgressTracker(unittest.TestCase):
    """Feature 43: Subtask progress tracking."""

    def test_init_and_complete(self) -> None:
        gt = GoalProgressTracker()
        gt.init_goal("g1", 5)
        for _ in range(3):
            gt.complete_subtask("g1")
        result = gt.get_progress("g1")
        self.assertEqual(result["completed"], 3)
        self.assertEqual(result["pending"], 2)
        self.assertEqual(result["percentage"], 60.0)

    def test_fail_subtask(self) -> None:
        gt = GoalProgressTracker()
        gt.init_goal("g1", 5)
        gt.fail_subtask("g1")
        result = gt.get_progress("g1")
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["pending"], 4)

    def test_complete(self) -> None:
        gt = GoalProgressTracker()
        gt.init_goal("g1", 2)
        gt.complete_subtask("g1")
        gt.complete_subtask("g1")
        result = gt.get_progress("g1")
        self.assertTrue(result["complete"])
        self.assertEqual(result["percentage"], 100.0)

    def test_unknown_goal(self) -> None:
        gt = GoalProgressTracker()
        result = gt.get_progress("unknown")
        self.assertEqual(result["error"], "not_found")

    def test_get_all_progress(self) -> None:
        gt = GoalProgressTracker()
        gt.init_goal("g1", 5)
        gt.init_goal("g2", 3)
        all_p = gt.get_all_progress()
        self.assertIn("g1", all_p)
        self.assertIn("g2", all_p)

    def test_get_completion_rate(self) -> None:
        gt = GoalProgressTracker()
        gt.init_goal("g1", 10)
        gt.init_goal("g2", 10)
        for _ in range(5):
            gt.complete_subtask("g1")
        for _ in range(3):
            gt.complete_subtask("g2")
        rate = gt.get_completion_rate()
        self.assertEqual(rate["total_subtasks"], 20)
        self.assertEqual(rate["completed"], 8)
        self.assertAlmostEqual(rate["completion_rate"], 0.4)

    def test_complete_subtask_not_found(self) -> None:
        gt = GoalProgressTracker()
        result = gt.complete_subtask("unknown")
        self.assertEqual(result["error"], "not_found")

    def test_no_pending(self) -> None:
        gt = GoalProgressTracker()
        gt.init_goal("g1", 1)
        gt.complete_subtask("g1")
        result = gt.complete_subtask("g1")
        self.assertEqual(result["error"], "no_pending")


class TestConfigurableRetryPolicy(unittest.TestCase):
    """Feature 44: Configurable retry strategy."""

    def test_exponential(self) -> None:
        crp = ConfigurableRetryPolicy()
        crp.configure("g1", strategy="exponential", base_delay_s=1.0)
        d1 = crp.get_delay("g1", 1, "")
        d2 = crp.get_delay("g1", 2, "")
        d3 = crp.get_delay("g1", 3, "")
        self.assertAlmostEqual(d1["delay_s"], 1.0)
        self.assertAlmostEqual(d2["delay_s"], 2.0)
        self.assertAlmostEqual(d3["delay_s"], 4.0)

    def test_linear(self) -> None:
        crp = ConfigurableRetryPolicy()
        crp.configure("g1", strategy="linear", base_delay_s=2.0, step_s=1.0)
        d1 = crp.get_delay("g1", 1, "")
        d2 = crp.get_delay("g1", 2, "")
        self.assertAlmostEqual(d1["delay_s"], 2.0)
        self.assertAlmostEqual(d2["delay_s"], 4.0)

    def test_fixed(self) -> None:
        crp = ConfigurableRetryPolicy()
        crp.configure("g1", strategy="fixed", base_delay_s=5.0)
        d1 = crp.get_delay("g1", 1, "")
        d2 = crp.get_delay("g1", 2, "")
        self.assertAlmostEqual(d1["delay_s"], 5.0)
        self.assertAlmostEqual(d2["delay_s"], 5.0)

    def test_none(self) -> None:
        crp = ConfigurableRetryPolicy()
        crp.configure("g1", strategy="none")
        d = crp.get_delay("g1", 1, "seed")
        self.assertEqual(d["delay_s"], 0.0)

    def test_should_retry(self) -> None:
        crp = ConfigurableRetryPolicy()
        crp.configure("g1", strategy="exponential")
        self.assertTrue(crp.should_retry("g1", 1, 3))
        self.assertTrue(crp.should_retry("g1", 2, 3))
        self.assertFalse(crp.should_retry("g1", 3, 3))

    def test_none_no_retry(self) -> None:
        crp = ConfigurableRetryPolicy()
        crp.configure("g1", strategy="none")
        self.assertFalse(crp.should_retry("g1", 1, 3))

    def test_get_policy(self) -> None:
        crp = ConfigurableRetryPolicy()
        crp.configure("g1", strategy="exponential", base_delay_s=1.0)
        policy = crp.get_policy("g1")
        self.assertIsNotNone(policy)
        self.assertEqual(policy["strategy"], "exponential")

    def test_get_all_policies(self) -> None:
        crp = ConfigurableRetryPolicy()
        crp.configure("g1", strategy="exponential")
        crp.configure("g2", strategy="fixed")
        all_p = crp.get_all_policies()
        self.assertEqual(len(all_p), 2)

    def test_default_policy(self) -> None:
        crp = ConfigurableRetryPolicy()
        d = crp.get_delay("unknown", 1, "seed")
        self.assertEqual(d["strategy"], "none")


class TestSubtaskFailureAggregator(unittest.TestCase):
    """Feature 45: Subtask failure aggregation."""

    def test_record_failure(self) -> None:
        sfa = SubtaskFailureAggregator()
        sfa.record_failure("g1", "t1", ValueError("err"))
        failures = sfa.get_failures("g1")
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["subtask_id"], "t1")

    def test_get_summary(self) -> None:
        sfa = SubtaskFailureAggregator()
        sfa.record_failure("g1", "t1", ValueError("err1"))
        sfa.record_failure("g1", "t2", ValueError("err1"))
        sfa.record_failure("g1", "t3", TypeError("err2"))
        summary = sfa.get_summary("g1")
        self.assertEqual(summary["total_failures"], 3)
        self.assertEqual(summary["root_cause"], "err1")
        self.assertEqual(summary["most_common"], "ValueError")
        self.assertEqual(summary["unique_error_types"], 2)

    def test_empty_summary(self) -> None:
        sfa = SubtaskFailureAggregator()
        summary = sfa.get_summary("unknown")
        self.assertEqual(summary["total_failures"], 0)

    def test_clear(self) -> None:
        sfa = SubtaskFailureAggregator()
        sfa.record_failure("g1", "t1", ValueError("err"))
        sfa.clear("g1")
        self.assertEqual(len(sfa.get_failures("g1")), 0)

    def test_multiple_goals(self) -> None:
        sfa = SubtaskFailureAggregator()
        sfa.record_failure("g1", "t1", ValueError("err"))
        sfa.record_failure("g2", "t2", TypeError("err"))
        self.assertEqual(len(sfa.get_failures("g1")), 1)
        self.assertEqual(len(sfa.get_failures("g2")), 1)


if __name__ == "__main__":
    unittest.main()



# =============================================================================
# Tests for PR #80 - 10 governed scheduler features
# =============================================================================


class TestCriticalPathHighlight(unittest.TestCase):
    """Feature 1 (PR80): DAG critical-path highlight."""

    def test_compute(self) -> None:
        ch = CriticalPathHighlight()
        ch._resolver.add_goal("a", ["b"])
        ch._resolver.add_goal("b", ["c"])
        ch._resolver.add_goal("c")
        result = ch.compute()
        self.assertEqual(result["critical_path"], ["c", "b", "a"])
        self.assertEqual(result["critical_path_length"], 3)
        self.assertIn("a", result["highlighted_nodes"])
        self.assertIn("b", result["highlighted_nodes"])
        self.assertIn("c", result["highlighted_nodes"])

    def test_is_critical(self) -> None:
        ch = CriticalPathHighlight()
        ch._resolver.add_goal("a", ["b"])
        ch._resolver.add_goal("b")
        ch.compute()
        self.assertTrue(ch.is_critical("a"))
        self.assertFalse(ch.is_critical("nonexistent"))

    def test_is_critical_edge(self) -> None:
        ch = CriticalPathHighlight()
        ch._resolver.add_goal("a", ["b"])
        ch._resolver.add_goal("b")
        ch.compute()
        self.assertTrue(ch.is_critical_edge("b", "a"))
        self.assertFalse(ch.is_critical_edge("a", "b"))

    def test_get_highlighted_viz(self) -> None:
        ch = CriticalPathHighlight()
        ch._resolver.add_goal("a", ["b"])
        ch._resolver.add_goal("b")
        viz = ch.get_highlighted_viz()
        self.assertIn("nodes", viz)
        self.assertIn("edges", viz)
        critical_nodes = [n for n in viz["nodes"] if n["critical"]]
        self.assertGreater(len(critical_nodes), 0)

    def test_empty_dag(self) -> None:
        ch = CriticalPathHighlight()
        result = ch.compute()
        self.assertEqual(result["critical_path"], [])
        self.assertEqual(result["critical_path_length"], 0)

    def test_get_stats(self) -> None:
        ch = CriticalPathHighlight()
        ch._resolver.add_goal("a", ["b"])
        ch._resolver.add_goal("b")
        ch.compute()
        stats = ch.get_stats()
        self.assertEqual(stats["critical_path_length"], 2)
        self.assertEqual(stats["critical_nodes"], 2)


class TestPriorityAging(unittest.TestCase):
    """Feature 2 (PR80): Priority aging."""

    def test_no_aging_when_fresh(self) -> None:
        pa = PriorityAging(aging_threshold_s=100.0)
        pa.register("g1", priority=0)
        result = pa.apply_aging("g1")
        self.assertFalse(result["aged"])

    def test_aging_after_threshold(self) -> None:
        pa = PriorityAging(aging_threshold_s=0.001, boost_amount=5, max_boosts=3)
        pa.register("g1", priority=0)
        time.sleep(0.01)
        result = pa.apply_aging("g1")
        self.assertTrue(result["aged"])
        self.assertEqual(result["old_priority"], 0)
        self.assertEqual(result["new_priority"], 5)

    def test_max_boosts_enforced(self) -> None:
        pa = PriorityAging(aging_threshold_s=0.001, boost_amount=5, max_boosts=2)
        pa.register("g1", priority=0)
        pa._boost_counts["g1"] = 2
        pa._enqueued_at["g1"] = 0
        result = pa.apply_aging("g1")
        self.assertFalse(result["aged"])

    def test_get_priority(self) -> None:
        pa = PriorityAging(boost_amount=10)
        pa.register("g1", priority=5)
        self.assertEqual(pa.get_priority("g1"), 5)

    def test_reset(self) -> None:
        pa = PriorityAging(aging_threshold_s=0.001, boost_amount=5)
        pa.register("g1", priority=0)
        time.sleep(0.01)
        pa.apply_aging("g1")
        pa.reset("g1")
        self.assertEqual(pa.get_priority("g1"), 0)

    def test_get_stats(self) -> None:
        pa = PriorityAging()
        pa.register("g1")
        pa.register("g2")
        stats = pa.get_stats()
        self.assertEqual(stats["registered"], 2)


class TestDeadlineMode(unittest.TestCase):
    """Feature 3 (PR80): Soft/hard deadline modes."""

    def test_soft_deadline_not_breached(self) -> None:
        dm = DeadlineMode(default_mode=DeadlineMode.SOFT)
        dm.set_deadline("g1", deadline_s=100.0, mode=DeadlineMode.SOFT)
        dm.register_start("g1", start_time=time.monotonic() - 50.0)
        result = dm.check("g1")
        self.assertFalse(result["breached"])

    def test_soft_deadline_breached(self) -> None:
        dm = DeadlineMode(default_mode=DeadlineMode.SOFT)
        dm.set_deadline("g1", deadline_s=1.0, mode=DeadlineMode.SOFT)
        dm.register_start("g1", start_time=time.monotonic() - 5.0)
        result = dm.check("g1")
        self.assertTrue(result["breached"])
        self.assertEqual(result["action"], "deprioritize")

    def test_hard_deadline_breached(self) -> None:
        dm = DeadlineMode(default_mode=DeadlineMode.HARD)
        dm.set_deadline("g1", deadline_s=1.0, mode=DeadlineMode.HARD)
        dm.register_start("g1", start_time=time.monotonic() - 5.0)
        result = dm.check("g1")
        self.assertTrue(result["breached"])
        self.assertEqual(result["action"], "cancel")

    def test_no_deadline_set(self) -> None:
        dm = DeadlineMode()
        result = dm.check("unknown")
        self.assertFalse(result["breached"])
        self.assertEqual(result["reason"], "no_deadline_set")

    def test_get_stats(self) -> None:
        dm = DeadlineMode()
        dm.set_deadline("g1", 10.0, mode=DeadlineMode.SOFT)
        dm.register_start("g1", start_time=time.monotonic() - 5.0)
        dm.check("g1")
        stats = dm.get_stats()
        self.assertEqual(stats["tracked_goals"], 1)


class TestJobGroupFanInGate(unittest.TestCase):
    """Feature 4 (PR80): Job groups with fan-in gate."""

    def test_all_succeed_all_must_succeed(self) -> None:
        gate = JobGroupFanInGate(fail_policy=JobGroupFanInGate.ALL_MUST_SUCCEED)
        gate.create_group("g1", ["a", "b", "c"])
        gate.record_member_result("g1", "a", "success")
        gate.record_member_result("g1", "b", "success")
        gate.record_member_result("g1", "c", "success")
        result = gate.check_gate("g1")
        self.assertTrue(result["complete"])
        self.assertTrue(result["success"])
        self.assertEqual(result["succeeded"], 3)

    def test_partial_completion_waiting(self) -> None:
        gate = JobGroupFanInGate()
        gate.create_group("g1", ["a", "b"])
        gate.record_member_result("g1", "a", "success")
        result = gate.check_gate("g1")
        self.assertFalse(result["complete"])
        self.assertEqual(result["members_pending"], 1)

    def test_fail_policy_all_fail(self) -> None:
        gate = JobGroupFanInGate(fail_policy=JobGroupFanInGate.ALL_FAIL)
        gate.create_group("g1", ["a", "b"])
        gate.record_member_result("g1", "a", "success")
        gate.record_member_result("g1", "b", "failed")
        result = gate.check_gate("g1")
        self.assertFalse(result["success"])
        self.assertEqual(result["result"], "failed")

    def test_fail_policy_majority_fail(self) -> None:
        gate = JobGroupFanInGate(fail_policy=JobGroupFanInGate.MAJORITY_FAIL)
        gate.create_group("g1", ["a", "b", "c"])
        gate.record_member_result("g1", "a", "success")
        gate.record_member_result("g1", "b", "failed")
        gate.record_member_result("g1", "c", "success")
        result = gate.check_gate("g1")
        self.assertTrue(result["success"])

    def test_get_group_status(self) -> None:
        gate = JobGroupFanInGate()
        gate.create_group("g1", ["a", "b"])
        status = gate.get_group_status("g1")
        self.assertEqual(status["total"], 2)

    def test_get_stats(self) -> None:
        gate = JobGroupFanInGate()
        gate.create_group("g1", ["a", "b"])
        gate.create_group("g2", ["c"])
        stats = gate.get_stats()
        self.assertEqual(stats["groups"], 2)


class TestTenantFairShare(unittest.TestCase):
    """Feature 5 (PR80): Per-tenant fair-share weights."""

    def test_next_tenant(self) -> None:
        tfs = TenantFairShare()
        tfs.set_weight("tenant_a", 2.0)
        tfs.set_weight("tenant_b", 1.0)
        order = []
        for _ in range(3):
            order.append(tfs.next_tenant())
        self.assertEqual(order[0], "tenant_a")
        self.assertEqual(order[1], "tenant_a")
        self.assertEqual(order[2], "tenant_b")

    def test_get_weight(self) -> None:
        tfs = TenantFairShare()
        tfs.set_weight("t1", 5.0)
        self.assertEqual(tfs.get_weight("t1"), 5.0)
        self.assertEqual(tfs.get_weight("unknown"), 1.0)

    def test_get_share(self) -> None:
        tfs = TenantFairShare()
        tfs.set_weight("t1", 3.0)
        tfs.set_weight("t2", 1.0)
        share1 = tfs.get_share("t1")
        share2 = tfs.get_share("t2")
        self.assertAlmostEqual(share1, 0.75, places=4)
        self.assertAlmostEqual(share2, 0.25, places=4)

    def test_empty(self) -> None:
        tfs = TenantFairShare()
        self.assertIsNone(tfs.next_tenant())

    def test_get_stats(self) -> None:
        tfs = TenantFairShare()
        tfs.set_weight("t1", 1.0)
        tfs.set_weight("t2", 2.0)
        stats = tfs.get_stats()
        self.assertEqual(stats["tenants"], 2)
        self.assertEqual(stats["total_weight"], 3.0)


class TestRetryBudgetWithJitter(unittest.TestCase):
    """Feature 6 (PR80): Retry budget + jitter."""

    def test_allocate(self) -> None:
        rb = RetryBudgetWithJitter(max_retries=3)
        budget = rb.allocate("g1")
        self.assertEqual(budget.max_retries, 3)

    def test_calculate_delay_exponential(self) -> None:
        rb = RetryBudgetWithJitter(base_delay_s=1.0)
        d1 = rb.calculate_delay("g1", 1, "seed")
        d2 = rb.calculate_delay("g1", 2, "seed")
        d3 = rb.calculate_delay("g1", 3, "seed")
        self.assertAlmostEqual(d1["base_delay_s"], 1.0)
        self.assertAlmostEqual(d2["base_delay_s"], 2.0)
        self.assertAlmostEqual(d3["base_delay_s"], 4.0)
        self.assertGreater(d1["jitter"], 0)
        self.assertLessEqual(d1["jitter"], d1["base_delay_s"] * 0.5)

    def test_can_retry(self) -> None:
        rb = RetryBudgetWithJitter(max_retries=2)
        rb.allocate("g1")
        self.assertTrue(rb.can_retry("g1")[0])
        rb.consume_retry("g1")
        self.assertTrue(rb.can_retry("g1")[0])
        rb.consume_retry("g1")
        self.assertFalse(rb.can_retry("g1")[0])

    def test_consume_retry_updates_ledger(self) -> None:
        rb = RetryBudgetWithJitter(max_retries=3)
        rb.allocate("g1")
        rb.consume_retry("g1")
        ledger = rb.get_ledger()
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0]["goal_id"], "g1")

    def test_get_budget(self) -> None:
        rb = RetryBudgetWithJitter(max_retries=5)
        rb.allocate("g1")
        rb.consume_retry("g1")
        budget = rb.get_budget("g1")
        self.assertEqual(budget["allocated"], 5)
        self.assertEqual(budget["consumed"], 1)
        self.assertEqual(budget["remaining"], 4)

    def test_get_stats(self) -> None:
        rb = RetryBudgetWithJitter(max_retries=3)
        rb.allocate("g1")
        rb.allocate("g2")
        rb.consume_retry("g1")
        stats = rb.get_stats()
        self.assertEqual(stats["goals"], 2)
        self.assertEqual(stats["total_consumed"], 1)


class TestIdempotencyStore(unittest.TestCase):
    """Feature 7 (PR80): Idempotency keys."""

    def test_enqueue_new(self) -> None:
        store = IdempotencyStore()
        result = store.enqueue("key1", "job-1")
        self.assertTrue(result["enqueued"])
        self.assertEqual(result["job_id"], "job-1")

    def test_duplicate_key_rejected(self) -> None:
        store = IdempotencyStore()
        store.enqueue("key1", "job-1")
        result = store.enqueue("key1", "job-2")
        self.assertFalse(result["enqueued"])
        self.assertEqual(result["existing_job_id"], "job-1")
        self.assertEqual(result["reason"], "duplicate_idempotency_key")

    def test_get(self) -> None:
        store = IdempotencyStore()
        store.enqueue("key1", "job-1")
        result = store.get("key1")
        self.assertIsNotNone(result)
        self.assertEqual(result["job_id"], "job-1")

    def test_exists(self) -> None:
        store = IdempotencyStore()
        store.enqueue("key1", "job-1")
        self.assertTrue(store.exists("key1"))
        self.assertFalse(store.exists("unknown"))

    def test_remove(self) -> None:
        store = IdempotencyStore()
        store.enqueue("key1", "job-1")
        self.assertTrue(store.remove("key1"))
        self.assertFalse(store.exists("key1"))

    def test_get_stats(self) -> None:
        store = IdempotencyStore()
        store.enqueue("key1", "job-1")
        store.enqueue("key2", "job-2")
        store.enqueue("key1", "job-dup")
        stats = store.get_stats()
        self.assertEqual(stats["total_keys"], 2)
        self.assertEqual(stats["duplicates_rejected"], 1)


class TestQueuePauseResume(unittest.TestCase):
    """Feature 8 (PR80): Pause/resume queue."""

    def test_pause(self) -> None:
        qr = QueuePauseResume()
        result = qr.pause("operator")
        self.assertTrue(qr.is_paused)
        self.assertEqual(result["action"], "pause")

    def test_resume(self) -> None:
        qr = QueuePauseResume()
        qr.pause("operator")
        result = qr.resume()
        self.assertFalse(qr.is_paused)
        self.assertEqual(result["action"], "resume")

    def test_should_admit_paused(self) -> None:
        qr = QueuePauseResume()
        qr.pause("operator")
        allowed, reason = qr.should_admit()
        self.assertFalse(allowed)
        self.assertEqual(reason, "queue_paused")

    def test_should_admit_resumed(self) -> None:
        qr = QueuePauseResume()
        allowed, reason = qr.should_admit()
        self.assertTrue(allowed)
        self.assertEqual(reason, "admission_allowed")

    def test_record_drained(self) -> None:
        qr = QueuePauseResume()
        qr.pause("operator")
        qr.record_drained("g1")
        info = qr.get_pause_info()
        self.assertIn("g1", info["drained"])

    def test_get_stats(self) -> None:
        qr = QueuePauseResume()
        qr.pause("op")
        qr.resume()
        qr.pause("op2")
        qr.resume()
        stats = qr.get_stats()
        self.assertEqual(stats["pause_count"], 2)
        self.assertEqual(stats["resume_count"], 2)


class TestSLABreachEmitter(unittest.TestCase):
    """Feature 9 (PR80): SLA breach events."""

    def test_latency_breach(self) -> None:
        emitter = SLABreachEmitter()
        emitter.set_sla("g1", latency_s=5.0)
        breach = emitter.check_latency("g1", 10.0)
        self.assertIsNotNone(breach)
        self.assertEqual(breach["breach_type"], "latency")
        self.assertEqual(breach["severity"], "warning")

    def test_latency_ok(self) -> None:
        emitter = SLABreachEmitter()
        emitter.set_sla("g1", latency_s=10.0)
        breach = emitter.check_latency("g1", 5.0)
        self.assertIsNone(breach)

    def test_deadline_breach(self) -> None:
        emitter = SLABreachEmitter()
        emitter.set_sla("g1", deadline_s=5.0)
        breach = emitter.check_deadline("g1", 10.0)
        self.assertIsNotNone(breach)
        self.assertEqual(breach["breach_type"], "deadline")
        self.assertEqual(breach["severity"], "critical")

    def test_no_sla_set(self) -> None:
        emitter = SLABreachEmitter()
        breach = emitter.check_latency("unknown", 10.0)
        self.assertIsNone(breach)
        breach2 = emitter.check_deadline("unknown", 10.0)
        self.assertIsNone(breach2)

    def test_get_breaches_for_goal(self) -> None:
        emitter = SLABreachEmitter()
        emitter.set_sla("g1", latency_s=5.0)
        emitter.check_latency("g1", 10.0)
        emitter.set_sla("g2", latency_s=5.0)
        emitter.check_latency("g2", 10.0)
        breaches = emitter.get_breaches_for_goal("g1")
        self.assertEqual(len(breaches), 1)
        self.assertEqual(breaches[0]["goal_id"], "g1")

    def test_get_stats(self) -> None:
        emitter = SLABreachEmitter()
        emitter.set_sla("g1", latency_s=5.0)
        emitter.check_latency("g1", 10.0)
        emitter.set_sla("g2", deadline_s=5.0)
        emitter.check_deadline("g2", 10.0)
        stats = emitter.get_stats()
        self.assertEqual(stats["total_breaches"], 2)
        self.assertEqual(stats["latency_breaches"], 1)
        self.assertEqual(stats["deadline_breaches"], 1)


class TestSchedulerPolicyPackV2(unittest.TestCase):
    """Feature 10 (PR80): Scheduler policy pack v2."""

    def test_load_from_dict(self) -> None:
        pack = SchedulerPolicyPackV2()
        policy = {
            "version": "v2",
            "priority": {"default": 50},
            "deadlines": {"default_s": 300},
            "retry": {"max_retries": 3},
        }
        result = pack.load_from_dict("policy1", policy)
        self.assertTrue(result["loaded"])
        self.assertEqual(result["version"], "v2")

    def test_load_from_json(self) -> None:
        pack = SchedulerPolicyPackV2()
        json_str = '{"version": "v2", "priority": {"default": 50}}'
        result = pack.load_from_json("policy1", json_str)
        self.assertTrue(result["loaded"])

    def test_get_policy_sections(self) -> None:
        pack = SchedulerPolicyPackV2()
        policy = {
            "version": "v2",
            "priority": {"default": 50},
            "deadlines": {"default_s": 300},
            "fair_share": {"strategy": "weighted"},
            "retry": {"max_retries": 3},
        }
        pack.load_from_dict("policy1", policy)
        self.assertEqual(pack.get_priority_policy("policy1"), {"default": 50})
        self.assertEqual(pack.get_deadline_policy("policy1"), {"default_s": 300})
        self.assertEqual(pack.get_fair_share_policy("policy1"), {"strategy": "weighted"})
        self.assertEqual(pack.get_retry_policy("policy1"), {"max_retries": 3})

    def test_validate_valid(self) -> None:
        pack = SchedulerPolicyPackV2()
        policy = {"version": "v2", "priority": {"default": 50}}
        pack.load_from_dict("policy1", policy)
        result = pack.validate("policy1")
        self.assertTrue(result["valid"])

    def test_validate_missing_fields(self) -> None:
        pack = SchedulerPolicyPackV2()
        policy = {"priority": {"default": 50}}
        pack.load_from_dict("policy1", policy)
        result = pack.validate("policy1")
        self.assertFalse(result["valid"])
        self.assertIn("version", result["missing"])

    def test_validate_not_found(self) -> None:
        pack = SchedulerPolicyPackV2()
        result = pack.validate("nonexistent")
        self.assertFalse(result["valid"])

    def test_list_policies(self) -> None:
        pack = SchedulerPolicyPackV2()
        pack.load_from_dict("p1", {"version": "v2", "priority": {}})
        pack.load_from_dict("p2", {"version": "v2", "priority": {}})
        policies = pack.list_policies()
        self.assertEqual(len(policies), 2)
        self.assertIn("p1", policies)

    def test_get_stats(self) -> None:
        pack = SchedulerPolicyPackV2()
        pack.load_from_dict("p1", {"version": "v2", "priority": {}})
        stats = pack.get_stats()
        self.assertEqual(stats["version"], "v2")
        self.assertEqual(stats["total_policies"], 1)



# =============================================================================
# Tests for PR #81 - 5 major governed scheduler features
# =============================================================================


class TestMultiQueueRouting(unittest.TestCase):
    """Feature 1 (PR81): Multi-queue routing with affinity."""

    def test_route_by_tenant(self) -> None:
        mqr = MultiQueueRouting()
        mqr.register_queue("q1", tenant_ids=["tenant_a"], capabilities=["compute"])
        result = mqr.route("job1", tenant_id="tenant_a")
        self.assertTrue(result["routed"])
        self.assertEqual(result["queue_id"], "q1")

    def test_route_by_capability(self) -> None:
        mqr = MultiQueueRouting()
        mqr.register_queue("q1", tenant_ids=["tenant_a"], capabilities=["compute"])
        result = mqr.route("job1", capability="compute")
        self.assertTrue(result["routed"])
        self.assertEqual(result["queue_id"], "q1")

    def test_fail_closed_no_queue(self) -> None:
        mqr = MultiQueueRouting()
        result = mqr.route("job1", tenant_id="unknown")
        self.assertFalse(result["routed"])
        self.assertEqual(result["reason"], "no_matching_queue_fail_closed")

    def test_sticky_affinity(self) -> None:
        mqr = MultiQueueRouting()
        mqr.register_queue("q1", tenant_ids=["tenant_a"], capabilities=["compute"])
        mqr.route("job1", tenant_id="tenant_a")
        mqr.route("job2", tenant_id="tenant_a")
        self.assertEqual(mqr._queue_assignments["job1"], "q1")
        self.assertEqual(mqr._queue_assignments["job2"], "q1")

    def test_get_queue_jobs(self) -> None:
        mqr = MultiQueueRouting()
        mqr.register_queue("q1", tenant_ids=["t1"], capabilities=["c1"])
        mqr.route("j1", tenant_id="t1")
        mqr.route("j2", tenant_id="t1")
        jobs = mqr.get_queue_jobs("q1")
        self.assertEqual(len(jobs), 2)

    def test_get_stats(self) -> None:
        mqr = MultiQueueRouting()
        mqr.register_queue("q1", tenant_ids=["t1"], capabilities=["c1"])
        mqr.route("j1", tenant_id="t1")
        stats = mqr.get_queue_stats()
        self.assertEqual(stats["queues"], 1)
        self.assertEqual(stats["total_routed"], 1)


class TestBackpressureAdmissionV2(unittest.TestCase):
    """Feature 2 (PR81): Backpressure + admission control v2."""

    def test_admit_within_limits(self) -> None:
        bp = BackpressureAdmissionV2(global_max_concurrency=5)
        result = bp.admit("job1", tenant_id="t1")
        self.assertTrue(result["admitted"])
        self.assertEqual(result["action"], "admit")

    def test_shed_when_global_exceeded(self) -> None:
        bp = BackpressureAdmissionV2(global_max_concurrency=2)
        bp.admit("j1", tenant_id="t1")
        bp.admit("j2", tenant_id="t1")
        result = bp.admit("j3", tenant_id="t1")
        self.assertFalse(result["admitted"])
        self.assertEqual(result["action"], "shed")

    def test_defer_when_tenant_exceeded(self) -> None:
        bp = BackpressureAdmissionV2(per_tenant_max_concurrency=2)
        bp.admit("j1", tenant_id="t1")
        bp.admit("j2", tenant_id="t1")
        result = bp.admit("j3", tenant_id="t1")
        self.assertFalse(result["admitted"])
        self.assertEqual(result["action"], "defer")

    def test_release(self) -> None:
        bp = BackpressureAdmissionV2(global_max_concurrency=2)
        bp.admit("j1", tenant_id="t1")
        bp.admit("j2", tenant_id="t2")
        bp.release("j1")
        result = bp.admit("j3", tenant_id="t3")
        self.assertTrue(result["admitted"])

    def test_set_queue_depth_warning(self) -> None:
        bp = BackpressureAdmissionV2()
        bp.set_queue_depth(25)
        events = bp.get_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["action"], "warning")

    def test_get_stats(self) -> None:
        bp = BackpressureAdmissionV2()
        bp.admit("j1", tenant_id="t1")
        stats = bp.get_stats()
        self.assertEqual(stats["global_active"], 1)
        self.assertIn("backpressure_events", stats)


class TestDurableJobCheckpoints(unittest.TestCase):
    """Feature 3 (PR81): Durable job checkpoints + resume."""

    def test_save_checkpoint(self) -> None:
        dc = DurableJobCheckpoints()
        cp = dc.save_checkpoint("job1", "step1", {"state": "running"})
        self.assertIn("checkpoint_id", cp)
        self.assertEqual(cp["job_id"], "job1")
        self.assertEqual(cp["step_id"], "step1")

    def test_get_latest_checkpoint(self) -> None:
        dc = DurableJobCheckpoints()
        dc.save_checkpoint("job1", "step1", {})
        dc.save_checkpoint("job1", "step2", {})
        cp = dc.get_latest_checkpoint("job1")
        self.assertIsNotNone(cp)
        self.assertEqual(cp["step_id"], "step2")

    def test_resume(self) -> None:
        dc = DurableJobCheckpoints()
        dc.save_checkpoint("job1", "step1", {})
        dc.mark_step_complete("job1", "step1")
        result = dc.resume("job1")
        self.assertTrue(result["resumed"])
        self.assertEqual(result["completed_steps"], 1)

    def test_resume_with_idempotency(self) -> None:
        dc = DurableJobCheckpoints()
        dc.save_checkpoint("job1", "step1", {})
        result = dc.resume("job1", idempotency_key="key1")
        self.assertEqual(result["idempotency_key"], "key1")
        self.assertEqual(result["idempotency_mode"], "keyed")

    def test_mark_step_complete(self) -> None:
        dc = DurableJobCheckpoints()
        dc.mark_step_complete("job1", "step1")
        self.assertTrue(dc.is_step_completed("job1", "step1"))
        self.assertFalse(dc.is_step_completed("job1", "step2"))

    def test_can_resume(self) -> None:
        dc = DurableJobCheckpoints()
        self.assertFalse(dc.can_resume("job1"))
        dc.save_checkpoint("job1", "step1", {})
        self.assertTrue(dc.can_resume("job1"))

    def test_get_stats(self) -> None:
        dc = DurableJobCheckpoints()
        dc.save_checkpoint("job1", "step1", {})
        stats = dc.get_stats()
        self.assertEqual(stats["jobs"], 1)
        self.assertEqual(stats["total_checkpoints"], 1)


class TestDAGExecutionEngine(unittest.TestCase):
    """Feature 4 (PR81): Dependency DAG execution engine."""

    def test_add_job_and_ready(self) -> None:
        dag = DAGExecutionEngine()
        dag.add_job("a")
        dag.add_job("b", depends_on=["a"])
        ready = dag.get_ready_jobs()
        self.assertIn("a", ready)
        self.assertNotIn("b", ready)

    def test_mark_completed(self) -> None:
        dag = DAGExecutionEngine()
        dag.add_job("a")
        dag.mark_completed("a", result="ok")
        self.assertEqual(dag.get_status("a"), "completed")
        self.assertTrue(dag.is_completed("a"))

    def test_mark_failed_cancels_downstream(self) -> None:
        dag = DAGExecutionEngine()
        dag.add_job("a")
        dag.add_job("b", depends_on=["a"])
        dag.add_job("c", depends_on=["b"])
        dag.mark_completed("a")
        cancelled = dag.mark_failed("a", error="fail", hard_failure=True)
        self.assertIn("b", cancelled)
        self.assertIn("c", cancelled)
        self.assertEqual(dag.get_status("b"), "cancelled")
        self.assertEqual(dag.get_status("c"), "cancelled")

    def test_soft_failure_no_cancel(self) -> None:
        dag = DAGExecutionEngine()
        dag.add_job("a")
        dag.add_job("b", depends_on=["a"])
        cancelled = dag.mark_failed("a", error="soft")
        self.assertEqual(len(cancelled), 0)
        self.assertEqual(dag.get_status("b"), "pending")

    def test_compute_schedule(self) -> None:
        dag = DAGExecutionEngine()
        dag.add_job("a")
        dag.add_job("b")
        dag.add_job("c", depends_on=["a", "b"])
        schedule = dag.compute_schedule()
        self.assertIsNotNone(schedule)
        self.assertEqual(len(schedule), 2)
        self.assertIn("a", schedule[0])
        self.assertIn("b", schedule[0])
        self.assertIn("c", schedule[1])

    def test_set_critical_path(self) -> None:
        dag = DAGExecutionEngine()
        dag.set_critical_path(["a", "b", "c"])
        self.assertEqual(dag.get_critical_path(), ["a", "b", "c"])

    def test_get_stats(self) -> None:
        dag = DAGExecutionEngine()
        dag.add_job("a")
        dag.add_job("b", depends_on=["a"])
        dag.mark_completed("a")
        stats = dag.get_stats()
        self.assertEqual(stats["total_jobs"], 2)
        self.assertEqual(stats["completed"], 1)


class TestObservabilityExportPack(unittest.TestCase):
    """Feature 5 (PR81): Observability export pack."""

    def test_record_metric(self) -> None:
        oep = ObservabilityExportPack()
        oep.record_metric("queue_depth", 5.0)
        self.assertEqual(oep._metrics["queue_depth"], 5.0)

    def test_record_event(self) -> None:
        oep = ObservabilityExportPack()
        oep.record_event("sla_breach", {"goal_id": "g1"})
        events = oep.get_event_stream()
        self.assertEqual(len(events), 1)

    def test_take_snapshot(self) -> None:
        oep = ObservabilityExportPack()
        oep.record_metric("depth", 5.0)
        snap = oep.take_snapshot()
        self.assertIn("snapshot_id", snap)
        self.assertEqual(snap["metrics"]["depth"], 5.0)

    def test_to_json(self) -> None:
        oep = ObservabilityExportPack()
        oep.record_metric("depth", 5.0)
        json_str = oep.to_json()
        self.assertIn('"depth": 5.0', json_str)

    def test_to_prometheus(self) -> None:
        oep = ObservabilityExportPack()
        oep.record_metric("queue_depth", 5.0)
        prom = oep.to_prometheus()
        self.assertIn("scheduler_metrics", prom)
        self.assertIn("queue_depth", prom)

    def test_get_json_snapshot(self) -> None:
        oep = ObservabilityExportPack()
        oep.record_metric("depth", 5.0)
        snap = oep.get_json_snapshot()
        self.assertTrue(snap["json_available"])
        self.assertTrue(snap["prometheus_available"])
        self.assertIn("metrics", snap)

    def test_get_event_stream(self) -> None:
        oep = ObservabilityExportPack()
        oep.record_event("type1", {})
        oep.record_event("type2", {})
        events1 = oep.get_event_stream("type1")
        events2 = oep.get_event_stream("type2")
        self.assertEqual(len(events1), 1)
        self.assertEqual(len(events2), 1)

    def test_get_stats(self) -> None:
        oep = ObservabilityExportPack()
        oep.record_metric("m1", 1.0)
        oep.record_event("e1", {})
        stats = oep.get_stats()
        self.assertEqual(stats["metrics_count"], 1)
        # record_metric creates both a metric and an event, so total_events = 2
        self.assertEqual(stats["total_events"], 2)
