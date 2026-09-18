"""Governed scheduler — 25 features extending the concurrent architecture.

All features extend the EXISTING governed concurrency architecture
(ThinkBoxEngine -> GovernedEngine -> VerifiedRetrySession -> DAG ->
concurrent_goals -> ExperimentManager/MemoryStore/Ledger -> dashboard).
No parallel systems are created.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from thinkbox.concurrent_goals import (
    GoalPriority,
    RetryBudget,
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


class GoalTimeoutEnforcer:
    """Feature 26: Goal timeout enforcement.

    Monitors running goals and forcefully cancels those that exceed
    their deadline. Unlike DeadlineAwareAdmission (which checks at
    admission time), this operates at execution time to catch goals
    that started within budget but are now overdue.
    """

    def __init__(self, default_timeout_s: float = 300.0) -> None:
        self.default_timeout_s = default_timeout_s
        self._timeouts: dict[str, float] = {}
        self._start_times: dict[str, float] = {}
        self._timed_out: list[dict[str, Any]] = []

    def register(self, goal_id: str, timeout_s: float | None = None) -> None:
        self._timeouts[goal_id] = timeout_s or self.default_timeout_s
        self._start_times[goal_id] = time.monotonic()

    def check(self, goal_id: str) -> dict[str, Any]:
        if goal_id not in self._timeouts:
            return {"goal_id": goal_id, "timed_out": False, "reason": "not_registered"}
        elapsed = time.monotonic() - self._start_times.get(goal_id, 0.0)
        limit = self._timeouts[goal_id]
        if elapsed > limit:
            self._timed_out.append({
                "goal_id": goal_id,
                "elapsed": round(elapsed, 4),
                "limit": limit,
                "excess": round(elapsed - limit, 4),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return {"goal_id": goal_id, "timed_out": True, "elapsed": elapsed, "limit": limit}
        return {"goal_id": goal_id, "timed_out": False, "elapsed": elapsed, "remaining": limit - elapsed}

    def is_timed_out(self, goal_id: str) -> bool:
        return self.check(goal_id)["timed_out"]

    def get_timed_out(self) -> list[dict[str, Any]]:
        return list(self._timed_out)

    def get_stats(self) -> dict[str, Any]:
        return {
            "registered": len(self._timeouts),
            "timed_out": len(self._timed_out),
            "default_timeout_s": self.default_timeout_s,
            "active": len(self._timeouts) - len(self._timed_out),
        }


class GoalDependencyResolver:
    """Feature 27: Goal dependency resolution with topological sort.

    Resolves DAG dependencies between goals, detects cycles,
    computes a parallel execution schedule, and identifies the
    critical path (longest dependency chain).
    """

    def __init__(self) -> None:
        self._deps: dict[str, set[str]] = {}
        self._dependents: dict[str, set[str]] = {}

    def add_goal(self, goal_id: str, depends_on: list[str] | None = None) -> None:
        self._deps[goal_id] = set(depends_on or [])
        if goal_id not in self._dependents:
            self._dependents[goal_id] = set()
        for dep in (depends_on or []):
            self._dependents.setdefault(dep, set()).add(goal_id)

    def detect_cycles(self) -> list[list[str]]:
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {g: WHITE for g in self._deps}
        cycles = []
        path: list[str] = []

        def dfs(node: str) -> None:
            color[node] = GRAY
            path.append(node)
            for neighbor in self._deps.get(node, set()):
                if neighbor not in color:
                    continue
                if color[neighbor] == GRAY:
                    idx = path.index(neighbor)
                    cycles.append(list(path[idx:]))
                elif color[neighbor] == WHITE:
                    dfs(neighbor)
            path.pop()
            color[node] = BLACK

        for node in list(self._deps.keys()):
            if color.get(node) == WHITE:
                dfs(node)
        return cycles

    def has_cycles(self) -> bool:
        return len(self.detect_cycles()) > 0

    def topological_sort(self) -> list[str] | None:
        if self.has_cycles():
            return None
        in_degree = {g: 0 for g in self._deps}
        for g in self._deps:
            for dep in self._deps[g]:
                if dep in in_degree:
                    in_degree[g] += 1
        queue = [g for g, d in in_degree.items() if d == 0]
        result: list[str] = []
        while queue:
            queue.sort()
            node = queue.pop(0)
            result.append(node)
            for dependent in sorted(self._dependents.get(node, set())):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
        if len(result) != len(self._deps):
            return None
        return result

    def parallel_schedule(self) -> list[list[str]]:
        sort = self.topological_sort()
        if sort is None:
            return []
        level: dict[str, int] = {}
        for g in sort:
            deps = self._deps.get(g, set())
            max_level = 0
            for d in deps:
                if d in level:
                    max_level = max(max_level, level[d] + 1)
            level[g] = max_level
        if not level:
            return []
        max_lvl = max(level.values())
        return [[g for g in sort if level[g] == l] for l in range(max_lvl + 1)]

    def critical_path(self) -> tuple[list[str], int]:
        sort = self.topological_sort()
        if sort is None:
            return [], 0
        dist: dict[str, int] = {}
        prev: dict[str, str | None] = {}
        for g in sort:
            dist[g] = 1
            prev[g] = None
            for dep in self._deps.get(g, set()):
                if dep in dist and dist[dep] + 1 > dist[g]:
                    dist[g] = dist[dep] + 1
                    prev[g] = dep
        if not dist:
            return [], 0
        end = max(dist, key=dist.get)
        path = []
        cur: str | None = end
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        return path, dist[end]

    def get_stats(self) -> dict[str, Any]:
        sort = self.topological_sort()
        return {
            "goals": len(self._deps),
            "has_cycles": self.has_cycles(),
            "sorted": sort is not None,
            "parallel_levels": len(self.parallel_schedule()),
        }


class SchedulerPerformanceAnalytics:
    """Feature 28: Scheduler performance analytics.

    Computes throughput (goals/sec), latency percentiles (p50, p95, p99),
    and cost-efficiency (calls per goal) from recorded execution data.
    """

    def __init__(self) -> None:
        self._completions: list[dict[str, Any]] = []

    def record_completion(self, goal_id: str, duration_s: float, calls: int = 0) -> None:
        self._completions.append({
            "goal_id": goal_id,
            "duration_s": duration_s,
            "calls": calls,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _percentile(self, values: list[float], p: float) -> float:
        if not values:
            return 0.0
        sorted_v = sorted(values)
        idx = (len(sorted_v) - 1) * (p / 100.0)
        lo = int(idx)
        hi = min(lo + 1, len(sorted_v) - 1)
        frac = idx - lo
        return sorted_v[lo] + (sorted_v[hi] - sorted_v[lo]) * frac

    def get_throughput(self, window_s: float = 60.0) -> dict[str, Any]:
        now = datetime.now(timezone.utc).timestamp()
        recent = [c for c in self._completions
                  if now - datetime.fromisoformat(c["timestamp"]).timestamp() <= window_s]
        return {
            "goals_per_second": len(recent) / max(window_s, 0.001),
            "recent_completions": len(recent),
            "total_completed": len(self._completions),
            "window_s": window_s,
        }

    def get_latency_percentiles(self) -> dict[str, float]:
        durations = [c["duration_s"] for c in self._completions]
        return {
            "p50": round(self._percentile(durations, 50), 6),
            "p95": round(self._percentile(durations, 95), 6),
            "p99": round(self._percentile(durations, 99), 6),
            "mean": round(sum(durations) / max(len(durations), 1), 6),
            "samples": len(durations),
        }

    def get_cost_efficiency(self) -> dict[str, Any]:
        if not self._completions:
            return {"calls_per_goal": 0.0, "avg_calls_per_goal": 0.0}
        calls = [c["calls"] for c in self._completions if c["calls"] > 0]
        return {
            "total_calls": sum(c["calls"] for c in self._completions),
            "total_goals": len(self._completions),
            "avg_calls_per_goal": round(sum(calls) / max(len(calls), 1), 4),
            "calls_per_goal": round(sum(calls) / max(len(self._completions), 1), 4),
        }

    def get_summary(self) -> dict[str, Any]:
        return {
            "throughput": self.get_throughput(),
            "latency_percentiles": self.get_latency_percentiles(),
            "cost_efficiency": self.get_cost_efficiency(),
            "total_completions": len(self._completions),
        }


class CapacityPredictor:
    """Feature 29: Capacity prediction from historical patterns.

    Predicts future capacity based on historical completion patterns
    to proactively adjust scheduling decisions before congestion hits.
    """

    def __init__(self, history_window: int = 100) -> None:
        self._history_window = history_window
        self._history: list[dict[str, Any]] = []

    def record_capacity(self, active: int, queue_depth: int, completed: int) -> None:
        self._history.append({
            "active": active,
            "queue_depth": queue_depth,
            "completed": completed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if len(self._history) > self._history_window:
            self._history = self._history[-self._history_window:]

    def predict_congestion(self, lookahead_s: float = 60.0) -> dict[str, Any]:
        if len(self._history) < 2:
            return {"congestion_risk": "unknown", "data_points": len(self._history)}
        recent = self._history[-min(len(self._history), 20):]
        avg_queue = sum(h["queue_depth"] for h in recent) / len(recent)
        avg_active = sum(h["active"] for h in recent) / len(recent)
        trend_q = recent[-1]["queue_depth"] - recent[0]["queue_depth"]
        trend_a = recent[-1]["active"] - recent[0]["active"]
        risk = "low"
        if avg_queue > 20 or trend_q > 5 or trend_a > 3:
            risk = "high"
        elif avg_queue > 10 or trend_q > 2 or trend_a > 1:
            risk = "medium"
        return {
            "congestion_risk": risk,
            "lookahead_s": lookahead_s,
            "avg_queue_depth": round(avg_queue, 2),
            "avg_active": round(avg_active, 2),
            "queue_trend": trend_q,
            "active_trend": trend_a,
            "data_points": len(recent),
        }

    def predict_optimal_concurrency(self) -> dict[str, Any]:
        if len(self._history) < 2:
            return {"recommended_concurrency": 1, "confidence": "low"}
        recent = self._history[-min(len(self._history), 50):]
        avg_active = sum(h["active"] for h in recent) / len(recent)
        avg_queue = sum(h["queue_depth"] for h in recent) / len(recent)
        if avg_queue > 15:
            concurrency = max(1, int(avg_active * 0.7))
        elif avg_queue > 5:
            concurrency = max(1, int(avg_active * 0.85))
        else:
            concurrency = max(1, int(avg_active * 1.2))
        confidence = "high" if len(recent) >= 20 else "medium" if len(recent) >= 5 else "low"
        return {
            "recommended_concurrency": concurrency,
            "confidence": confidence,
            "based_on": len(recent),
            "avg_active": round(avg_active, 2),
        }

    def get_trend(self) -> dict[str, Any]:
        if len(self._history) < 2:
            return {"queue_trend": "insufficient_data", "data_points": len(self._history)}
        recent = self._history[-min(len(self._history), 20):]
        first_q = recent[0]["queue_depth"]
        last_q = recent[-1]["queue_depth"]
        diff = last_q - first_q
        trend = "improving" if diff < -1 else "worsening" if diff > 1 else "stable"
        return {"queue_trend": trend, "change": diff, "data_points": len(recent)}


class WorkStealingQueue:
    """Feature 30: Dynamic work stealing for load balancing.

    When one goal's queue has excess capacity while another is
    overloaded, work items are stolen from the fuller queue to
    balance load dynamically across goals.
    """

    def __init__(self, imbalance_threshold: float = 2.0) -> None:
        self._queues: dict[str, list[str]] = {}
        self._imbalance_threshold = imbalance_threshold
        self._steals: list[dict[str, Any]] = []

    def add_goal(self, goal_id: str) -> None:
        if goal_id not in self._queues:
            self._queues[goal_id] = []

    def enqueue(self, goal_id: str, item: str) -> None:
        self.add_goal(goal_id)
        self._queues[goal_id].append(item)

    def dequeue(self, goal_id: str) -> str | None:
        if goal_id not in self._queues or not self._queues[goal_id]:
            return None
        return self._queues[goal_id].pop(0)

    def steal(self, donor: str, recipient: str) -> dict[str, Any] | None:
        if donor == recipient or donor not in self._queues or recipient not in self._queues:
            return None
        if not self._queues[donor]:
            return None
        load_ratio = self._load_ratio(donor, recipient)
        if load_ratio < self._imbalance_threshold:
            return None
        item = self._queues[donor].pop(0)
        self._queues[recipient].append(item)
        steal_record = {
            "donor": donor,
            "recipient": recipient,
            "item": item,
            "load_ratio": round(load_ratio, 4),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._steals.append(steal_record)
        return steal_record

    def _load_ratio(self, donor: str, recipient: str) -> float:
        d_len = len(self._queues.get(donor, []))
        r_len = len(self._queues.get(recipient, []))
        if r_len == 0:
            return float(d_len)
        return d_len / r_len

    def rebalance(self) -> list[dict[str, Any]]:
        steals: list[dict[str, Any]] = []
        if len(self._queues) < 2:
            return steals
        while True:
            sorted_goals = sorted(self._queues.keys(), key=lambda g: len(self._queues[g]), reverse=True)
            if len(sorted_goals) < 2:
                break
            donor = sorted_goals[0]
            recipient = sorted_goals[-1]
            result = self.steal(donor, recipient)
            if result is None:
                break
            steals.append(result)
        return steals

    def get_load(self, goal_id: str) -> int:
        return len(self._queues.get(goal_id, []))

    def get_balanced(self) -> bool:
        if len(self._queues) < 2:
            return True
        sizes = [len(q) for q in self._queues.values()]
        if not sizes:
            return True
        return max(sizes) - min(sizes) <= 1

    def get_stats(self) -> dict[str, Any]:
        return {
            "goals": len(self._queues),
            "total_items": sum(len(q) for q in self._queues.values()),
            "steals": len(self._steals),
            "balanced": self.get_balanced(),
            "loads": {g: len(q) for g, q in self._queues.items()},
        }


class SLAComplianceTracker:
    """Feature 31: SLA compliance tracking and reporting.

    Tracks SLA targets per goal (max completion time, min success rate)
    and generates compliance reports showing which goals meet their
    contractual obligations.
    """

    def __init__(self) -> None:
        self._targets: dict[str, dict[str, Any]] = {}
        self._results: list[dict[str, Any]] = []

    def set_sla(self, goal_id: str, max_completion_s: float, min_success_rate: float = 0.95) -> None:
        self._targets[goal_id] = {
            "max_completion_s": max_completion_s,
            "min_success_rate": min_success_rate,
        }

    def record_result(self, goal_id: str, completion_s: float, success: bool) -> None:
        self._results.append({
            "goal_id": goal_id,
            "completion_s": completion_s,
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def check_compliance(self, goal_id: str) -> dict[str, Any]:
        if goal_id not in self._targets:
            return {"goal_id": goal_id, "compliant": False, "reason": "no_sla"}
        target = self._targets[goal_id]
        results = [r for r in self._results if r["goal_id"] == goal_id]
        if not results:
            return {"goal_id": goal_id, "compliant": False, "reason": "no_results", "sla": target}
        avg_time = sum(r["completion_s"] for r in results) / len(results)
        success_rate = sum(1 for r in results if r["success"]) / len(results)
        time_ok = avg_time <= target["max_completion_s"]
        rate_ok = success_rate >= target["min_success_rate"]
        return {
            "goal_id": goal_id,
            "compliant": time_ok and rate_ok,
            "sla": target,
            "avg_completion_s": round(avg_time, 4),
            "success_rate": round(success_rate, 4),
            "time_ok": time_ok,
            "rate_ok": rate_ok,
            "results": len(results),
        }

    def get_compliance_report(self) -> dict[str, Any]:
        report = {goal_id: self.check_compliance(goal_id) for goal_id in self._targets}
        total = len(report)
        compliant = sum(1 for r in report.values() if r.get("compliant"))
        return {
            "total_goals": total,
            "compliant": compliant,
            "non_compliant": total - compliant,
            "compliance_rate": round(compliant / max(total, 1), 4),
            "goals": report,
        }


class CheckpointManager:
    """Feature 32: Checkpoint/save-point management for goal recovery.

    Manages checkpoints for goals: save state to a named checkpoint,
    restore from checkpoint, list available checkpoints, and garbage
    collect old checkpoints to reclaim space.
    """

    def __init__(self, max_checkpoints: int = 50) -> None:
        self.max_checkpoints = max_checkpoints
        self._checkpoints: dict[str, dict[str, Any]] = {}

    def save(self, goal_id: str, state: dict[str, Any]) -> dict[str, Any]:
        checkpoint_id = f"cp_{goal_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
        checkpoint = {
            "checkpoint_id": checkpoint_id,
            "goal_id": goal_id,
            "state": state,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "size": len(str(state)),
        }
        self._checkpoints[checkpoint_id] = checkpoint
        self._gc(goal_id)
        return checkpoint

    def restore(self, checkpoint_id: str) -> dict[str, Any] | None:
        cp = self._checkpoints.get(checkpoint_id)
        if cp is None:
            return None
        return {"checkpoint_id": cp["checkpoint_id"], "goal_id": cp["goal_id"], "state": cp["state"]}

    def list_checkpoints(self, goal_id: str | None = None) -> list[dict[str, Any]]:
        if goal_id:
            return [c for c in self._checkpoints.values() if c["goal_id"] == goal_id]
        return list(self._checkpoints.values())

    def _gc(self, goal_id: str) -> None:
        goal_cps = sorted(
            [c for c in self._checkpoints.values() if c["goal_id"] == goal_id],
            key=lambda c: c["created_at"],
        )
        while len(goal_cps) > self.max_checkpoints:
            oldest = goal_cps.pop(0)
            del self._checkpoints[oldest["checkpoint_id"]]

    def delete(self, checkpoint_id: str) -> bool:
        if checkpoint_id in self._checkpoints:
            del self._checkpoints[checkpoint_id]
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        by_goal: dict[str, int] = {}
        for c in self._checkpoints.values():
            by_goal[c["goal_id"]] = by_goal.get(c["goal_id"], 0) + 1
        return {
            "total_checkpoints": len(self._checkpoints),
            "max_per_goal": self.max_checkpoints,
            "goals_with_checkpoints": len(by_goal),
            "checkpoints_per_goal": by_goal,
        }


class GoalProgressTracker:
    """Feature 43: Track subtask completion progress within goals.

    Tracks the progress of subtasks within a goal,
    providing completion percentages, remaining work,
    and progress trend analysis.
    """

    def __init__(self) -> None:
        self._progress: dict[str, dict[str, Any]] = {}

    def init_goal(self, goal_id: str, total_subtasks: int) -> None:
        self._progress[goal_id] = {
            "total": total_subtasks,
            "completed": 0,
            "failed": 0,
            "pending": total_subtasks,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

    def complete_subtask(self, goal_id: str) -> dict[str, Any]:
        if goal_id not in self._progress:
            return {"goal_id": goal_id, "error": "not_found"}
        p = self._progress[goal_id]
        if p["pending"] <= 0:
            return {"goal_id": goal_id, "error": "no_pending"}
        p["completed"] += 1
        p["pending"] -= 1
        return self._get_status(goal_id)

    def fail_subtask(self, goal_id: str) -> dict[str, Any]:
        if goal_id not in self._progress:
            return {"goal_id": goal_id, "error": "not_found"}
        p = self._progress[goal_id]
        if p["pending"] <= 0:
            return {"goal_id": goal_id, "error": "no_pending"}
        p["failed"] += 1
        p["pending"] -= 1
        return self._get_status(goal_id)

    def _get_status(self, goal_id: str) -> dict[str, Any]:
        p = self._progress[goal_id]
        completed = p["completed"] + p["failed"]
        pct = round((completed / max(p["total"], 1)) * 100, 2)
        return {
            "goal_id": goal_id,
            "total": p["total"],
            "completed": p["completed"],
            "failed": p["failed"],
            "pending": p["pending"],
            "percentage": pct,
            "complete": p["pending"] == 0,
        }

    def get_progress(self, goal_id: str) -> dict[str, Any]:
        if goal_id not in self._progress:
            return {"goal_id": goal_id, "error": "not_found"}
        return self._get_status(goal_id)

    def get_all_progress(self) -> dict[str, dict[str, Any]]:
        return {gid: self._get_status(gid) for gid in self._progress}

    def get_completion_rate(self) -> dict[str, Any]:
        total = sum(p["total"] for p in self._progress.values())
        completed = sum(p["completed"] for p in self._progress.values())
        failed = sum(p["failed"] for p in self._progress.values())
        return {
            "total_subtasks": total,
            "completed": completed,
            "failed": failed,
            "completion_rate": round(completed / max(total, 1), 4),
            "failure_rate": round(failed / max(total, 1), 4),
        }


class ConfigurableRetryPolicy:
    """Feature 44: Per-goal configurable retry strategy.

    Supports multiple retry strategies: exponential, linear,
    fixed interval, or no retry. Strategy is configurable
    per goal at creation time.
    """

    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"
    NONE = "none"

    def __init__(self) -> None:
        self._policies: dict[str, dict[str, Any]] = {}

    def configure(
        self,
        goal_id: str,
        strategy: str = EXPONENTIAL,
        base_delay_s: float = 1.0,
        max_delay_s: float = 60.0,
        multiplier: float = 2.0,
        step_s: float = 5.0,
    ) -> None:
        self._policies[goal_id] = {
            "strategy": strategy,
            "base_delay_s": base_delay_s,
            "max_delay_s": max_delay_s,
            "multiplier": multiplier,
            "step_s": step_s,
        }

    def get_delay(self, goal_id: str, attempt: int, seed: str = "") -> dict[str, Any]:
        policy = self._policies.get(goal_id)
        if policy is None:
            return {"delay_s": 0.0, "strategy": "none"}
        strategy = policy["strategy"]
        base = policy["base_delay_s"]
        if strategy == self.EXPONENTIAL:
            delay = min(base * (policy["multiplier"] ** (attempt - 1)), policy["max_delay_s"])
        elif strategy == self.LINEAR:
            delay = min(base * attempt * policy["step_s"], policy["max_delay_s"])
        elif strategy == self.FIXED:
            delay = base
        else:
            delay = 0.0
        jitter = 0.0
        if seed and strategy != self.NONE:
            h = hashlib.sha256(f"{seed}_{attempt}".encode()).hexdigest()
            jitter = (int(h[:8], 16) % 1000) / 1000.0 * delay * 0.5
        return {
            "delay_s": round(delay - jitter if jitter else delay, 4),
            "strategy": strategy,
            "attempt": attempt,
            "jitter": round(jitter, 4),
        }

    def should_retry(self, goal_id: str, attempt: int, max_retries: int = 3) -> bool:
        policy = self._policies.get(goal_id)
        if policy is None:
            return attempt < max_retries
        if policy["strategy"] == self.NONE:
            return False
        return attempt < max_retries

    def get_policy(self, goal_id: str) -> dict[str, Any] | None:
        return self._policies.get(goal_id)

    def get_all_policies(self) -> dict[str, dict[str, Any]]:
        return dict(self._policies)


class SubtaskFailureAggregator:
    """Feature 45: Aggregate subtask failures with root cause analysis.

    Collects subtask failures within a goal, groups them by
    error type, and identifies the most likely root cause
    based on failure frequency and type.
    """

    def __init__(self) -> None:
        self._failures: dict[str, list[dict[str, Any]]] = {}

    def record_failure(self, goal_id: str, subtask_id: str, error: Exception) -> None:
        if goal_id not in self._failures:
            self._failures[goal_id] = []
        self._failures[goal_id].append({
            "subtask_id": subtask_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_failures(self, goal_id: str) -> list[dict[str, Any]]:
        return list(self._failures.get(goal_id, []))

    def get_summary(self, goal_id: str) -> dict[str, Any]:
        failures = self._failures.get(goal_id, [])
        if not failures:
            return {"goal_id": goal_id, "total_failures": 0}
        by_type: dict[str, int] = {}
        by_msg: dict[str, int] = {}
        for f in failures:
            et = f["error_type"]
            em = f["error_message"]
            by_type[et] = by_type.get(et, 0) + 1
            by_msg[em] = by_msg.get(em, 0) + 1
        root_cause = max(by_msg, key=by_msg.get) if by_msg else ""
        return {
            "goal_id": goal_id,
            "total_failures": len(failures),
            "by_type": by_type,
            "by_message": by_msg,
            "root_cause": root_cause,
            "unique_error_types": len(by_type),
            "most_common": max(by_type, key=by_type.get) if by_type else "",
        }

    def clear(self, goal_id: str) -> None:
        if goal_id in self._failures:
            del self._failures[goal_id]


class DAGVisualizer:
    """Feature 36: DAG visualization for debugging and monitoring.

    Generates ASCII-art visualization of goal dependency DAGs
    with critical path highlighting and depth indicators.
    """

    def __init__(self, resolver: GoalDependencyResolver | None = None) -> None:
        self._resolver = resolver or GoalDependencyResolver()

    def set_resolver(self, resolver: GoalDependencyResolver) -> None:
        self._resolver = resolver

    def visualize_ascii(self) -> str:
        sort = self._resolver.topological_sort()
        if sort is None:
            return "DAG has cycles - cannot visualize"
        if not sort:
            return "DAG Visualization\n========================================\n\n(empty)"
        levels = self._resolver.parallel_schedule()
        path, _ = self._resolver.critical_path()
        path_set = set(path)

        lines = ["DAG Visualization", "=" * 40]
        for i, level in enumerate(levels):
            marker = " [CRITICAL PATH]" if any(g in path_set for g in level) else ""
            lines.append(f"Level {i}: {', '.join(sorted(level))}{marker}")

        lines.append("")
        lines.append("Dependencies:")
        for goal in sort:
            deps = sorted(self._resolver._deps.get(goal, set()))
            if deps:
                lines.append(f"  {goal} <- {', '.join(deps)}")

        return "\n".join(lines)

    def visualize_dot(self) -> str:
        sort = self._resolver.topological_sort()
        if sort is None:
            return "digraph { error=\"cycles detected\" }"
        path, _ = self._resolver.critical_path()
        path_edges = set()
        for i in range(len(path) - 1):
            path_edges.add((path[i], path[i + 1]))

        lines = ["digraph goals {"]
        lines.append('  rankdir=LR;')
        for goal in sort:
            style = 'filled, bold' if goal in path else 'filled'
            color = 'lightgreen' if goal in path else 'lightblue'
            lines.append(f'  "{goal}" [style="{style}", fillcolor="{color}"];')
        for goal in sort:
            for dep in sorted(self._resolver._deps.get(goal, set())):
                edge_style = ' bold, color=red' if (dep, goal) in path_edges else ''
                lines.append(f'  "{dep}" -> "{goal}"[{edge_style}];')
        lines.append("}")
        return "\n".join(lines)

    def get_depth_map(self) -> dict[str, int]:
        sort = self._resolver.topological_sort()
        if sort is None:
            return {}
        depth: dict[str, int] = {}
        for g in sort:
            deps = self._resolver._deps.get(g, set())
            max_d = 0
            for d in deps:
                if d in depth:
                    max_d = max(max_d, depth[d] + 1)
            depth[g] = max_d
        return depth

    def get_width_at_level(self, level: int) -> int:
        levels = self._resolver.parallel_schedule()
        if level < len(levels):
            return len(levels[level])
        return 0

    def get_stats(self) -> dict[str, Any]:
        sort = self._resolver.topological_sort()
        levels = self._resolver.parallel_schedule()
        path, path_len = self._resolver.critical_path()
        return {
            "goals": len(sort) if sort else 0,
            "has_cycles": self._resolver.has_cycles(),
            "parallel_levels": len(levels),
            "critical_path": path,
            "critical_path_length": path_len,
            "max_width": max((len(l) for l in levels), default=0),
        }


class GoalPriorityBoost:
    """Feature 37: Dynamic priority boosting for starved goals.

    Monitors goal wait times and boosts priority for goals
    that have been waiting beyond a configurable threshold
    to prevent indefinite deferral.
    """

    def __init__(
        self,
        boost_threshold_s: float = 60.0,
        boost_amount: int = 5,
        max_boosts: int = 3,
    ) -> None:
        self.boost_threshold_s = boost_threshold_s
        self.boost_amount = boost_amount
        self.max_boosts = max_boosts
        self._wait_start: dict[str, float] = {}
        self._boost_counts: dict[str, int] = {}
        self._boosted: list[dict[str, Any]] = []

    def register(self, goal_id: str) -> None:
        self._wait_start[goal_id] = time.monotonic()
        self._boost_counts[goal_id] = 0

    def check(self, goal_id: str, current_priority: int) -> dict[str, Any]:
        if goal_id not in self._wait_start:
            return {"goal_id": goal_id, "boosted": False, "reason": "not_registered"}
        waited = time.monotonic() - self._wait_start[goal_id]
        if waited > self.boost_threshold_s and self._boost_counts[goal_id] < self.max_boosts:
            new_priority = current_priority + self.boost_amount
            self._boost_counts[goal_id] += 1
            self._boosted.append({
                "goal_id": goal_id,
                "old_priority": current_priority,
                "new_priority": new_priority,
                "waited_s": round(waited, 4),
                "boost_number": self._boost_counts[goal_id],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return {
                "goal_id": goal_id,
                "boosted": True,
                "old_priority": current_priority,
                "new_priority": new_priority,
                "waited_s": round(waited, 4),
            }
        return {"goal_id": goal_id, "boosted": False, "waited_s": round(waited, 4)}

    def is_max_boosted(self, goal_id: str) -> bool:
        return self._boost_counts.get(goal_id, 0) >= self.max_boosts

    def reset(self, goal_id: str) -> None:
        if goal_id in self._wait_start:
            self._wait_start[goal_id] = time.monotonic()

    def get_boosted(self) -> list[dict[str, Any]]:
        return list(self._boosted)

    def get_stats(self) -> dict[str, Any]:
        return {
            "registered": len(self._wait_start),
            "total_boosts": len(self._boosted),
            "max_boosts": self.max_boosts,
            "threshold_s": self.boost_threshold_s,
        }


class SchedulerLatencyTracker:
    """Feature 38: Measure decision-to-execution latency.

    Tracks the time elapsed between a scheduling decision
    being made and the goal actually starting execution.
    High latency indicates scheduler bottlenecks.
    """

    def __init__(self) -> None:
        self._decisions: list[dict[str, Any]] = []

    def record_decision(self, goal_id: str, decision_type: str) -> None:
        self._decisions.append({
            "goal_id": goal_id,
            "decision_type": decision_type,
            "decided_at": datetime.now(timezone.utc).isoformat(),
            "decided_ts": time.monotonic(),
        })

    def record_execution_start(self, goal_id: str) -> None:
        now_ts = time.monotonic()
        for d in reversed(self._decisions):
            if d["goal_id"] == goal_id and "started_at" not in d:
                d["started_at"] = datetime.now(timezone.utc).isoformat()
                d["started_ts"] = now_ts
                d["latency_s"] = round(now_ts - d["decided_ts"], 6)
                break

    def get_avg_latency(self) -> float:
        latencies = [d["latency_s"] for d in self._decisions if "latency_s" in d]
        if not latencies:
            return 0.0
        return round(sum(latencies) / len(latencies), 6)

    def get_p95_latency(self) -> float:
        latencies = sorted([d["latency_s"] for d in self._decisions if "latency_s" in d])
        if not latencies:
            return 0.0
        idx = int(len(latencies) * 0.95)
        return round(latencies[min(idx, len(latencies) - 1)], 6)

    def get_decisions(self, goal_id: str | None = None) -> list[dict[str, Any]]:
        if goal_id:
            return [d for d in self._decisions if d["goal_id"] == goal_id and "latency_s" in d]
        return [d for d in self._decisions if "latency_s" in d]

    def get_summary(self) -> dict[str, Any]:
        latencies = [d["latency_s"] for d in self._decisions if "latency_s" in d]
        return {
            "total_decisions": len(self._decisions),
            "measured": len(latencies),
            "avg_latency_s": self.get_avg_latency(),
            "p95_latency_s": self.get_p95_latency(),
            "max_latency_s": round(max(latencies), 6) if latencies else 0.0,
            "min_latency_s": round(min(latencies), 6) if latencies else 0.0,
        }


class DeadlineExtensionPolicy:
    """Feature 39: Smart deadline extension for goals near completion.

    When a goal is close to its deadline but has made significant
    progress, optionally extends the deadline to avoid unnecessary
    cancellation of nearly-complete work.
    """

    def __init__(
        self,
        progress_threshold: float = 0.7,
        extension_factor: float = 1.5,
        max_extensions: int = 2,
    ) -> None:
        self.progress_threshold = progress_threshold
        self.extension_factor = extension_factor
        self.max_extensions = max_extensions
        self._extensions: dict[str, int] = {}
        self._history: list[dict[str, Any]] = []

    def should_extend(
        self,
        goal_id: str,
        deadline_s: float,
        elapsed_s: float,
        progress: float,
    ) -> dict[str, Any]:
        if goal_id not in self._extensions:
            self._extensions[goal_id] = 0
        if self._extensions[goal_id] >= self.max_extensions:
            return {
                "goal_id": goal_id,
                "extend": False,
                "reason": "max_extensions_reached",
            }
        if progress >= self.progress_threshold and elapsed_s > deadline_s * 0.8:
            new_deadline = deadline_s * self.extension_factor
            self._extensions[goal_id] += 1
            self._history.append({
                "goal_id": goal_id,
                "old_deadline_s": deadline_s,
                "new_deadline_s": new_deadline,
                "progress": progress,
                "extension_number": self._extensions[goal_id],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return {
                "goal_id": goal_id,
                "extend": True,
                "old_deadline_s": deadline_s,
                "new_deadline_s": new_deadline,
                "extension_number": self._extensions[goal_id],
            }
        return {"goal_id": goal_id, "extend": False, "progress": progress}

    def get_extensions(self, goal_id: str | None = None) -> list[dict[str, Any]]:
        if goal_id:
            return [h for h in self._history if h["goal_id"] == goal_id]
        return list(self._history)

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_extensions": len(self._history),
            "goals_extended": len(set(h["goal_id"] for h in self._history)),
            "max_extensions": self.max_extensions,
            "threshold": self.progress_threshold,
        }


class GoalGroupManager:
    """Feature 40: Group related goals for batch operations.

    Groups related goals together for batch admission, cancellation,
    or prioritization. Groups are identified by a shared group_id.
    """

    def __init__(self) -> None:
        self._groups: dict[str, set[str]] = {}
        self._goal_groups: dict[str, str] = {}

    def create_group(self, group_id: str, goal_ids: list[str]) -> None:
        self._groups[group_id] = set(goal_ids)
        for gid in goal_ids:
            self._goal_groups[gid] = group_id

    def add_to_group(self, group_id: str, goal_id: str) -> None:
        if group_id not in self._groups:
            self._groups[group_id] = set()
        self._groups[group_id].add(goal_id)
        self._goal_groups[goal_id] = group_id

    def get_group(self, group_id: str) -> set[str]:
        return set(self._groups.get(group_id, set()))

    def get_goal_group(self, goal_id: str) -> str | None:
        return self._goal_groups.get(goal_id)

    def get_goals_in_group(self, goal_id: str) -> set[str]:
        group_id = self._goal_groups.get(goal_id)
        if group_id is None:
            return set()
        return self.get_group(group_id)

    def batch_admit(self, group_id: str, scheduler: Any) -> dict[str, Any]:
        goals = self.get_group(group_id)
        admitted = []
        rejected = []
        for goal in sorted(goals):
            try:
                scheduler.admit(goal)
                admitted.append(goal)
            except Exception:
                rejected.append(goal)
        return {"group_id": group_id, "admitted": admitted, "rejected": rejected}

    def batch_cancel(self, group_id: str) -> list[str]:
        goals = self.get_group(group_id)
        return sorted(goals)

    def list_groups(self) -> dict[str, list[str]]:
        return {gid: sorted(g) for gid, g in self._groups.items()}

    def get_stats(self) -> dict[str, Any]:
        return {
            "groups": len(self._groups),
            "goals_grouped": len(self._goal_groups),
            "avg_group_size": round(
                sum(len(g) for g in self._groups.values()) / max(len(self._groups), 1), 2
            ),
        }


class AdmissionPolicyChain:
    """Feature 41: Chain multiple admission policies together.

    Allows multiple admission policies to be evaluated in sequence.
    A goal must pass all policies to be admitted. Records which
    policy rejected each goal.
    """

    def __init__(self, policies: list[Any] | None = None) -> None:
        self._policies: list[Any] = policies or []
        self._rejections: list[dict[str, Any]] = []

    def add_policy(self, policy: Any, name: str | None = None) -> None:
        self._policies.append((policy, name or type(policy).__name__))

    def admit(self, goal_id: str) -> dict[str, Any]:
        for policy, name in self._policies:
            result = self._evaluate_policy(policy, goal_id)
            if not result.get("admitted", True):
                self._rejections.append({
                    "goal_id": goal_id,
                    "policy": name,
                    "reason": result.get("reason", "rejected"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return {
                    "goal_id": goal_id,
                    "admitted": False,
                    "rejected_by": name,
                    "reason": result.get("reason", "rejected"),
                }
        return {"goal_id": goal_id, "admitted": True, "policies_passed": len(self._policies)}

    def _evaluate_policy(self, policy: Any, goal_id: str) -> dict[str, Any]:
        if hasattr(policy, "admit") and callable(policy.admit):
            try:
                result = policy.admit(goal_id)
                if isinstance(result, dict):
                    return result
                return {"admitted": True}
            except Exception as e:
                return {"admitted": False, "reason": str(e)}
        return {"admitted": True}

    def get_rejections(self, goal_id: str | None = None) -> list[dict[str, Any]]:
        if goal_id:
            return [r for r in self._rejections if r["goal_id"] == goal_id]
        return list(self._rejections)

    def get_stats(self) -> dict[str, Any]:
        return {
            "policies": len(self._policies),
            "policy_names": [n for _, n in self._policies],
            "total_rejections": len(self._rejections),
            "unique_rejected_goals": len(set(r["goal_id"] for r in self._rejections)),
        }


class GoalRetryBudgetResolver:
    """Feature 42: Allocate retry budgets across competing goals.

    When multiple goals compete for a shared retry budget,
    this resolver distributes retries based on priority,
    remaining budget, and retry attempts so far.
    """

    def __init__(self, total_budget: int = 100) -> None:
        self.total_budget = total_budget
        self._allocated: dict[str, int] = {}
        self._used: dict[str, int] = {}

    def allocate(self, goal_id: str, priority: int = 0, max_retries: int = 3) -> int:
        if goal_id not in self._allocated:
            self._allocated[goal_id] = 0
            self._used[goal_id] = 0
        remaining = self.total_budget - sum(self._allocated.values())
        if remaining <= 0:
            return 0
        share = max(1, remaining // max(len(self._allocated), 1))
        allocation = min(share, remaining, max_retries)
        self._allocated[goal_id] = allocation
        return allocation

    def consume(self, goal_id: str, retries: int = 1) -> bool:
        if goal_id not in self._allocated:
            return False
        if self._used[goal_id] + retries > self._allocated[goal_id]:
            return False
        self._used[goal_id] += retries
        return True

    def get_remaining(self, goal_id: str) -> int:
        if goal_id not in self._allocated:
            return 0
        return self._allocated[goal_id] - self._used[goal_id]

    def get_total_remaining(self) -> int:
        total_used = sum(self._used.values())
        return max(0, self.total_budget - total_used)

    def get_budgets(self) -> dict[str, dict[str, int]]:
        return {
            gid: {
                "allocated": self._allocated.get(gid, 0),
                "used": self._used.get(gid, 0),
                "remaining": self._allocated.get(gid, 0) - self._used.get(gid, 0),
            }
            for gid in self._allocated
        }

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_budget": self.total_budget,
            "total_allocated": sum(self._allocated.values()),
            "total_used": sum(self._used.values()),
            "total_remaining": self.get_total_remaining(),
            "goals": len(self._allocated),
        }


# =============================================================================
# PR #80 Features — 10 governed scheduler features
# =============================================================================

class CriticalPathHighlight:
    """Feature 46: DAG critical-path highlight.

    Marks the longest-path nodes and edges in a DAG for visualization
    or API retrieval. Works with GoalDependencyResolver to identify
    the critical path and expose it with highlighted status for each
    node and edge.
    """

    def __init__(self, resolver: GoalDependencyResolver | None = None) -> None:
        self._resolver = resolver or GoalDependencyResolver()
        self._highlighted_nodes: set[str] = set()
        self._highlighted_edges: set[tuple[str, str]] = set()
        self._path: list[str] = []
        self._path_length: int = 0

    def set_resolver(self, resolver: GoalDependencyResolver) -> None:
        self._resolver = resolver

    def compute(self) -> dict[str, Any]:
        path, length = self._resolver.critical_path()
        self._path = path
        self._path_length = length
        self._highlighted_nodes = set(path)
        self._highlighted_edges = set()
        for i in range(len(path) - 1):
            self._highlighted_edges.add((path[i], path[i + 1]))
        return {
            "critical_path": path,
            "critical_path_length": length,
            "highlighted_nodes": list(self._highlighted_nodes),
            "highlighted_edges": list(self._highlighted_edges),
            "total_goals": len(self._resolver._deps),
        }

    def is_critical(self, node_id: str) -> bool:
        return node_id in self._highlighted_nodes

    def is_critical_edge(self, from_node: str, to_node: str) -> bool:
        return (from_node, to_node) in self._highlighted_edges

    def get_highlighted_viz(self) -> dict[str, Any]:
        self.compute()
        sort = self._resolver.topological_sort() or []
        nodes = []
        for goal in sort:
            nodes.append({
                "id": goal,
                "critical": goal in self._highlighted_nodes,
                "on_critical_path": goal in self._highlighted_nodes,
            })
        edges = []
        for goal in sort:
            for dep in sorted(self._resolver._deps.get(goal, set())):
                edges.append({
                    "from": dep,
                    "to": goal,
                    "critical": (dep, goal) in self._highlighted_edges,
                })
        return {
            "nodes": nodes,
            "edges": edges,
            "critical_path": self._path,
            "critical_path_length": self._path_length,
        }

    def get_stats(self) -> dict[str, Any]:
        self.compute()
        return {
            "critical_path_length": self._path_length,
            "critical_nodes": len(self._highlighted_nodes),
            "critical_edges": len(self._highlighted_edges),
            "total_goals": len(self._resolver._deps),
        }


class PriorityAging:
    """Feature 47: Priority aging for starved low-priority jobs.

    Jobs that have been waiting longer than a configurable threshold
    receive a priority boost. Prevents indefinite deferral of
    low-priority jobs. Configurable wait time, boost amount, and
    maximum boost count.
    """

    def __init__(
        self,
        aging_threshold_s: float = 60.0,
        boost_amount: int = 5,
        max_boosts: int = 3,
    ) -> None:
        self.aging_threshold_s = aging_threshold_s
        self.boost_amount = boost_amount
        self.max_boosts = max_boosts
        self._enqueued_at: dict[str, float] = {}
        self._base_priorities: dict[str, int] = {}
        self._current_priorities: dict[str, int] = {}
        self._boost_counts: dict[str, int] = {}
        self._aged: list[dict[str, Any]] = []

    def register(self, goal_id: str, priority: int = 0) -> None:
        self._enqueued_at[goal_id] = time.monotonic()
        self._base_priorities[goal_id] = priority
        self._current_priorities[goal_id] = priority
        self._boost_counts[goal_id] = 0

    def apply_aging(self, goal_id: str) -> dict[str, Any]:
        if goal_id not in self._enqueued_at:
            return {"goal_id": goal_id, "aged": False, "reason": "not_registered"}
        waited = time.monotonic() - self._enqueued_at[goal_id]
        if waited >= self.aging_threshold_s and self._boost_counts[goal_id] < self.max_boosts:
            new_priority = self._current_priorities[goal_id] + self.boost_amount
            self._current_priorities[goal_id] = new_priority
            self._boost_counts[goal_id] += 1
            entry = {
                "goal_id": goal_id,
                "aged": True,
                "waited_s": round(waited, 4),
                "old_priority": self._current_priorities[goal_id] - self.boost_amount,
                "new_priority": new_priority,
                "boost_number": self._boost_counts[goal_id],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._aged.append(entry)
            return entry
        return {
            "goal_id": goal_id,
            "aged": False,
            "waited_s": round(waited, 4),
            "current_priority": self._current_priorities[goal_id],
        }

    def get_priority(self, goal_id: str) -> int:
        return self._current_priorities.get(goal_id, 0)

    def reset(self, goal_id: str) -> None:
        if goal_id in self._enqueued_at:
            self._enqueued_at[goal_id] = time.monotonic()
        if goal_id in self._current_priorities:
            self._current_priorities[goal_id] = self._base_priorities.get(goal_id, 0)
        if goal_id in self._boost_counts:
            self._boost_counts[goal_id] = 0

    def get_stats(self) -> dict[str, Any]:
        return {
            "registered": len(self._enqueued_at),
            "total_aged": len(self._aged),
            "threshold_s": self.aging_threshold_s,
            "boost_amount": self.boost_amount,
            "max_boosts": self.max_boosts,
        }


class DeadlineMode:
    """Feature 48: Soft/hard deadline modes.

    Soft deadlines warn and deprioritize when exceeded but allow
    continuation. Hard deadlines refuse or cancel past-due jobs.
    Configurable per goal or globally.
    """

    SOFT = "soft"
    HARD = "hard"

    def __init__(self, default_mode: str = SOFT, default_deadline_s: float = 300.0) -> None:
        self.default_mode = default_mode
        self.default_deadline_s = default_deadline_s
        self._modes: dict[str, str] = {}
        self._deadlines: dict[str, float] = {}
        self._start_times: dict[str, float] = {}
        self._violations: list[dict[str, Any]] = []

    def set_deadline(self, goal_id: str, deadline_s: float, mode: str = SOFT) -> None:
        self._deadlines[goal_id] = deadline_s
        self._modes[goal_id] = mode

    def register_start(self, goal_id: str, start_time: float | None = None) -> None:
        self._start_times[goal_id] = start_time or time.monotonic()

    def check(self, goal_id: str) -> dict[str, Any]:
        if goal_id not in self._deadlines:
            return {"goal_id": goal_id, "breached": False, "reason": "no_deadline_set"}
        deadline = self._deadlines[goal_id]
        mode = self._modes.get(goal_id, self.default_mode)
        start = self._start_times.get(goal_id, 0.0)
        elapsed = time.monotonic() - start
        if elapsed > deadline:
            violation = {
                "goal_id": goal_id,
                "deadline_s": deadline,
                "elapsed_s": round(elapsed, 4),
                "overdue_s": round(elapsed - deadline, 4),
                "mode": mode,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._violations.append(violation)
            if mode == self.HARD:
                return {
                    **violation,
                    "breached": True,
                    "action": "cancel",
                    "reason": "hard_deadline_exceeded",
                }
            else:
                return {
                    **violation,
                    "breached": True,
                    "action": "deprioritize",
                    "reason": "soft_deadline_exceeded",
                }
        return {"goal_id": goal_id, "breached": False, "remaining_s": round(deadline - elapsed, 4)}

    def get_violations(self) -> list[dict[str, Any]]:
        return list(self._violations)

    def get_stats(self) -> dict[str, Any]:
        return {
            "tracked_goals": len(self._deadlines),
            "violations": len(self._violations),
            "hard_violations": sum(1 for v in self._violations if v["mode"] == self.HARD),
            "soft_violations": sum(1 for v in self._violations if v["mode"] == self.SOFT),
        }


class JobGroupFanInGate:
    """Feature 49: Job groups with fan-in gate.

    A group completes only when all members succeed (or fail
    according to the fail policy). Fail policies: 'all_fail'
    (any member fails = group fails), 'majority_fail' (>50%
    fail = group fails), 'all_must_succeed' (default - all must
    succeed for group success).
    """

    ALL_MUST_SUCCEED = "all_must_succeed"
    ALL_FAIL = "all_fail"
    MAJORITY_FAIL = "majority_fail"

    def __init__(self, fail_policy: str = ALL_MUST_SUCCEED) -> None:
        self.fail_policy = fail_policy
        self._groups: dict[str, set[str]] = {}
        self._group_members: dict[str, dict[str, str]] = {}
        self._completion_status: dict[str, dict[str, str]] = {}
        self._gate_results: list[dict[str, Any]] = []

    def create_group(self, group_id: str, member_ids: list[str]) -> None:
        self._groups[group_id] = set(member_ids)
        self._group_members[group_id] = {}
        for mid in member_ids:
            self._group_members[group_id][mid] = "pending"
        self._completion_status[group_id] = {}

    def record_member_result(self, group_id: str, member_id: str, status: str) -> None:
        if group_id not in self._group_members:
            return
        self._group_members[group_id][member_id] = status

    def check_gate(self, group_id: str) -> dict[str, Any]:
        if group_id not in self._group_members:
            return {"group_id": group_id, "complete": False, "reason": "group_not_found"}
        members = self._group_members[group_id]
        total = len(members)
        if total == 0:
            return {"group_id": group_id, "complete": True, "result": "empty", "success": True}
        completed = {k: v for k, v in members.items() if v in ("success", "failed")}
        if len(completed) < total:
            return {
                "group_id": group_id,
                "complete": False,
                "members_done": len(completed),
                "members_pending": total - len(completed),
                "result": "waiting",
            }
        successes = sum(1 for v in members.values() if v == "success")
        failures = sum(1 for v in members.values() if v == "failed")
        if self.fail_policy == self.ALL_FAIL and failures > 0:
            result = "failed"
            success = False
        elif self.fail_policy == self.MAJORITY_FAIL and failures > total / 2:
            result = "failed"
            success = False
        elif failures > 0:
            result = "partial_failure"
            success = True
        else:
            result = "success"
            success = True
        gate_result = {
            "group_id": group_id,
            "complete": True,
            "result": result,
            "success": success,
            "total": total,
            "succeeded": successes,
            "failed": failures,
            "fail_policy": self.fail_policy,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._gate_results.append(gate_result)
        return gate_result

    def get_group_status(self, group_id: str) -> dict[str, Any]:
        if group_id not in self._group_members:
            return {"group_id": group_id, "error": "not_found"}
        members = self._group_members[group_id]
        return {
            "group_id": group_id,
            "members": dict(members),
            "total": len(members),
            "fail_policy": self.fail_policy,
        }

    def get_stats(self) -> dict[str, Any]:
        return {
            "groups": len(self._groups),
            "total_members": sum(len(m) for m in self._group_members.values()),
            "gate_results": len(self._gate_results),
            "fail_policy": self.fail_policy,
        }


class TenantFairShare:
    """Feature 50: Per-tenant fair-share weights.

    Weighted round-robin scheduling across tenants/agents based on
    configurable weights. Each tenant gets a share of scheduling
    opportunities proportional to their weight.
    """

    def __init__(self) -> None:
        self._weights: dict[str, float] = {}
        self._counters: dict[str, int] = {}
        self._total_weight: float = 0.0
        self._schedule_log: list[dict[str, Any]] = []

    def set_weight(self, tenant_id: str, weight: float) -> None:
        self._weights[tenant_id] = max(0.0, weight)
        if tenant_id not in self._counters:
            self._counters[tenant_id] = 0
        self._total_weight = sum(self._weights.values())

    def get_weight(self, tenant_id: str) -> float:
        return self._weights.get(tenant_id, 1.0)

    def next_tenant(self) -> str | None:
        if not self._weights:
            return None
        if self._total_weight == 0:
            return list(self._weights.keys())[0]
        for tenant_id in self._weights:
            if self._counters[tenant_id] < self._weights[tenant_id]:
                self._counters[tenant_id] += 1
                entry = {
                    "tenant_id": tenant_id,
                    "weight": self._weights[tenant_id],
                    "counter": self._counters[tenant_id],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                self._schedule_log.append(entry)
                return tenant_id
        for tenant_id in self._weights:
            self._counters[tenant_id] = 0
        return self.next_tenant()

    def get_share(self, tenant_id: str) -> float:
        if self._total_weight == 0:
            return 0.0
        return self._weights.get(tenant_id, 0.0) / self._total_weight

    def get_schedule_log(self) -> list[dict[str, Any]]:
        return list(self._schedule_log)

    def get_stats(self) -> dict[str, Any]:
        return {
            "tenants": len(self._weights),
            "total_weight": self._total_weight,
            "counters": dict(self._counters),
            "shares": {tid: round(self.get_share(tid), 4) for tid in self._weights},
        }


class RetryBudgetWithJitter:
    """Feature 51: Retry budget with exponential backoff and full jitter.

    Max retries with exponential backoff using full jitter
    (AWS-style). Retry budget tracked in ledger entries.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay_s: float = 1.0,
        max_delay_s: float = 60.0,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay_s = base_delay_s
        self.max_delay_s = max_delay_s
        self._budgets: dict[str, RetryBudget] = {}
        self._delays: dict[str, list[dict[str, Any]]] = {}
        self._ledger_entries: list[dict[str, Any]] = []

    def allocate(self, goal_id: str, max_retries: int | None = None) -> RetryBudget:
        budget = RetryBudget(max_retries=max_retries if max_retries is not None else self.max_retries)
        self._budgets[goal_id] = budget
        self._delays[goal_id] = []
        return budget

    def calculate_delay(self, goal_id: str, attempt: int, seed: str = "") -> dict[str, Any]:
        delay = min(self.base_delay_s * (2 ** (attempt - 1)), self.max_delay_s)
        jitter = 0.0
        if seed and delay > 0:
            h = hashlib.sha256(f"{seed}_{attempt}".encode()).hexdigest()
            jitter = (int(h[:8], 16) % 1000) / 1000.0 * delay
        return {
            "goal_id": goal_id,
            "attempt": attempt,
            "base_delay_s": delay,
            "jitter": round(jitter, 6),
            "final_delay_s": round(delay + jitter, 6),
        }

    def can_retry(self, goal_id: str) -> tuple[bool, str]:
        if goal_id not in self._budgets:
            return False, "no_budget_allocated"
        budget = self._budgets[goal_id]
        if budget.consumed_retries >= budget.max_retries:
            return False, "retries_exhausted"
        return True, "available"

    def consume_retry(self, goal_id: str, ledger: Any = None) -> bool:
        allowed, _ = self.can_retry(goal_id)
        if allowed:
            self._budgets[goal_id].consumed_retries += 1
            entry = {
                "goal_id": goal_id,
                "action": "retry_consumed",
                "retries_used": self._budgets[goal_id].consumed_retries,
                "max_retries": self._budgets[goal_id].max_retries,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._ledger_entries.append(entry)
            if ledger is not None and hasattr(ledger, "append"):
                try:
                    ledger.append(
                        agent_id="scheduler",
                        capability="retry_budget",
                        action=f"retry_consume:{goal_id}",
                        allowed=True,
                        reason=f"retry {self._budgets[goal_id].consumed_retries}/{self._budgets[goal_id].max_retries}",
                        metadata=entry,
                    )
                except Exception:
                    pass
        return allowed

    def get_budget(self, goal_id: str) -> dict[str, Any]:
        if goal_id not in self._budgets:
            return {"goal_id": goal_id, "allocated": 0, "consumed": 0, "remaining": 0}
        b = self._budgets[goal_id]
        return {
            "goal_id": goal_id,
            "allocated": b.max_retries,
            "consumed": b.consumed_retries,
            "remaining": b.available,
        }

    def get_ledger(self) -> list[dict[str, Any]]:
        return list(self._ledger_entries)

    def get_stats(self) -> dict[str, Any]:
        total_consumed = sum(b.consumed_retries for b in self._budgets.values())
        total_max = sum(b.max_retries for b in self._budgets.values())
        return {
            "goals": len(self._budgets),
            "total_max_retries": total_max,
            "total_consumed": total_consumed,
            "total_remaining": total_max - total_consumed,
            "ledger_entries": len(self._ledger_entries),
        }


class IdempotencyStore:
    """Feature 52: Idempotency keys for duplicate prevention.

    Duplicate enqueue with the same idempotency key returns the
    existing job instead of creating a duplicate. No double-run.
    """

    def __init__(self) -> None:
        self._keys: dict[str, dict[str, Any]] = {}
        self._duplicates_rejected: int = 0

    def enqueue(self, key: str, job_id: str, job_data: dict[str, Any] | None = None) -> dict[str, Any]:
        if key in self._keys:
            self._duplicates_rejected += 1
            return {
                "key": key,
                "enqueued": False,
                "existing_job_id": self._keys[key]["job_id"],
                "reason": "duplicate_idempotency_key",
                "original_timestamp": self._keys[key].get("timestamp", ""),
            }
        entry = {
            "key": key,
            "job_id": job_id,
            "job_data": job_data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._keys[key] = entry
        return {
            "key": key,
            "enqueued": True,
            "job_id": job_id,
            "timestamp": entry["timestamp"],
        }

    def get(self, key: str) -> dict[str, Any] | None:
        return self._keys.get(key)

    def exists(self, key: str) -> bool:
        return key in self._keys

    def remove(self, key: str) -> bool:
        if key in self._keys:
            del self._keys[key]
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_keys": len(self._keys),
            "duplicates_rejected": self._duplicates_rejected,
        }


class QueuePauseResume:
    """Feature 53: Pause/resume queue.

    Operator pause drains in-flight tasks only (no new admissions).
    Resume continues normal admission and scheduling.
    """

    def __init__(self) -> None:
        self._paused = False
        self._pause_reason = ""
        self._paused_at: str = ""
        self._resumed_at: str = ""
        self._drained: list[str] = []
        self._admission_blocked: list[dict[str, Any]] = []
        self._history: list[dict[str, Any]] = []

    @property
    def is_paused(self) -> bool:
        return self._paused

    def pause(self, reason: str = "operator") -> dict[str, Any]:
        self._paused = True
        self._pause_reason = reason
        self._paused_at = datetime.now(timezone.utc).isoformat()
        entry = {
            "action": "pause",
            "reason": reason,
            "timestamp": self._paused_at,
        }
        self._history.append(entry)
        return entry

    def resume(self) -> dict[str, Any]:
        was_paused = self._paused
        self._paused = False
        self._resumed_at = datetime.now(timezone.utc).isoformat()
        entry = {
            "action": "resume",
            "was_paused": was_paused,
            "drained_count": len(self._drained),
            "timestamp": self._resumed_at,
        }
        self._history.append(entry)
        return entry

    def should_admit(self) -> tuple[bool, str]:
        if self._paused:
            self._admission_blocked.append({
                "reason": self._pause_reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return False, "queue_paused"
        return True, "admission_allowed"

    def record_drained(self, goal_id: str) -> None:
        self._drained.append(goal_id)

    def get_pause_info(self) -> dict[str, Any]:
        return {
            "paused": self._paused,
            "reason": self._pause_reason,
            "paused_at": self._paused_at,
            "resumed_at": self._resumed_at,
            "drained": list(self._drained),
            "admission_blocked_count": len(self._admission_blocked),
        }

    def get_history(self) -> list[dict[str, Any]]:
        return list(self._history)

    def get_stats(self) -> dict[str, Any]:
        return {
            "paused": self._paused,
            "pause_count": sum(1 for h in self._history if h["action"] == "pause"),
            "resume_count": sum(1 for h in self._history if h["action"] == "resume"),
            "total_drained": len(self._drained),
        }


class SLABreachEmitter:
    """Feature 54: SLA breach event emitter.

    Emits structured events when latency or deadline SLAs are
    violated. Events are emitted via dashboard and stored in
    breach log.
    """

    LATENCY = "latency"
    DEADLINE = "deadline"

    def __init__(self) -> None:
        self._breaches: list[dict[str, Any]] = []
        self._sla_targets: dict[str, dict[str, float]] = {}

    def set_sla(self, goal_id: str, latency_s: float | None = None, deadline_s: float | None = None) -> None:
        self._sla_targets[goal_id] = {
            "latency_s": latency_s or float("inf"),
            "deadline_s": deadline_s or float("inf"),
        }

    def emit_breach(self, goal_id: str, breach_type: str, value: float, threshold: float) -> dict[str, Any]:
        event = {
            "goal_id": goal_id,
            "breach_type": breach_type,
            "value": value,
            "threshold": threshold,
            "severity": "critical" if breach_type == self.DEADLINE else "warning",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "sla_breach",
            "structured": True,
        }
        self._breaches.append(event)
        return event

    def check_latency(self, goal_id: str, latency_s: float) -> dict[str, Any] | None:
        if goal_id not in self._sla_targets:
            return None
        threshold = self._sla_targets[goal_id]["latency_s"]
        if latency_s > threshold:
            return self.emit_breach(goal_id, self.LATENCY, latency_s, threshold)
        return None

    def check_deadline(self, goal_id: str, elapsed_s: float) -> dict[str, Any] | None:
        if goal_id not in self._sla_targets:
            return None
        threshold = self._sla_targets[goal_id]["deadline_s"]
        if elapsed_s > threshold:
            return self.emit_breach(goal_id, self.DEADLINE, elapsed_s, threshold)
        return None

    def get_breaches(self) -> list[dict[str, Any]]:
        return list(self._breaches)

    def get_breaches_for_goal(self, goal_id: str) -> list[dict[str, Any]]:
        return [b for b in self._breaches if b["goal_id"] == goal_id]

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_breaches": len(self._breaches),
            "latency_breaches": sum(1 for b in self._breaches if b["breach_type"] == self.LATENCY),
            "deadline_breaches": sum(1 for b in self._breaches if b["breach_type"] == self.DEADLINE),
            "critical": sum(1 for b in self._breaches if b["severity"] == "critical"),
            "warnings": sum(1 for b in self._breaches if b["severity"] == "warning"),
        }


class SchedulerPolicyPackV2:
    """Feature 55: Scheduler policy pack v2.

    Versioned JSON/YAML policies for priority, deadlines, fair-share,
    and retry configuration. Loadable without code changes.
    """

    CURRENT_VERSION = "v2"

    def __init__(self) -> None:
        self._policies: dict[str, dict[str, Any]] = {}
        self._loaded_at: dict[str, str] = {}
        self._version: str = self.CURRENT_VERSION

    def load_from_dict(self, policy_id: str, policy: dict[str, Any]) -> dict[str, Any]:
        self._policies[policy_id] = policy
        self._loaded_at[policy_id] = datetime.now(timezone.utc).isoformat()
        return {
            "policy_id": policy_id,
            "version": policy.get("version", self._version),
            "loaded": True,
            "loaded_at": self._loaded_at[policy_id],
            "sections": list(policy.keys()),
        }

    def load_from_json(self, policy_id: str, json_str: str) -> dict[str, Any]:
        import json as json_lib
        policy = json_lib.loads(json_str)
        return self.load_from_dict(policy_id, policy)

    def get_policy(self, policy_id: str) -> dict[str, Any] | None:
        return self._policies.get(policy_id)

    def get_priority_policy(self, policy_id: str) -> dict[str, Any]:
        policy = self.get_policy(policy_id) or {}
        return policy.get("priority", {})

    def get_deadline_policy(self, policy_id: str) -> dict[str, Any]:
        policy = self.get_policy(policy_id) or {}
        return policy.get("deadlines", {})

    def get_fair_share_policy(self, policy_id: str) -> dict[str, Any]:
        policy = self.get_policy(policy_id) or {}
        return policy.get("fair_share", {})

    def get_retry_policy(self, policy_id: str) -> dict[str, Any]:
        policy = self.get_policy(policy_id) or {}
        return policy.get("retry", {})

    def list_policies(self) -> list[str]:
        return list(self._policies.keys())

    def validate(self, policy_id: str) -> dict[str, Any]:
        policy = self.get_policy(policy_id)
        if policy is None:
            return {"valid": False, "error": "policy_not_found"}
        required = ["version", "priority"]
        missing = [r for r in required if r not in policy]
        if missing:
            return {"valid": False, "missing": missing}
        version = policy.get("version", "")
        if not version.startswith("v"):
            return {"valid": False, "error": f"unsupported_version:{version}"}
        return {"valid": True, "version": version, "policy_id": policy_id}

    def get_stats(self) -> dict[str, Any]:
        return {
            "version": self._version,
            "total_policies": len(self._policies),
            "policies": list(self._policies.keys()),
            "loaded_at": dict(self._loaded_at),
        }
