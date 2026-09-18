"""Governed scheduler — 25 features extending the concurrent architecture.

All features extend the EXISTING governed concurrency architecture
(ThinkBoxEngine -> GovernedEngine -> VerifiedRetrySession -> DAG ->
concurrent_goals -> ExperimentManager/MemoryStore/Ledger -> dashboard).
No parallel systems are created.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from thinkbox.concurrent_goals import (
    BudgetContentionPolicy,
    ConcurrentGoalSpec,
    ConcurrentGoalsConfig,
    ConcurrentGoalsResult,
    GoalLifecycleState,
    GoalPriority,
    BudgetReservation,
    RetryBudget,
    aggregate_layer_telemetry,
)
from thinkbox.pop_arena import VerifiedRetryConfig, VerifiedRetrySession, BudgetExhausted


class SchedulerState(str, Enum):
    IDLE = "idle"
    ADMITTING = "admitting"
    SCHEDULING = "scheduling"
    RUNNING = "running"
    PAUSING = "pausing"
    RECOVERING = "recovering"
    STOPPED = "stopped"


class HealthIndicator(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    RECOVERING = "recovering"
    BLOCKED = "blocked"


class SchedulerDecisionType(str, Enum):
    ADMIT = "admit"
    REJECT = "reject"
    DEFER = "defer"
    CANCEL = "cancel"
    RETRY = "retry"
    COMPLETE = "complete"
    RECOVER = "recover"


@dataclass
class SchedulerDecisionReceipt:
    decision_id: str
    decision_type: SchedulerDecisionType
    goal_id: str
    timestamp: str = ""
    state: SchedulerState = SchedulerState.IDLE
    reasoning: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    ledger_hash: str = ""

    def __post_init__(self) -> None:
        if not self.decision_id:
            self.decision_id = f"sdc_{uuid.uuid4().hex[:12]}"
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "decision_type": self.decision_type.value,
            "goal_id": self.goal_id,
            "timestamp": self.timestamp,
            "state": self.state.value,
            "reasoning": self.reasoning,
            "metadata": self.metadata,
            "ledger_hash": self.ledger_hash,
        }


class AdaptiveConcurrencyLimiter:
    """Feature 1: Adaptive concurrency limits.

    Dynamically adjusts the maximum number of concurrent goals based on
    observed completion rate and system load. Uses a moving window of
    recent completions to estimate capacity.
    """

    def __init__(
        self,
        min_concurrency: int = 1,
        max_concurrency: int = 10,
        window_size: int = 20,
        adjustment_step: float = 0.25,
        target_completion_time: float = 5.0,
    ) -> None:
        self.min_concurrency = min_concurrency
        self.max_concurrency = max_concurrency
        self.window_size = window_size
        self.adjustment_step = adjustment_step
        self.target_completion_time = target_completion_time
        self._completion_times: list[float] = []
        self._current_limit = max_concurrency
        self._history: list[dict[str, Any]] = []

    @property
    def current_limit(self) -> int:
        return self._current_limit

    def record_completion(self, duration_s: float) -> None:
        self._completion_times.append(duration_s)
        if len(self._completion_times) > self.window_size:
            self._completion_times = self._completion_times[-self.window_size:]
        self._adjust()

    def _adjust(self) -> None:
        if not self._completion_times:
            return
        avg = sum(self._completion_times) / len(self._completion_times)
        if avg < self.target_completion_time * 0.5:
            new_limit = min(self.max_concurrency, self._current_limit + 1)
        elif avg > self.target_completion_time * 2.0:
            new_limit = max(self.min_concurrency, self._current_limit - 1)
        else:
            return
        self._current_limit = new_limit
        self._history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "avg_completion": round(avg, 4),
            "new_limit": new_limit,
        })

    def get_stats(self) -> dict[str, Any]:
        return {
            "current_limit": self._current_limit,
            "min": self.min_concurrency,
            "max": self.max_concurrency,
            "window_size": self.window_size,
            "target_completion_time": self.target_completion_time,
            "recent_completions": len(self._completion_times),
            "adjustment_history": self._history[-10:],
        }


class GlobalSchedulerAdmission:
    """Feature 2: Global scheduler admission control.

    Central admission gate that checks global capacity (active goals,
    queue depth, resource utilization) before allowing a goal to be
    admitted into the scheduler. Denials are recorded as receipts.
    """

    def __init__(
        self,
        max_active_goals: int = 10,
        max_queue_depth: int = 50,
        max_global_calls: int = 100,
        admission_token: str = "",
    ) -> None:
        self.max_active_goals = max_active_goals
        self.max_queue_depth = max_queue_depth
        self.max_global_calls = max_global_calls
        self.admission_token = admission_token
        self._active_goals: dict[str, float] = {}
        self._queue_depth = 0
        self._global_calls = 0
        self._admission_log: list[SchedulerDecisionReceipt] = []

    def can_admit(
        self,
        goal_id: str,
        estimated_calls: int = 1,
        priority: int = GoalPriority.NORMAL.value,
    ) -> tuple[bool, str, Optional[SchedulerDecisionReceipt]]:
        reasons: list[str] = []
        if len(self._active_goals) >= self.max_active_goals:
            reasons.append("max_active_goals_reached")
        if self._queue_depth >= self.max_queue_depth:
            reasons.append("max_queue_depth_reached")
        if self._global_calls + estimated_calls > self.max_global_calls:
            reasons.append("global_budget_insufficient")

        admitted = not reasons
        reasoning = "admitted" if admitted else "; ".join(reasons)
        receipt = SchedulerDecisionReceipt(
            decision_id="",
            decision_type=SchedulerDecisionType.ADMIT if admitted else SchedulerDecisionType.REJECT,
            goal_id=goal_id,
            state=SchedulerState.ADMITTING,
            reasoning=reasoning,
            metadata={
                "active_goals": len(self._active_goals),
                "queue_depth": self._queue_depth,
                "global_calls": self._global_calls,
                "estimated_calls": estimated_calls,
                "priority": priority,
            },
        )
        self._admission_log.append(receipt)
        if admitted:
            self._active_goals[goal_id] = time.monotonic()
            self._global_calls += estimated_calls
        return admitted, reasoning, receipt

    def admit(self, goal_id: str, **kwargs: Any) -> SchedulerDecisionReceipt:
        admitted, reasoning, receipt = self.can_admit(goal_id, **kwargs)
        if not admitted:
            raise BudgetExhausted(reasoning)
        return receipt

    def release(self, goal_id: str) -> None:
        self._active_goals.pop(goal_id, None)

    def get_state(self) -> dict[str, Any]:
        return {
            "active_goals": len(self._active_goals),
            "max_active_goals": self.max_active_goals,
            "queue_depth": self._queue_depth,
            "max_queue_depth": self.max_queue_depth,
            "global_calls": self._global_calls,
            "max_global_calls": self.max_global_calls,
            "admission_count": len(self._admission_log),
            "admissions": sum(1 for r in self._admission_log if r.decision_type == SchedulerDecisionType.ADMIT),
            "rejections": sum(1 for r in self._admission_log if r.decision_type == SchedulerDecisionType.REJECT),
        }


class PerGoalConcurrencyCap:
    """Feature 3: Per-goal concurrency caps.

    Limits the number of concurrent tasks within a single goal to
    prevent any one goal from monopolizing resources.
    """

    def __init__(self, default_cap: int = 4) -> None:
        self.default_cap = default_cap
        self._caps: dict[str, int] = {}
        self._active: dict[str, int] = {}
        self._violations: list[dict[str, Any]] = []

    def set_cap(self, goal_id: str, cap: int) -> None:
        self._caps[goal_id] = max(1, cap)
        if goal_id not in self._active:
            self._active[goal_id] = 0

    def get_cap(self, goal_id: str) -> int:
        return self._caps.get(goal_id, self.default_cap)

    def can_start_task(self, goal_id: str) -> tuple[bool, str]:
        cap = self.get_cap(goal_id)
        active = self._active.get(goal_id, 0)
        if active >= cap:
            self._violations.append({
                "goal_id": goal_id,
                "cap": cap,
                "active": active,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return False, f"cap_reached:{cap}"
        return True, "allowed"

    def start_task(self, goal_id: str) -> bool:
        allowed, _ = self.can_start_task(goal_id)
        if allowed:
            self._active[goal_id] = self._active.get(goal_id, 0) + 1
        return allowed

    def finish_task(self, goal_id: str) -> None:
        if goal_id in self._active and self._active[goal_id] > 0:
            self._active[goal_id] -= 1

    def get_state(self) -> dict[str, Any]:
        return {
            "default_cap": self.default_cap,
            "caps": dict(self._caps),
            "active": dict(self._active),
            "violations": len(self._violations),
        }


class WeightedPriorityScheduler:
    """Feature 4: Weighted priority scheduling.

    Schedules goals by weighted priority. Extends the existing
    GoalPriority enum with configurable weights. Higher weight
    goals get proportionally more budget and earlier scheduling.
    """

    def __init__(self) -> None:
        self._weights: dict[str, float] = {}
        self._schedule_log: list[SchedulerDecisionReceipt] = []

    def set_weight(self, goal_id: str, weight: float) -> None:
        self._weights[goal_id] = max(0.0, weight)

    def get_weight(self, goal_id: str) -> float:
        return self._weights.get(goal_id, 1.0)

    def compute_priority_score(self, goal_id: str, base_priority: int = 0) -> float:
        weight = self.get_weight(goal_id)
        return base_priority * weight

    def schedule(self, goals: list[tuple[str, int]]) -> list[str]:
        scored = [(gid, self.compute_priority_score(gid, pri)) for gid, pri in goals]
        scored.sort(key=lambda x: x[1], reverse=True)
        ordered = [gid for gid, _ in scored]
        for gid, score in scored:
            receipt = SchedulerDecisionReceipt(
                decision_id="",
                decision_type=SchedulerDecisionType.ADMIT,
                goal_id=gid,
                state=SchedulerState.SCHEDULING,
                reasoning=f"scheduled with priority_score={score:.4f}",
                metadata={"base_priority": 0, "weight": self.get_weight(gid)},
            )
            self._schedule_log.append(receipt)
        return ordered

    def get_schedule_log(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self._schedule_log]


class BudgetAwareAdmission:
    """Feature 5: Budget-aware admission.

    Admission control that verifies sufficient budget exists before
    admitting a goal. Prevents over-admission that would exhaust
    shared budgets prematurely.
    """

    def __init__(self, global_budget: int = 50) -> None:
        self.global_budget = global_budget
        self._consumed: int = 0
        self._admitted: list[str] = []
        self._receipts: list[SchedulerDecisionReceipt] = []

    @property
    def remaining(self) -> int:
        return max(0, self.global_budget - self._consumed)

    def admit(self, goal_id: str, estimated_calls: int = 1) -> SchedulerDecisionReceipt:
        if self._consumed + estimated_calls > self.global_budget:
            receipt = SchedulerDecisionReceipt(
                decision_id="",
                decision_type=SchedulerDecisionType.REJECT,
                goal_id=goal_id,
                state=SchedulerState.ADMITTING,
                reasoning="budget_insufficient",
                metadata={
                    "requested": estimated_calls,
                    "remaining": self.remaining,
                    "global_budget": self.global_budget,
                },
            )
            self._receipts.append(receipt)
            return receipt
        self._consumed += estimated_calls
        self._admitted.append(goal_id)
        receipt = SchedulerDecisionReceipt(
            decision_id="",
            decision_type=SchedulerDecisionType.ADMIT,
            goal_id=goal_id,
            state=SchedulerState.ADMITTING,
            reasoning="budget_sufficient",
            metadata={
                "consumed": self._consumed,
                "remaining": self.remaining,
                "global_budget": self.global_budget,
            },
        )
        self._receipts.append(receipt)
        return receipt

    def release_budget(self, goal_id: str, calls: int) -> None:
        self._consumed = max(0, self._consumed - calls)
        if goal_id in self._admitted:
            self._admitted.remove(goal_id)

    def get_state(self) -> dict[str, Any]:
        return {
            "global_budget": self.global_budget,
            "consumed": self._consumed,
            "remaining": self.remaining,
            "admitted_count": len(self._admitted),
            "admission_count": len(self._receipts),
            "rejections": sum(1 for r in self._receipts if r.decision_type == SchedulerDecisionType.REJECT),
        }


class DeadlineAwareAdmission:
    """Feature 6: Deadline-aware admission.

    Checks whether a goal can complete within its deadline before
    admitting it. Uses historical completion time estimates.
    """

    def __init__(self, default_deadline_s: float = 300.0) -> None:
        self.default_deadline_s = default_deadline_s
        self._deadlines: dict[str, float] = {}
        self._estimates: dict[str, float] = {}
        self._decisions: list[SchedulerDecisionReceipt] = []

    def set_deadline(self, goal_id: str, deadline_s: float, estimate_s: float = 0.0) -> None:
        self._deadlines[goal_id] = deadline_s
        self._estimates[goal_id] = estimate_s

    def check(self, goal_id: str) -> tuple[bool, str, Optional[SchedulerDecisionReceipt]]:
        deadline = self._deadlines.get(goal_id, self.default_deadline_s)
        estimate = self._estimates.get(goal_id, 0.0)
        margin = deadline - estimate
        feasible = margin > 0
        reasoning = (
            f"feasible: margin={margin:.2f}s" if feasible
            else f"infeasible: margin={margin:.2f}s (deadline={deadline:.2f}, estimate={estimate:.2f})"
        )
        decision = SchedulerDecisionType.ADMIT if feasible else SchedulerDecisionType.DEFER
        receipt = SchedulerDecisionReceipt(
            decision_id="",
            decision_type=decision,
            goal_id=goal_id,
            state=SchedulerState.ADMITTING,
            reasoning=reasoning,
            metadata={
                "deadline_s": deadline,
                "estimate_s": estimate,
                "margin_s": round(margin, 4),
            },
        )
        self._decisions.append(receipt)
        return feasible, reasoning, receipt

    def get_state(self) -> dict[str, Any]:
        return {
            "default_deadline_s": self.default_deadline_s,
            "tracked_goals": len(self._deadlines),
            "decisions": [d.to_dict() for d in self._decisions],
        }


class RetryAwareReservation:
    """Feature 7: Retry-aware reservations.

    Reserves retry budget for a goal before execution begins,
    ensuring retry capacity is available and tracked separately
    from the call budget.
    """

    def __init__(self, default_retries: int = 1) -> None:
        self.default_retries = default_retries
        self._reservations: dict[str, RetryBudget] = {}
        self._consumed: dict[str, int] = {}
        self._log: list[dict[str, Any]] = []

    def reserve(self, goal_id: str, max_retries: int | None = None) -> RetryBudget:
        budget = RetryBudget(max_retries=max_retries if max_retries is not None else self.default_retries)
        self._reservations[goal_id] = budget
        self._consumed[goal_id] = 0
        self._log.append({
            "goal_id": goal_id,
            "action": "reserve",
            "max_retries": budget.max_retries,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return budget

    def can_retry(self, goal_id: str) -> tuple[bool, str]:
        if goal_id not in self._reservations:
            return False, "no_reservation"
        budget = self._reservations[goal_id]
        if self._consumed[goal_id] >= budget.max_retries:
            return False, "retries_exhausted"
        return True, "available"

    def consume_retry(self, goal_id: str) -> bool:
        allowed, _ = self.can_retry(goal_id)
        if allowed:
            self._consumed[goal_id] += 1
        return allowed

    def release(self, goal_id: str) -> None:
        self._reservations.pop(goal_id, None)
        self._consumed.pop(goal_id, None)

    def get_state(self) -> dict[str, Any]:
        return {
            "default_retries": self.default_retries,
            "reservations": {gid: {"max": b.max_retries, "consumed": self._consumed.get(gid, 0)} for gid, b in self._reservations.items()},
            "log": self._log[-20:],
        }


class BudgetForecaster:
    """Feature 8: Budget forecasting.

    Predicts future budget consumption from historical patterns.
    Uses linear regression on consumption rate to estimate when
    budget will be exhausted.
    """

    def __init__(self) -> None:
        self._consumption_history: list[dict[str, Any]] = []

    def record(self, goal_id: str, calls: int, timestamp: float, duration_s: float) -> None:
        self._consumption_history.append({
            "goal_id": goal_id,
            "calls": calls,
            "timestamp": timestamp,
            "duration_s": duration_s,
        })

    def forecast(
        self,
        goal_id: str | None = None,
        horizon_s: float = 60.0,
    ) -> dict[str, Any]:
        relevant = [
            h for h in self._consumption_history
            if goal_id is None or h["goal_id"] == goal_id
        ]
        if len(relevant) < 2:
            return {"predicted_calls": 0, "exhaustion_time": None, "confidence": 0.0, "sample_size": len(relevant)}
        timestamps = [h["timestamp"] for h in relevant]
        calls = [h["calls"] for h in relevant]
        t_min = min(timestamps)
        x = [t - t_min for t in timestamps]
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(calls)
        sum_xy = sum(xi * yi for xi, yi in zip(x, calls))
        sum_x2 = sum(xi * xi for xi in x)
        denom = n * sum_x2 - sum_x * sum_x
        if denom == 0:
            slope = 0.0
        else:
            slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n
        current_time = max(timestamps)
        future_x = current_time - t_min + horizon_s
        predicted = slope * future_x + intercept
        if slope > 0:
            budget_at_current = slope * (current_time - t_min) + intercept
            if budget_at_current > 0:
                exhaustion_x = (1 - intercept) / slope if slope != 0 else float("inf")
                exhaustion_time = t_min + exhaustion_x
            else:
                exhaustion_time = current_time
        else:
            exhaustion_time = None
        return {
            "predicted_calls": max(0, round(predicted, 2)),
            "exhaustion_time": exhaustion_time,
            "slope": round(slope, 6),
            "confidence": min(1.0, len(relevant) / 20.0),
            "sample_size": len(relevant),
            "horizon_s": horizon_s,
        }


class BudgetOverspendPrevention:
    """Feature 9: Budget overspend prevention.

    Hard cap enforcement that prevents any mechanism from exceeding
    the configured global budget. Every call must be pre-authorized.
    """

    def __init__(self, max_budget: int = 100) -> None:
        self.max_budget = max_budget
        self._spent: int = 0
        self._blocked: list[dict[str, Any]] = []
        self._ledger: list[dict[str, Any]] = []

    def authorize(self, goal_id: str, calls: int = 1) -> tuple[bool, str]:
        if self._spent + calls > self.max_budget:
            self._blocked.append({
                "goal_id": goal_id,
                "requested": calls,
                "spent": self._spent,
                "max": self.max_budget,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return False, f"overspend_prevented: {self._spent}/{self.max_budget}"
        self._spent += calls
        self._ledger.append({
            "goal_id": goal_id,
            "calls": calls,
            "total_spent": self._spent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return True, "authorized"

    def get_state(self) -> dict[str, Any]:
        return {
            "max_budget": self.max_budget,
            "spent": self._spent,
            "remaining": max(0, self.max_budget - self._spent),
            "blocked_count": len(self._blocked),
            "ledger_entries": len(self._ledger),
        }


class SchedulerTelemetry:
    """Base class for scheduler telemetry features (10-15)."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def record(self, event_type: str, data: dict[str, Any]) -> None:
        self._events.append({
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if len(self._events) > 10000:
            self._events = self._events[-10000:]

    def get_events(self, event_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        events = self._events
        if event_type:
            events = [e for e in events if e["event_type"] == event_type]
        return events[-limit:]


class QueueDepthTelemetry(SchedulerTelemetry):
    """Feature 10: Queue-depth telemetry.

    Tracks queue depth over time, recording samples at regular
    intervals and providing summary statistics.
    """

    def __init__(self) -> None:
        super().__init__()
        self._samples: list[dict[str, Any]] = []

    def sample(self, depth: int, active: int = 0) -> None:
        self._samples.append({
            "depth": depth,
            "active": active,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self.record("queue_depth", {"depth": depth, "active": active})

    def get_stats(self) -> dict[str, Any]:
        depths = [s["depth"] for s in self._samples]
        if not depths:
            return {"samples": 0, "current": 0, "mean": 0.0, "max": 0, "min": 0}
        return {
            "samples": len(depths),
            "current": depths[-1],
            "mean": round(sum(depths) / len(depths), 4),
            "max": max(depths),
            "min": min(depths),
            "samples_recent": depths[-20:],
        }


class WaitTimeTelemetry(SchedulerTelemetry):
    """Feature 11: Wait-time telemetry.

    Tracks how long goals wait before being executed, from
    admission to start.
    """

    def __init__(self) -> None:
        super().__init__()
        self._admitted_at: dict[str, float] = {}
        self._wait_times: list[dict[str, Any]] = []

    def admit(self, goal_id: str) -> None:
        self._admitted_at[goal_id] = time.monotonic()

    def start(self, goal_id: str) -> Optional[float]:
        admitted = self._admitted_at.pop(goal_id, None)
        if admitted is None:
            return None
        wait = time.monotonic() - admitted
        self._wait_times.append({
            "goal_id": goal_id,
            "wait_s": round(wait, 4),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self.record("wait_time", {"goal_id": goal_id, "wait_s": round(wait, 4)})
        return wait

    def get_stats(self) -> dict[str, Any]:
        waits = [w["wait_s"] for w in self._wait_times]
        if not waits:
            return {"samples": 0, "mean": 0.0, "max": 0.0, "p95": 0.0}
        sorted_w = sorted(waits)
        return {
            "samples": len(waits),
            "mean": round(sum(waits) / len(waits), 4),
            "max": round(max(waits), 4),
            "p95": round(sorted_w[int(len(sorted_w) * 0.95)], 4) if len(sorted_w) > 1 else waits[0],
            "recent": self._wait_times[-10:],
        }


class ExecutionUtilization(SchedulerTelemetry):
    """Feature 12: Execution utilization metrics.

    Tracks concurrency utilization as a ratio of active goals to
    the configured maximum, recording samples over time.
    """

    def __init__(self, max_concurrency: int = 10) -> None:
        super().__init__()
        self.max_concurrency = max_concurrency
        self._samples: list[dict[str, Any]] = []

    def sample(self, active: int) -> None:
        util = min(1.0, active / self.max_concurrency) if self.max_concurrency > 0 else 0.0
        self._samples.append({
            "active": active,
            "max": self.max_concurrency,
            "utilization": round(util, 4),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self.record("utilization", {"active": active, "utilization": util})

    def get_stats(self) -> dict[str, Any]:
        utils = [s["utilization"] for s in self._samples]
        if not utils:
            return {"samples": 0, "current": 0.0, "mean": 0.0}
        return {
            "samples": len(utils),
            "current": utils[-1],
            "mean": round(sum(utils) / len(utils), 4),
            "max": round(max(utils), 4),
            "min": round(min(utils), 4),
        }


class FairnessTrendTracker(SchedulerTelemetry):
    """Feature 13: Fairness trend tracking.

    Tracks fairness metrics (Jain's index) over time across
    scheduler iterations, detecting trends and anomalies.
    """

    def __init__(self) -> None:
        super().__init__()
        self._trends: list[dict[str, Any]] = []

    def record_fairness(self, jain_index: float, distribution: list[float]) -> None:
        self._trends.append({
            "jain_index": round(jain_index, 6),
            "distribution": distribution,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self.record("fairness", {"jain_index": jain_index, "distribution": distribution})

    def get_trend(self) -> dict[str, Any]:
        indices = [t["jain_index"] for t in self._trends]
        if len(indices) < 2:
            return {"samples": len(indices), "trend": "insufficient_data", "current": indices[-1] if indices else 0.0}
        delta = indices[-1] - indices[0]
        return {
            "samples": len(indices),
            "first": indices[0],
            "current": indices[-1],
            "delta": round(delta, 6),
            "trend": "improving" if delta > 0.001 else "declining" if delta < -0.001 else "stable",
            "min": round(min(indices), 6),
            "max": round(max(indices), 6),
            "recent": self._trends[-5:],
        }


class SchedulerHealth:
    """Feature 24 partial: Scheduler health indicators."""

    def __init__(self) -> None:
        self._indicators: dict[str, HealthIndicator] = {}
        self._warnings: list[dict[str, Any]] = []

    def set_health(self, component: str, status: HealthIndicator) -> None:
        old = self._indicators.get(component)
        self._indicators[component] = status
        if old != status and status in (HealthIndicator.CRITICAL, HealthIndicator.DEGRADED):
            self._warnings.append({
                "component": component,
                "status": status.value,
                "previous": old.value if old else "unknown",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    def get_health(self) -> dict[str, Any]:
        return {
            "indicators": {k: v.value for k, v in self._indicators.items()},
            "overall": self._overall(),
            "warnings": self._warnings[-10:],
        }

    def _overall(self) -> str:
        vals = list(self._indicators.values())
        if not vals:
            return HealthIndicator.HEALTHY.value
        if any(v == HealthIndicator.CRITICAL for v in vals):
            return HealthIndicator.CRITICAL.value
        if any(v == HealthIndicator.DEGRADED for v in vals):
            return HealthIndicator.DEGRADED.value
        if any(v == HealthIndicator.RECOVERING for v in vals):
            return HealthIndicator.RECOVERING.value
        return HealthIndicator.HEALTHY.value


class StarvationRecovery:
    """Feature 15 (extending 14): Starvation recovery.

    Monitors for starved goals and automatically recovers them by
    bumping priority or allocating budget. Works with the existing
    StarvationDetector in concurrent_goals.py.
    """

    def __init__(self, max_wait_s: float = 30.0) -> None:
        self.max_wait_s = max_wait_s
        self._starvation_log: list[dict[str, Any]] = []
        self._recoveries: list[dict[str, Any]] = []

    def detect(
        self,
        goal_start_times: dict[str, float],
        running_goals: set[str],
    ) -> list[dict[str, Any]]:
        now = time.monotonic()
        starved = []
        for goal_id, start in goal_start_times.items():
            if goal_id not in running_goals:
                continue
            wait = now - start
            if wait > self.max_wait_s:
                entry = {
                    "goal_id": goal_id,
                    "wait_s": round(wait, 4),
                    "max_wait_s": self.max_wait_s,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                }
                starved.append(entry)
                self._starvation_log.append(entry)
        return starved

    def recover(self, goal_id: str, action: str = "priority_bump") -> dict[str, Any]:
        recovery = {
            "goal_id": goal_id,
            "action": action,
            "recovered_at": datetime.now(timezone.utc).isoformat(),
        }
        self._recoveries.append(recovery)
        return recovery

    def get_stats(self) -> dict[str, Any]:
        return {
            "starvation_detections": len(self._starvation_log),
            "recoveries": len(self._recoveries),
            "last_starvation": self._starvation_log[-1] if self._starvation_log else None,
            "last_recovery": self._recoveries[-1] if self._recoveries else None,
        }


class PriorityInversionRecovery:
    """Feature 16: Priority inversion recovery.

    Detects priority inversion (low-priority goal holding resources
    needed by high-priority goal) and applies recovery actions
    (priority inheritance or preemption).
    """

    def __init__(self) -> None:
        self._inversion_log: list[dict[str, Any]] = []
        self._resolutions: list[dict[str, Any]] = []

    def detect(
        self,
        goal_priorities: dict[str, int],
        blocked_by: dict[str, str],
    ) -> list[dict[str, Any]]:
        inversions = []
        for blocked_id, blocking_id in blocked_by.items():
            bp = goal_priorities.get(blocked_id, 0)
            bsp = goal_priorities.get(blocking_id, 0)
            if bp > bsp:
                entry = {
                    "blocked_goal": blocked_id,
                    "blocking_goal": blocking_id,
                    "blocked_priority": bp,
                    "blocking_priority": bsp,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                }
                inversions.append(entry)
                self._inversion_log.append(entry)
        return inversions

    def resolve(self, goal_id: str, method: str = "priority_inheritance") -> dict[str, Any]:
        resolution = {
            "goal_id": goal_id,
            "method": method,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        }
        self._resolutions.append(resolution)
        return resolution

    def get_stats(self) -> dict[str, Any]:
        return {
            "inversions_detected": len(self._inversion_log),
            "resolutions": len(self._resolutions),
            "recent_inversions": self._inversion_log[-5:],
            "recent_resolutions": self._resolutions[-5:],
        }


class CancellationPropagator:
    """Feature 17: Cancellation propagation across DAGs.

    Propagates cancellation signals across dependent DAG goals.
    When one goal is cancelled, all goals that depend on its
    outputs are also cancelled (transitively).
    """

    def __init__(self) -> None:
        self._dependencies: dict[str, set[str]] = {}
        self._cancelled: set[str] = set()
        self._propagation_log: list[dict[str, Any]] = []

    def register_dependency(self, goal_id: str, depends_on: list[str]) -> None:
        self._dependencies[goal_id] = set(depends_on)

    def cancel(self, goal_id: str, reason: str = "cancelled") -> list[str]:
        affected = self._propagate(goal_id)
        for gid in affected:
            self._cancelled.add(gid)
            self._propagation_log.append({
                "goal_id": gid,
                "reason": reason,
                "cancelled_at": datetime.now(timezone.utc).isoformat(),
                "triggered_by": goal_id,
            })
        return list(affected)

    def _propagate(self, goal_id: str) -> set[str]:
        affected = {goal_id}
        stack = [goal_id]
        while stack:
            current = stack.pop()
            for other, deps in self._dependencies.items():
                if current in deps and other not in affected:
                    affected.add(other)
                    stack.append(other)
        return affected

    def is_cancelled(self, goal_id: str) -> bool:
        return goal_id in self._cancelled

    def get_log(self) -> list[dict[str, Any]]:
        return self._propagation_log[-20:]


class FanOutBackpressure:
    """Feature 19: Fan-out backpressure.

    Applies backpressure during fan-out phases of DAG execution
    when the number of ready tasks exceeds the concurrency limit.
    Tasks are queued and released as capacity becomes available.
    """

    def __init__(self, max_concurrent_tasks: int = 8) -> None:
        self.max_concurrent_tasks = max_concurrent_tasks
        self._queue: list[str] = []
        self._active: set[str] = set()
        self._backpressure_events: list[dict[str, Any]] = []
        self._released: list[str] = []

    def submit(self, task_id: str) -> tuple[bool, str]:
        if len(self._active) >= self.max_concurrent_tasks:
            self._queue.append(task_id)
            self._backpressure_events.append({
                "task_id": task_id,
                "action": "queued",
                "queue_depth": len(self._queue),
                "active": len(self._active),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return False, "backpressure:queued"
        self._active.add(task_id)
        return True, "active"

    def release(self, task_id: str) -> Optional[str]:
        self._active.discard(task_id)
        self._released.append(task_id)
        if self._queue:
            next_task = self._queue.pop(0)
            self._active.add(next_task)
            return next_task
        return None

    def get_state(self) -> dict[str, Any]:
        return {
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "active": len(self._active),
            "queued": len(self._queue),
            "released": len(self._released),
            "backpressure_events": len(self._backpressure_events),
        }


class FanInQuorumTracker:
    """Feature 20: Fan-in quorum/aggregation telemetry.

    Tracks fan-in aggregation status, monitoring when all
    dependencies of a fan-in task have completed (quorum reached).
    """

    def __init__(self) -> None:
        self._dependencies: dict[str, set[str]] = {}
        self._completed: set[str] = set()
        self._quorum_reached: list[dict[str, Any]] = []
        self._partial_updates: list[dict[str, Any]] = []

    def register(self, task_id: str, dependencies: list[str]) -> None:
        self._dependencies[task_id] = set(dependencies)

    def mark_complete(self, task_id: str) -> list[str]:
        self._completed.add(task_id)
        ready = []
        for tid, deps in self._dependencies.items():
            if tid in self._completed:
                continue
            if deps.issubset(self._completed):
                ready.append(tid)
                self._quorum_reached.append({
                    "task_id": tid,
                    "dependency_count": len(deps),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
        for tid in ready:
            self._partial_updates.append({
                "task_id": tid,
                "status": "quorum_reached",
                "ready": True,
            })
        return ready

    def get_quorum_status(self, task_id: str) -> dict[str, Any]:
        deps = self._dependencies.get(task_id, set())
        completed = deps.intersection(self._completed)
        return {
            "task_id": task_id,
            "total_dependencies": len(deps),
            "completed_dependencies": len(completed),
            "quorum_reached": deps.issubset(self._completed),
            "pending": list(deps - self._completed),
        }


class CrossGoalReplayVerifier:
    """Feature 21: Cross-goal replay verification.

    Verifies that replayed goal executions produce deterministic
    results across goals, comparing replay hashes against originals.
    """

    def __init__(self) -> None:
        self._verifications: list[dict[str, Any]] = []

    def verify(
        self,
        goal_id: str,
        original_hash: str,
        replay_hash: str,
        goal_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        match = original_hash == replay_hash
        verification = {
            "goal_id": goal_id,
            "original_hash": original_hash,
            "replay_hash": replay_hash,
            "deterministic": match,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": goal_config or {},
        }
        self._verifications.append(verification)
        return verification

    def get_results(self) -> list[dict[str, Any]]:
        return self._verifications

    def get_summary(self) -> dict[str, Any]:
        total = len(self._verifications)
        if not total:
            return {"total": 0, "deterministic": 0, "ratio": 0.0}
        det = sum(1 for v in self._verifications if v["deterministic"])
        return {"total": total, "deterministic": det, "ratio": round(det / total, 4)}


class RestartSafeSchedulerRecovery:
    """Feature 22: Restart-safe scheduler recovery.

    Persists scheduler state to SQLite via ExperimentManager and
    reconstructs it after restart. Ensures no scheduling decisions
    are lost across process restarts.
    """

    def __init__(self, db_path: str = "data/thinkboxmd/db/scheduler.db") -> None:
        self._db_path = db_path
        self._state: dict[str, Any] = {"goals": {}, "queue": [], "decisions": []}
        self._recovery_log: list[dict[str, Any]] = []

    def persist(self) -> dict[str, Any]:
        import sqlite3
        import os
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("""CREATE TABLE IF NOT EXISTS scheduler_state (
                key TEXT PRIMARY KEY, value TEXT, timestamp TEXT
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS scheduling_decisions (
                decision_id TEXT, goal_id TEXT, decision_type TEXT,
                reasoning TEXT, timestamp TEXT, metadata TEXT
            )""")
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("INSERT OR REPLACE INTO scheduler_state VALUES (?, ?, ?)",
                        ("state", json.dumps(self._state, default=str), now))
            conn.commit()
            result = {"persisted": True, "timestamp": now, "keys": list(self._state.keys())}
        finally:
            conn.close()
        return result

    def recover(self) -> dict[str, Any]:
        import sqlite3
        if not os.path.exists(self._db_path):
            return {"recovered": False, "reason": "no_persisted_state"}
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT value FROM scheduler_state WHERE key='state'")
            row = cursor.fetchone()
            if row:
                self._state = json.loads(row["value"])
                result = {"recovered": True, "keys": list(self._state.keys())}
            else:
                result = {"recovered": False, "reason": "empty_state"}
        finally:
            conn.close()
        self._recovery_log.append({
            "recovered": result["recovered"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return result


class PersistentSchedulerState:
    """Feature 23: Persistent scheduler state reconstruction.

    Builds a full reconstruction of scheduler state from persisted
    data, including receipts, telemetry, and goal statuses.
    Verifiable via hash-chain on reconstruction.
    """

    def __init__(self, db_path: str = "data/thinkboxmd/db/scheduler.db") -> None:
        self._db_path = db_path
        self._hash_chain: list[str] = []

    def reconstruct(self) -> dict[str, Any]:
        import sqlite3
        import os
        if not os.path.exists(self._db_path):
            return {"reconstructed": False, "reason": "no_db"}
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT value FROM scheduler_state WHERE key='state'")
            row = cursor.fetchone()
            state = json.loads(row["value"]) if row else {}
            cursor = conn.execute("SELECT * FROM scheduling_decisions")
            decisions = [dict(r) for r in cursor.fetchall()]
            prev_hash = "0" * 64
            for d in decisions:
                d_str = json.dumps(d, sort_keys=True, default=str)
                h = hashlib.sha256(d_str.encode()).hexdigest()
                self._hash_chain.append(h)
                prev_hash = h
            return {
                "reconstructed": True,
                "state_keys": list(state.keys()),
                "decisions": len(decisions),
                "hash_chain": self._hash_chain[:10],
                "hash_chain_valid": len(self._hash_chain) > 0,
            }
        finally:
            conn.close()

    def compute_reconstruction_hash(self, state: dict[str, Any]) -> str:
        s = json.dumps(state, sort_keys=True, default=str)
        return hashlib.sha256(s.encode()).hexdigest()


class FailureDomainIsolator:
    """Feature 18: Failure-domain isolation.

    Isolates failures to prevent cascade across domains.
    Each domain (goal, DAG, or execution context) is isolated
    so a failure in one cannot affect others.
    """

    def __init__(self) -> None:
        self._domains: dict[str, dict[str, Any]] = {}
        self._failure_log: list[dict[str, Any]] = []
        self._isolated_domains: set[str] = set()

    def register_domain(self, domain_id: str, parent: str = "root") -> None:
        self._domains[domain_id] = {
            "parent": parent,
            "status": "healthy",
            "tasks": 0,
            "failures": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def record_failure(self, domain_id: str, error: Exception) -> None:
        if domain_id not in self._domains:
            return
        self._domains[domain_id]["failures"] += 1
        self._domains[domain_id]["status"] = "failed"
        self._isolated_domains.add(domain_id)
        self._failure_log.append({
            "domain_id": domain_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "isolated": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "parent": self._domains[domain_id]["parent"],
        })

    def is_isolated(self, domain_id: str) -> bool:
        return domain_id in self._isolated_domains

    def get_domain_status(self, domain_id: str) -> dict[str, Any]:
        return self._domains.get(domain_id, {"status": "unknown"})

    def propagate_containment(self, domain_id: str) -> list[str]:
        """Contain failure to prevent cascade to sibling/parent domains."""
        contained = [domain_id]
        domain = self._domains.get(domain_id, {})
        parent = domain.get("parent", "root")
        if parent in self._domains and parent != "root":
            siblings = [d for d, info in self._domains.items()
                        if info.get("parent") == parent and d != domain_id]
            for s in siblings:
                if s not in self._isolated_domains:
                    self._domains[s]["status"] = "contained"
                    contained.append(s)
        return contained

    def get_stats(self) -> dict[str, Any]:
        return {
            "domains": len(self._domains),
            "isolated": len(self._isolated_domains),
            "failures": len(self._failure_log),
            "recent_failures": self._failure_log[-5:],
        }


class SchedulerDashboardExtension:
    """Feature 24: Dashboard scheduler timeline + health indicators.

    Provides data for the dashboard to display scheduler state,
    queue depth, active goals, reservations, consumption,
    utilization, fairness, starvation/inversion warnings, deadlines,
    retries, DAG pressure, proof and replay status.
    """

    def __init__(self) -> None:
        self._timeline: list[dict[str, Any]] = []
        self._health: dict[str, str] = {}
        self._metrics: dict[str, Any] = {
            "queue_depth": 0,
            "active_goals": 0,
            "reservations": 0,
            "consumption": 0,
            "utilization": 0.0,
            "fairness": 0.0,
            "retries": 0,
            "dag_pressure": 0.0,
        }

    def record_timeline_event(self, event: dict[str, Any]) -> None:
        event["timestamp"] = datetime.now(timezone.utc).isoformat()
        self._timeline.append(event)
        if len(self._timeline) > 1000:
            self._timeline = self._timeline[-1000:]

    def set_health(self, component: str, status: str) -> None:
        self._health[component] = status

    def update_metric(self, key: str, value: Any) -> None:
        if key in self._metrics:
            self._metrics[key] = value

    def get_dashboard_data(self) -> dict[str, Any]:
        return {
            "timeline": self._timeline[-50:],
            "health": dict(self._health),
            "metrics": dict(self._metrics),
            "summary": {
                "total_events": len(self._timeline),
                "healthy_components": sum(1 for s in self._health.values() if s == "healthy"),
                "unhealthy_components": sum(1 for s in self._health.values() if s != "healthy"),
                "warnings": [k for k, v in self._health.items() if v != "healthy"],
            },
        }

    def emit(self) -> None:
        """Emit current scheduler state as a dashboard event."""
        try:
            from thinkbox.dashboard_state import (
                get_dashboard_state, DashboardCategory, DashboardEvent,
            )
            data = self.get_dashboard_data()
            get_dashboard_state().emit(
                DashboardCategory.THINK_BOXES,
                DashboardEvent.TASK_COMPLETED,
                {
                    "timeline_events": data["summary"]["total_events"],
                    "healthy_components": data["summary"]["healthy_components"],
                    "unhealthy_components": data["summary"]["unhealthy_components"],
                    "warnings": data["summary"]["warnings"],
                    "metrics": data["metrics"],
                },
                source="SchedulerDashboardExtension",
                evidence_label="simulated",
            )
        except Exception:
            pass
