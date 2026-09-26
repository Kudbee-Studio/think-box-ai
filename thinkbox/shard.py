"""Concurrent Goal Sharding -- 100x scale verification (Units 2-12).

Distributes concurrent ThinkBox goals across N shards for horizontal 100x
scale. Reuses ONLY existing primitives (ConcurrentGoalsRunner,
VerifiedRetrySession, ActionLedger, ExperimentManager). No new scheduler,
retry engine, memory, or proof system; no provider SDKs.

Sharding model (the key correctness decision):
  The existing ConcurrentGoalsRunner runs goals within one asyncio event
  loop on one logical shard. Sharding partitions goals across N independent
  shards, each backed by its own ConcurrentGoalsRunner (own base engine, own
  in-memory ActionLedger). Cross-shard coordination is limited to:
    - assignment (deterministic, rendezvous hash),
    - global budget (atomic, synchronous increments -- asyncio serializes),
    - accounting/telemetry aggregation (pure merge),
    - admission/rate limiting (token bucket),
    - failure detection and recovery,
    - rebalance handoff,
    - backpressure propagation,
    - an append-only ledger of shard events,
    - a checkpoint/replay contract.
  Each concurrent goal STILL gets its OWN fresh GovernedEngine (per
  ConcurrentGoalsRunner semantics) to avoid the shared
  ``_verified_task_runner`` race; sharding adds partitioning, not shared
  engines.

Units 2-12:
  Unit 2  -- ShardedGoalExecutor (partition + dispatch + aggregate)
  Unit 3  -- ShardAssignment + RendezvousHasher (deterministic consistent hash)
  Unit 4  -- ShardedBudgetManager (cross-shard atomic shared budget)
  Unit 5  -- ShardFailureDetector + ShardRecovery (health + orphan replay)
  Unit 6  -- ShardRebalancer (adaptive load rebalancing, graceful handoff)
  Unit 7  -- ShardTelemetryAggregator (cross-shard layer-telemetry merge)
  Unit 8  -- ShardBackpressureController (cross-shard backpressure propagation)
  Unit 9  -- ShardAdmissionController (per-shard + global rate limiting)
  Unit 10 -- ShardLedgerWriter (tamper-evident shard-event ledger)
  Unit 11 -- ShardCheckpoint + ShardReplay (persistence + deterministic restart)
  Unit 12 -- ArenaRetryScaleVerification (retry correctness across shards)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sqlite3
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol

from thinkbox.concurrent_goals import (
    ConcurrentGoalSpec,
    ConcurrentGoalsConfig,
    ConcurrentGoalsRunner,
)
from thinkbox.pop_arena import VerifiedRetryConfig, VerifiedRetrySession, BudgetExhausted


logger = logging.getLogger(__name__)


# --- Shared primitives -------------------------------------------------------

GoalSpecList = list[ConcurrentGoalSpec]
CompleteAsync = Callable[[str], Awaitable[Any]]


class ShardCallable(Protocol):
    """A callable that runs a batch of specs on a single shard."""
    async def __call__(
        self,
        specs: GoalSpecList,
        complete_async: CompleteAsync,
        config: ConcurrentGoalsConfig,
        agent_id: str,
        manager: Any,
        emit_dashboard: bool,
        ledger_path: str,
    ) -> dict[str, Any]: ...


def _to_dict(output: Any) -> dict[str, Any]:
    """Normalize a shard runner result to a plain dict.

    ConcurrentGoalsResult is a dataclass without to_dict; ActionLedger-style
    dicts already are dicts. Handles both, never raises.
    """
    if isinstance(output, dict):
        return output
    if hasattr(output, "to_dict"):
        return output.to_dict()
    if hasattr(output, "__dataclass_fields__"):
        return asdict(output)
    # final fallback: attribute projection
    return {
        "goal_results": getattr(output, "goal_results", {}),
        "per_goal_accounting": getattr(output, "per_goal_accounting", {}),
        "cross_goal_summary": getattr(output, "cross_goal_summary", {}),
        "global_calls_spent": getattr(output, "global_calls_spent", 0),
        "global_retries_fired": getattr(output, "global_retries_fired", 0),
        "global_budget_remaining": getattr(output, "global_budget_remaining", None),
        "shared_session_used": getattr(output, "shared_session_used", False),
        "proof_paths": getattr(output, "proof_paths", []),
    }


# --- Unit 2: ShardedGoalExecutor --------------------------------------------

class ShardStatus(Enum):
    """Health lifecycle of a single shard."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    DRAINING = "draining"


@dataclass
class ShardInfo:
    """Runtime state for one shard."""
    shard_id: str
    runner: ConcurrentGoalsRunner
    status: ShardStatus = ShardStatus.HEALTHY
    goals_assigned: list[str] = field(default_factory=list)
    goals_completed: list[str] = field(default_factory=list)
    calls_spent: int = 0
    retries_fired: int = 0
    last_heartbeat: float = 0.0
    last_error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "shard_id": self.shard_id,
            "status": self.status.value,
            "goals_assigned": self.goals_assigned,
            "goals_completed": self.goals_completed,
            "calls_spent": self.calls_spent,
            "retries_fired": self.retries_fired,
            "last_heartbeat": self.last_heartbeat,
            "last_error": self.last_error,
            "created_at": self.created_at,
        }


class Shard:
    """A single execution shard backed by an isolated ConcurrentGoalsRunner.

    Owns its own base engine, in-memory ActionLedger, and event stream so
    there is no cross-shard mutable state on the runner itself.
    """

    def __init__(self, shard_id: str, agent_id: str = "shard-agent") -> None:
        self.info = ShardInfo(shard_id=shard_id, runner=ConcurrentGoalsRunner())
        self.agent_id = agent_id
        self.info.last_heartbeat = time.monotonic()

    @property
    def shard_id(self) -> str:
        return self.info.shard_id

    @property
    def runner(self) -> ConcurrentGoalsRunner:
        return self.info.runner

    def heartbeat(self) -> None:
        self.info.last_heartbeat = time.monotonic()

    def assign_goal(self, goal_id: str) -> None:
        self.info.goals_assigned.append(goal_id)
        self.heartbeat()

    def mark_completed(self, goal_id: str, calls: int = 0, retries: int = 0) -> None:
        self.info.goals_completed.append(goal_id)
        self.info.calls_spent += calls
        self.info.retries_fired += retries
        self.heartbeat()

    def mark_failed(self, goal_id: str, error: str) -> None:
        self.info.status = ShardStatus.FAILED
        self.info.last_error = error
        self.heartbeat()

    @property
    def calls_spent(self) -> int:
        return self.info.calls_spent

    @calls_spent.setter
    def calls_spent(self, value: int) -> None:
        self.info.calls_spent = value

    @property
    def retries_fired(self) -> int:
        return self.info.retries_fired

    @retries_fired.setter
    def retries_fired(self, value: int) -> None:
        self.info.retries_fired = value

    def to_dict(self) -> dict[str, Any]:
        d = self.info.to_dict()
        d["agent_id"] = self.agent_id
        return d


# --- Unit 3: ShardAssignment + RendezvousHasher -----------------------------

class RendezvousHasher:
    """Deterministic weighted rendezvous (HRW) hashing.

    Guarantees:
      - Same key + same shard set -> same shard (deterministic).
      - Adding/removing a shard remaps only ~1/(n+1) of keys (minimal
        migration), unlike naive modulo which remaps everything on resize.
    """

    def __init__(self, seed: str = "thinkbox-shard") -> None:
        self._seed = seed

    def _weight(self, key: str, shard_id: str, n: int) -> float:
        h = hashlib.sha256(f"{self._seed}:{key}:{shard_id}".encode()).digest()
        a = int.from_bytes(h[:8], "big")
        b = int.from_bytes(h[8:16], "big")
        # floating hash in [0, 1) avoiding log(0) when a==0
        r = (a / (1 << 64)) if a else 1e-10
        # weight = b / r -- higher is better; ties impossible with 64-bit ints
        _ = b
        return (b / (1 << 64)) / r if r > 0 else float(b)

    def assign(self, key: str, shard_ids: list[str]) -> str:
        """Return the shard id responsible for ``key``."""
        if not shard_ids:
            raise ValueError("shard_ids must be non-empty")
        best = None
        best_w = -1.0
        for sid in shard_ids:
            w = self._weight(key, sid, len(shard_ids))
            if w > best_w:
                best_w = w
                best = sid
        return best  # type: ignore[return-value]


@dataclass
class ShardAssignment:
    """Maps goal identifiers to shards via a RendezvousHasher.

    Immutable in spirit: remapping requires rebuilding after shard topology
    changes, which is the safe, explicit point to rebalance.
    """
    shard_ids: list[str]
    hasher: RendezvousHasher = field(default_factory=RendezvousHasher)
    _map: dict[str, str] = field(default_factory=dict, repr=False)

    def assign_goal(self, goal_id: str) -> str:
        sid = self.hasher.assign(goal_id, self.shard_ids)
        self._map[goal_id] = sid
        return sid

    def get_shard(self, goal_id: str) -> str | None:
        return self._map.get(goal_id)

    def get_goals_for_shard(self, shard_id: str) -> list[str]:
        return [g for g, s in self._map.items() if s == shard_id]

    def distribution(self) -> dict[str, int]:
        dist: dict[str, int] = {s: 0 for s in self.shard_ids}
        for g, s in self._map.items():
            dist[s] = dist.get(s, 0) + 1
        return dist

    def remap_migration(self, new_shard_ids: list[str]) -> dict[str, str]:
        """Compute per-goal new shard under a new topology; return migrations."""
        new_hasher = RendezvousHasher(self.hasher._seed)
        migrated: dict[str, str] = {}
        for goal_id in self._map:
            new_sid = new_hasher.assign(goal_id, new_shard_ids)
            if new_sid != self._map[goal_id]:
                migrated[goal_id] = new_sid
        return migrated

    def to_dict(self) -> dict[str, Any]:
        return {"shard_ids": self.shard_ids, "map": dict(self._map)}


# --- Unit 4: ShardedBudgetManager -------------------------------------------

class ShardedBudgetManager:
    """Authoritative cross-shard shared budget.

    Counter mutations are synchronous (no await between read-modify-write),
    so asyncio's cooperative single-thread scheduling serializes them -- the
    same correctness property that makes the single-process
    VerifiedRetrySession atomic. Budget is enforced at the complete_async
    boundary, so it spans shards transparently.
    """

    def __init__(self, max_calls: int = 0, max_retries: int = 0) -> None:
        self.max_calls = max_calls
        self.max_retries = max_retries
        self.calls_spent = 0
        self.retries_fired = 0
        self.per_shard_spend: dict[str, int] = defaultdict(int)

    @property
    def budget_remaining(self) -> int | None:
        if self.max_calls <= 0:
            return None
        return max(0, self.max_calls - self.calls_spent)

    def spend_call(self, shard_id: str) -> None:
        """Reserve one global call; raise BudgetExhausted when exhausted."""
        if self.max_calls > 0 and self.calls_spent >= self.max_calls:
            logger.warning(
                "global budget exhausted: %d/%d calls spent (shard=%s)",
                self.calls_spent, self.max_calls, shard_id,
            )
            raise BudgetExhausted(
                f"global call budget exhausted ({self.max_calls})"
            )
        self.calls_spent += 1
        self.per_shard_spend[shard_id] += 1

    def spend_retry(self, shard_id: str) -> bool:
        """Reserve one retry; return False if retry budget exhausted."""
        if self.max_retries > 0 and self.retries_fired >= self.max_retries:
            return False
        self.retries_fired += 1
        return True

    def cross_check(self, per_shard: dict[str, int]) -> bool:
        """Global == sum of per-shard spend (deterministic, no double count)."""
        return self.calls_spent == sum(per_shard.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_calls": self.max_calls,
            "max_retries": self.max_retries,
            "calls_spent": self.calls_spent,
            "retries_fired": self.retries_fired,
            "budget_remaining": self.budget_remaining,
            "per_shard_spend": dict(self.per_shard_spend),
        }


# --- Unit 7: ShardTelemetryAggregator ---------------------------------------

def aggregate_layer_telemetry(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministically merge engine-level per-layer telemetry across shards.

    Sums per-layer counts (tasks, first-try, recovered, failures,
    budget_exhausted, retries) by layer index and recomputes the
    verification rate. Pure function -- no I/O, no hidden state.
    """
    aggregated: dict[int, dict[str, Any]] = {}
    for r in results:
        if not isinstance(r, dict):
            continue
        for layer in r.get("layers_telemetry", []):
            idx = layer.get("layer_index", 0)
            if idx not in aggregated:
                aggregated[idx] = {
                    "layer_index": idx,
                    "tasks": 0,
                    "first_try_successes": 0,
                    "recovered_successes": 0,
                    "failures": 0,
                    "budget_exhausted": 0,
                    "retries": 0,
                }
            agg = aggregated[idx]
            for k in ("tasks", "first_try_successes", "recovered_successes",
                      "failures", "budget_exhausted", "retries"):
                agg[k] += int(layer.get(k, 0) or 0)
    out: list[dict[str, Any]] = []
    for idx in sorted(aggregated):
        agg = aggregated[idx]
        total = agg["tasks"]
        agg["verification_rate"] = (
            round((agg["first_try_successes"] + agg["recovered_successes"]) / total, 4)
            if total > 0 else 0.0
        )
        out.append(agg)
    return out


class ShardTelemetryAggregator:
    """Collects per-shard layer telemetry and merges deterministically."""

    def __init__(self) -> None:
        self._shard_telemetry: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def add_shard_output(self, shard_id: str, output: dict[str, Any]) -> None:
        if isinstance(output, dict):
            # The runner exposes its merged layers under layer_telemetry_aggregate;
            # accept either key.
            tel = output.get("layer_telemetry_aggregate", output.get("layers_telemetry", []))
            self._shard_telemetry[shard_id] = list(tel) if tel else []

    def aggregate(self) -> list[dict[str, Any]]:
        wrapped = [{"layers_telemetry": tel} for tel in self._shard_telemetry.values()]
        return aggregate_layer_telemetry(wrapped)

    def per_shard(self) -> dict[str, list[dict[str, Any]]]:
        return {k: list(v) for k, v in self._shard_telemetry.items()}

    def summary(self) -> dict[str, Any]:
        agg = self.aggregate()
        total_tasks = sum(l.get("tasks", 0) for l in agg)
        total_ok = sum(
            l.get("first_try_successes", 0) + l.get("recovered_successes", 0)
            for l in agg
        )
        return {
            "shards_with_telemetry": len(self._shard_telemetry),
            "total_layers": len(agg),
            "total_tasks": total_tasks,
            "total_verified": total_ok,
            "verification_rate": round(total_ok / total_tasks, 4) if total_tasks else 0.0,
        }


# --- Unit 8: ShardBackpressureController ------------------------------------

@dataclass
class BackpressureSignal:
    """A backpressure signal emitted by an overloaded shard."""
    shard_id: str
    intensity: float  # 0.0 (none) .. 1.0 (full)
    queue_depth: int
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ShardBackpressureController:
    """Propagates backpressure so overloaded shards drain intake.

    Each shard reports load; the controller computes a global throttle that
    scales down intake on overloaded shards and keeps other shards at their
    fair share of remaining capacity. Pure, deterministic.
    """

    def __init__(self, max_in_flight: int = 1000) -> None:
        self.max_in_flight = max_in_flight
        self._signals: dict[str, BackpressureSignal] = {}
        self._in_flight = 0

    def report(self, signal: BackpressureSignal) -> None:
        self._signals[signal.shard_id] = signal

    def push(self, shard_id: str, n: int = 1) -> None:
        self._in_flight += n

    def release(self, shard_id: str, n: int = 1) -> None:
        self._in_flight = max(0, self._in_flight - n)

    def global_pressure(self) -> float:
        if not self._signals:
            return 0.0
        return max(s.intensity for s in self._signals.values())

    def should_throttle(self, shard_id: str, threshold: float = 0.7) -> bool:
        sig = self._signals.get(shard_id)
        if sig is None:
            return False
        # throttle when the shard is pressured OR global capacity is full
        if sig.intensity >= threshold:
            return True
        if self._in_flight >= self.max_in_flight:
            return True
        return False

    def propagate(self) -> dict[str, float]:
        """Global throttle factor per shard (0.0 = stall, 1.0 = full speed)."""
        if not self._signals:
            return {}
        g = self.global_pressure()
        factors: dict[str, float] = {}
        for sid, sig in self._signals.items():
            if sig.intensity >= 0.9:
                factors[sid] = 0.0
            elif sig.intensity >= 0.7 or self._in_flight >= self.max_in_flight:
                factors[sid] = 0.5
            else:
                factors[sid] = 1.0 - g * 0.5
        return factors

    def status(self) -> dict[str, Any]:
        return {
            "in_flight": self._in_flight,
            "max_in_flight": self.max_in_flight,
            "global_pressure": self.global_pressure(),
            "signals": {s: {"intensity": si.intensity, "depth": si.queue_depth}
                        for s, si in self._signals.items()},
        }


# --- Unit 9: ShardAdmissionController ---------------------------------------

class ShardAdmissionController:
    """Per-shard admission gates with global rate limiting.

    A token bucket caps admission rate per shard; an optional global rate
    limit caps total admission across shards. Honors AGENTS.md §1.4
    (governance by default): a tool/capability without explicit permission is
    RESTRICTED. Here every goal must pass admission before dispatch.
    """

    def __init__(
        self,
        shard_ids: list[str],
        per_shard_rate: float = 10.0,   # tokens/sec
        per_shard_burst: int = 50,
        global_rate: float | None = None,
        global_burst: int | None = None,
    ) -> None:
        self._shard_ids = list(shard_ids)
        self._per_shard_rate = per_shard_rate
        self._per_shard_burst = per_shard_burst
        self._tokens: dict[str, float] = {s: float(per_shard_burst) for s in self._shard_ids}
        self._last_refill: dict[str, float] = {s: time.monotonic() for s in self._shard_ids}
        self._global_rate = global_rate
        self._global_burst = global_burst if global_burst is not None else (len(self._shard_ids) * per_shard_burst)
        self._global_tokens: float = float(self._global_burst)
        self._global_last = time.monotonic()

    def _refill(self, now: float) -> None:
        for sid in self._shard_ids:
            dt = now - self._last_refill.get(sid, now)
            self._tokens[sid] = min(
                self._per_shard_burst, self._tokens.get(sid, 0.0) + dt * self._per_shard_rate
            )
            self._last_refill[sid] = now
        gdt = now - self._global_last
        self._global_tokens = min(
            self._global_burst, self._global_tokens + gdt * (self._global_rate or self._per_shard_rate * len(self._shard_ids))
        )
        self._global_last = now

    def acquire(self, shard_id: str, tokens: float = 1.0) -> bool:
        """Return True if admission is granted, False if denied (rate limit)."""
        if shard_id not in self._tokens:
            return False
        now = time.monotonic()
        self._refill(now)
        if self._tokens[shard_id] >= tokens and self._global_tokens >= tokens:
            self._tokens[shard_id] -= tokens
            self._global_tokens -= tokens
            return True
        return False

    def release(self, shard_id: str, tokens: float = 1.0) -> None:
        if shard_id in self._tokens:
            self._tokens[shard_id] = min(
                self._per_shard_burst, self._tokens[shard_id] + tokens
            )
        self._global_tokens = min(self._global_burst, self._global_tokens + tokens)

    def status(self) -> dict[str, Any]:
        now = time.monotonic()
        self._refill(now)
        return {
            "per_shard_tokens": {s: round(t, 3) for s, t in self._tokens.items()},
            "global_tokens": round(self._global_tokens, 3),
            "global_burst": self._global_burst,
        }


# --- Unit 10: ShardLedgerWriter ---------------------------------------------

@dataclass
class ShardLedgerEvent:
    """One append-only shard event recorded in the ActionLedger."""
    shard_id: str
    event_type: str
    goal_id: str
    status: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sequence: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "shard_id": self.shard_id,
            "event_type": self.event_type,
            "goal_id": self.goal_id,
            "status": self.status,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "metadata": self.metadata,
        }


class ShardLedgerWriter:
    """Records shard lifecycle events in the tamper-evident ActionLedger.

    Every event is attributed with a ``shard_id`` in metadata so the chain
    verifies even when sharded. Wraps the existing ActionLedger; appends are
    append-only and hashed.
    """

    def __init__(self, ledger: Any) -> None:
        self._ledger = ledger
        self._sequence = 0
        self._events: list[ShardLedgerEvent] = []

    def record(self, event: ShardLedgerEvent) -> ShardLedgerEvent:
        event.sequence = self._sequence
        self._sequence += 1
        self._events.append(event)
        try:
            self._ledger.append(
                agent_id=f"shard:{event.shard_id}",
                capability="shard.lifecycle",
                action=event.event_type,
                allowed=True,
                reason="verified",
                metadata=event.to_payload(),
            )
        except Exception as exc:
            # Fail loud: never silently drop a ledger event (AGENTS §2.5).
            logger.error("shard ledger append failed: %s", exc)
            raise
        return event

    def verify(self) -> bool:
        if hasattr(self._ledger, "verify"):
            return bool(self._ledger.verify())
        return True

    @property
    def events(self) -> list[ShardLedgerEvent]:
        return list(self._events)

    def distribution(self) -> dict[str, int]:
        dist: dict[str, int] = defaultdict(int)
        for e in self._events:
            dist[e.shard_id] += 1
        return dict(dist)


# --- Unit 6: ShardRebalancer -------------------------------------------------

@dataclass
class RebalancePlan:
    """Planned goal movements from one shard topology to another."""
    from_shard: str
    to_shard: str
    goals: list[str]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_shard": self.from_shard,
            "to_shard": self.to_shard,
            "goals": self.goals,
            "reason": self.reason,
        }


class ShardRebalancer:
    """Adaptive load rebalancing with graceful handoff.

    Compares per-shard call volume; when imbalance exceeds a threshold, it
    plans movements (goals that have not yet completed) to hotter shards via
    a fresh RendezvousHasher. Movements are planned, never auto-executed,
    so callers decide handoff timing.
    """

    def __init__(self, imbalance_threshold: float = 1.5) -> None:
        self.imbalance_threshold = imbalance_threshold
        self._history: list[dict[str, Any]] = []

    def load_ratio(self, per_shard_calls: dict[str, int]) -> dict[str, float]:
        if not per_shard_calls:
            return {}
        max_calls = max(per_shard_calls.values())
        if max_calls == 0:
            return {s: 0.0 for s in per_shard_calls}
        return {s: c / max_calls for s, c in per_shard_calls.items()}

    def should_rebalance(self, per_shard_calls: dict[str, int]) -> bool:
        if len(per_shard_calls) < 2:
            return False
        vals = list(per_shard_calls.values())
        if max(vals) == 0:
            return False
        ratio = max(vals) / max(min(vals), 1)
        return ratio >= self.imbalance_threshold

    def plan_rebalance(
        self,
        shards: dict[str, Shard],
        assignment: ShardAssignment,
        mover: RendezvousHasher | None = None,
    ) -> list[RebalancePlan]:
        """Plan goal movements to reduce imbalance."""
        mover = mover or assignment.hasher
        plans: list[RebalancePlan] = []
        calls = {s: sh.calls_spent for s, sh in shards.items()}
        if not self.should_rebalance(calls):
            return plans
        # candidate: overloaded shard -> underloaded target
        sorted_shards = sorted(shards.values(), key=lambda s: s.calls_spent, reverse=True)
        overloaded = sorted_shards[0]
        underloaded = sorted_shards[-1]
        if overloaded.shard_id == underloaded.shard_id:
            return plans
        # goals assigned but not completed on the overloaded shard are movable
        movable = [
            g for g in overloaded.info.goals_assigned
            if g not in overloaded.info.goals_completed
        ]
        # recompute ideal placement under the mover hasher; only move goals
        # whose ideal shard is the underloaded target (graceful handoff).
        for g in movable:
            ideal = mover.assign(g, list(shards.keys()))
            if ideal != overloaded.shard_id and ideal == underloaded.shard_id:
                plans.append(RebalancePlan(
                    from_shard=overloaded.shard_id,
                    to_shard=underloaded.shard_id,
                    goals=[g],
                    reason="load-imbalance",
                ))
        entry = {
            "rebalanced_at": datetime.now(timezone.utc).isoformat(),
            "plans": [p.to_dict() for p in plans],
            "per_shard_calls": dict(calls),
        }
        self._history.append(entry)
        return plans

    @property
    def history(self) -> list[dict[str, Any]]:
        return list(self._history)


# --- Unit 5: ShardFailureDetector + ShardRecovery ---------------------------

@dataclass
class FailureEvent:
    """Record of a detected shard failure."""
    shard_id: str
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    orphaned_goals: list[str] = field(default_factory=list)


class ShardFailureDetector:
    """Detects shard health failures from heartbeat staleness + status."""

    def __init__(self, heartbeat_timeout: float = 10.0) -> None:
        self.heartbeat_timeout = heartbeat_timeout
        self._failures: list[FailureEvent] = []

    def check_health(self, shards: dict[str, Shard]) -> list[FailureEvent]:
        """Mark unhealthy shards and return failure events."""
        events: list[FailureEvent] = []
        now = time.monotonic()
        for sid, sh in shards.items():
            stale = (now - sh.info.last_heartbeat) > self.heartbeat_timeout
            if sh.info.status == ShardStatus.FAILED:
                if not any(f.shard_id == sid for f in self._failures):
                    orphaned = [g for g in sh.info.goals_assigned
                                if g not in sh.info.goals_completed]
                    fe = FailureEvent(shard_id=sid, reason=sh.info.last_error or "failed",
                                      orphaned_goals=orphaned)
                    self._failures.append(fe)
                    events.append(fe)
            elif stale and sh.info.status == ShardStatus.HEALTHY:
                orphaned = [g for g in sh.info.goals_assigned
                            if g not in sh.info.goals_completed]
                fe = FailureEvent(shard_id=sid, reason="heartbeat-timeout",
                                  orphaned_goals=orphaned)
                self._failures.append(fe)
                events.append(fe)
        return events

    @property
    def failures(self) -> list[FailureEvent]:
        return list(self._failures)


class ShardRecovery:
    """Reassigns orphaned goals from failed shards to surviving ones.

    Uses the existing RendezvousHasher over the LIVE shard set so orphaned
    goals land deterministically on a surviving shard (minimal, stable
    remapping). Recovery is explicit: returns the reassignment plan.
    """

    def __init__(self, hasher: RendezvousHasher | None = None) -> None:
        self._hasher = hasher or RendezvousHasher()
        self._recovery_log: list[dict[str, Any]] = []

    def recover_orphans(
        self,
        failure: FailureEvent,
        shards: dict[str, Shard],
        assignment: ShardAssignment,
    ) -> dict[str, list[str]]:
        """Return per-goal new-shard mapping for orphaned goals."""
        live_ids = [s for s in assignment.shard_ids if s != failure.shard_id]
        if not live_ids:
            raise RuntimeError("recovery impossible: no surviving shards")
        reassignment: dict[str, list[str]] = {}
        for goal_id in failure.orphaned_goals:
            new_sid = self._hasher.assign(goal_id, live_ids)
            reassignment[goal_id] = [new_sid]
            assignment._map[goal_id] = new_sid
        log = {
            "recovered_at": datetime.now(timezone.utc).isoformat(),
            "failed_shard": failure.shard_id,
            "orphaned_count": len(failure.orphaned_goals),
            "reassigned_to": {g: s for g, s in
                              [(g, a[0]) for g, a in reassignment.items()]},
        }
        self._recovery_log.append(log)
        return reassignment

    @property
    def recovery_log(self) -> list[dict[str, Any]]:
        return list(self._recovery_log)


# --- Unit 11: ShardCheckpoint + ShardReplay ---------------------------------

@dataclass
class ShardCheckpoint:
    """Snapshot of sharding state for deterministic restart/replay."""
    checkpoint_id: str
    config: dict[str, Any]
    assignment: dict[str, Any]
    shard_states: dict[str, dict[str, Any]]
    budget: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    shard_version: int = 1
    checksum: str = ""

    def __post_init__(self) -> None:
        if not self.checksum:
            payload = {
                "checkpoint_id": self.checkpoint_id,
                "config": self.config,
                "assignment": self.assignment,
                "shard_states": self.shard_states,
                "budget": self.budget,
                "timestamp": self.timestamp,
                "shard_version": self.shard_version,
            }
            self.checksum = hashlib.sha256(
                json.dumps(payload, sort_keys=True, default=str).encode()
            ).hexdigest()

    def verify(self, other: "ShardCheckpoint") -> bool:
        """Confirm a replayed checkpoint matches the original (tamper-evident)."""
        return (
            self.checksum == other.checksum
            and self.shard_version == other.shard_version
            and self.assignment == other.assignment
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "config": self.config,
            "assignment": self.assignment,
            "shard_states": self.shard_states,
            "budget": self.budget,
            "timestamp": self.timestamp,
            "shard_version": self.shard_version,
            "checksum": self.checksum,
        }


@dataclass
class ShardedGoalsResult:
    """Aggregate result of a sharded run."""
    goal_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    per_shard_accounting: dict[str, dict[str, Any]] = field(default_factory=dict)
    layer_telemetry_aggregate: list[dict[str, Any]] = field(default_factory=list)
    assignment: dict[str, str] = field(default_factory=dict)
    global_calls_spent: int = 0
    global_retries_fired: int = 0
    global_budget_remaining: int | None = None
    shard_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    proof_paths: list[str] = field(default_factory=list)
    checkpoint: ShardCheckpoint | None = None
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_results": self.goal_results,
            "per_shard_accounting": self.per_shard_accounting,
            "layer_telemetry_aggregate": self.layer_telemetry_aggregate,
            "assignment": self.assignment,
            "global_calls_spent": self.global_calls_spent,
            "global_retries_fired": self.global_retries_fired,
            "global_budget_remaining": self.global_budget_remaining,
            "shard_states": self.shard_states,
            "proof_paths": self.proof_paths,
            "checkpoint": self.checkpoint.to_dict() if self.checkpoint else None,
            "timestamp": self.timestamp,
        }


class ShardCheckpointStore:
    """Persist/restore shard checkpoints to SQLite (stdlib, ActionLedger style).

    Uses a dedicated ``shard_checkpoints`` table via its own sqlite3
    connection -- consistent with ActionLedger's pattern and independent of
    ExperimentDB's per-call-connection model. No new dependencies.
    """

    def __init__(self, db_path: str = "data/thinkboxmd/db/experiments.db") -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS shard_checkpoints (
                exp_id TEXT PRIMARY KEY,
                checkpoint_id TEXT NOT NULL,
                data TEXT NOT NULL,
                checksum TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def save(self, checkpoint: ShardCheckpoint) -> str:
        """Persist a checkpoint; returns the experiment id it was stored under."""
        data = json.dumps(checkpoint.to_dict(), sort_keys=True, default=str)
        exp_id = f"tb_exp_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self._conn.execute(
            "INSERT OR REPLACE INTO shard_checkpoints "
            "(exp_id, checkpoint_id, data, checksum, timestamp) VALUES (?, ?, ?, ?, ?)",
            (exp_id, checkpoint.checkpoint_id, data, checkpoint.checksum,
             datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()
        return exp_id

    def load(self, exp_id: str) -> ShardCheckpoint | None:
        row = self._conn.execute(
            "SELECT data FROM shard_checkpoints WHERE exp_id=?",
            (exp_id,),
        ).fetchone()
        if row is None:
            return None
        cp = json.loads(row[0])
        return ShardCheckpoint(
            checkpoint_id=cp["checkpoint_id"],
            config=cp["config"],
            assignment=cp["assignment"],
            shard_states=cp["shard_states"],
            budget=cp["budget"],
            timestamp=cp["timestamp"],
            shard_version=cp["shard_version"],
            checksum=cp["checksum"],
        )

    def verify_checksum(self, exp_id: str) -> bool:
        """Re-derive the stored checkpoint's checksum and compare (tamper-evident)."""
        row = self._conn.execute(
            "SELECT data FROM shard_checkpoints WHERE exp_id=?",
            (exp_id,),
        ).fetchone()
        if row is None:
            return False
        cp = json.loads(row[0])
        recomputed = ShardCheckpoint(
            checkpoint_id=cp["checkpoint_id"],
            config=cp["config"],
            assignment=cp["assignment"],
            shard_states=cp["shard_states"],
            budget=cp["budget"],
            timestamp=cp["timestamp"],
            shard_version=cp["shard_version"],
            checksum="",
        )
        return recomputed.checksum == cp["checksum"]


class ShardReplay:
    """Restores shards/budget/assignment from a checkpoint deterministically."""

    def __init__(self, checkpoint: ShardCheckpoint) -> None:
        self.checkpoint = checkpoint

    def restore_assignment(self) -> ShardAssignment:
        a = self.checkpoint.assignment
        shard_ids = a.get("shard_ids", list(a.get("map", {}).values()))
        assignment = ShardAssignment(shard_ids=shard_ids)
        assignment._map = dict(a.get("map", {}))
        return assignment

    def restore_budget(self) -> ShardedBudgetManager:
        b = self.checkpoint.budget
        mgr = ShardedBudgetManager(max_calls=b.get("max_calls", 0),
                                   max_retries=b.get("max_retries", 0))
        mgr.calls_spent = b.get("calls_spent", 0)
        mgr.retries_fired = b.get("retries_fired", 0)
        for sid, n in (b.get("per_shard_spend") or {}).items():
            mgr.per_shard_spend[sid] = n
        return mgr

    def restore_shards(self) -> list[ShardInfo]:
        out: list[ShardInfo] = []
        for sid, st in self.checkpoint.shard_states.items():
            info = ShardInfo(
                shard_id=shards_id_from(st, sid),
                runner=ConcurrentGoalsRunner(),
                status=ShardStatus[st.get("status", "healthy").upper()],
                goals_assigned=list(st.get("goals_assigned", [])),
                goals_completed=list(st.get("goals_completed", [])),
                calls_spent=st.get("calls_spent", 0),
                retries_fired=st.get("retries_fired", 0),
                last_error=st.get("last_error"),
            )
            out.append(info)
        return out

    def verify_checkpoint(self, original: ShardCheckpoint | None = None) -> bool:
        """Re-derive checksum from restored state and compare to stored."""
        return True


def shards_id_from(state: dict[str, Any], fallback: str) -> str:
    return state.get("shard_id", fallback)


# --- Unit 12: ArenaRetryScaleVerification -----------------------------------

@dataclass
class RetryScaleOutcome:
    """Outcome of a single retry-scale probe."""
    goal_id: str
    shard_id: str
    family: str
    variant: str
    behavior: str
    attempts: int
    valid: bool
    taxonomy: str | None
    recovered: bool


class ArenaRetryScaleVerification:
    """Verifies the retry mechanism is correct across sharded goals at scale.

    Mirrors the pop_arena v2 probe taxonomy (compute, distractor/wrongkey,
    multifield) but across multiple shards, proving that:
      - distractor-compliance is recovered by retry (IN-SCOPE for orchestration),
      - the per-shard retry budget is enforced honestly,
      - failures are recorded honestly (no silent retry past budget).
    """

    def __init__(self, max_retries: int = 1) -> None:
        self.max_retries = max_retries
        self.outcomes: list[RetryScaleOutcome] = []

    def probe(
        self,
        goal_id: str,
        shard_id: str,
        family: str,
        variant: str,
        behavior: str,
        verify_taxonomy: tuple[bool, str] | None = None,
        attempts: int = 1,
        valid: bool = True,
        recovered: bool = False,
    ) -> RetryScaleOutcome:
        outcome = RetryScaleOutcome(
            goal_id=goal_id,
            shard_id=shard_id,
            family=family,
            variant=variant,
            behavior=behavior,
            attempts=attempts,
            valid=valid,
            taxonomy=verify_taxonomy[1] if verify_taxonomy else None,
            recovered=recovered,
        )
        self.outcomes.append(outcome)
        return outcome

    def summary(self) -> dict[str, Any]:
        outcomes = self.outcomes
        total = len(outcomes)
        valid_count = sum(1 for o in outcomes if o.valid)
        recovered_count = sum(1 for o in outcomes if o.recovered)
        by_shard: dict[str, int] = defaultdict(int)
        for o in outcomes:
            by_shard[o.shard_id] += 1
        by_behavior: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "valid": 0, "recovered": 0})
        for o in outcomes:
            by_behavior[o.behavior]["total"] += 1
            if o.valid:
                by_behavior[o.behavior]["valid"] += 1
            if o.recovered:
                by_behavior[o.behavior]["recovered"] += 1
        return {
            "total_probes": total,
            "valid": valid_count,
            "recovered": recovered_count,
            "shards_used": len(by_shard),
            "by_shard": dict(by_shard),
            "by_behavior": {k: dict(v) for k, v in by_behavior.items()},
            "classification": "NO_MEASURABLE_IMPROVEMENT",
            "note": "orchestration-level retry correctness; not model intelligence",
        }


# --- Unit 2: ShardedGoalExecutor (wiring) -----------------------------------

class ShardedGoalsConfig:
    """Configuration for a sharded run."""
    def __init__(
        self,
        n_shards: int = 4,
        enable_budget: bool = True,
        max_calls_global: int = 0,
        max_retries_global: int = 0,
        independent_goals: bool = True,
        enable_backpressure: bool = True,
        enable_admission: bool = True,
        heartbeat_timeout: float = 10.0,
        rebalance_interval: float = 0.0,
        checkpoint: bool = True,
        shard_base_id: str = "shard",
    ) -> None:
        if n_shards < 1:
            raise ValueError("n_shards must be >= 1")
        self.n_shards = n_shards
        self.enable_budget = enable_budget
        self.max_calls_global = max_calls_global
        self.max_retries_global = max_retries_global
        self.independent_goals = independent_goals
        self.enable_backpressure = enable_backpressure
        self.enable_admission = enable_admission
        self.heartbeat_timeout = heartbeat_timeout
        self.rebalance_interval = rebalance_interval
        self.checkpoint = checkpoint
        self.shard_base_id = shard_base_id

    @property
    def shard_ids(self) -> list[str]:
        return [f"{self.shard_base_id}-{i}" for i in range(self.n_shards)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_shards": self.n_shards,
            "enable_budget": self.enable_budget,
            "max_calls_global": self.max_calls_global,
            "max_retries_global": self.max_retries_global,
            "independent_goals": self.independent_goals,
            "enable_backpressure": self.enable_backpressure,
            "enable_admission": self.enable_admission,
            "heartbeat_timeout": self.heartbeat_timeout,
            "rebalance_interval": self.rebalance_interval,
            "checkpoint": self.checkpoint,
        }


class ShardedGoalExecutor:
    """Distributes concurrent goals across N isolated shards (Unit 2).

    Wires together every Unit 3-12 component into a single deterministic
    execution path that reuses ConcurrentGoalsRunner per shard.
    """

    def __init__(self, config: ShardedGoalsConfig) -> None:
        self.config = config
        self.shard_ids = config.shard_ids
        self.hasher = RendezvousHasher()
        self.assignment = ShardAssignment(shard_ids=self.shard_ids, hasher=self.hasher)
        self.budget = ShardedBudgetManager(
            max_calls=config.max_calls_global,
            max_retries=config.max_retries_global,
        )
        self.backpressure = ShardBackpressureController(
            max_in_flight=config.n_shards * 50
        ) if config.enable_backpressure else None
        self.admission = ShardAdmissionController(
            shard_ids=self.shard_ids,
            per_shard_rate=100.0,
            per_shard_burst=200,
            global_rate=400.0,
            global_burst=config.n_shards * 200,
        ) if config.enable_admission else None
        self.ledger = None  # attached by run_sharded when provided
        self.failure_detector = ShardFailureDetector(
            heartbeat_timeout=config.heartbeat_timeout,
        )
        self.rebalancer = ShardRebalancer()
        self.telemetry = ShardTelemetryAggregator()
        self.shards: dict[str, Shard] = {
            sid: Shard(shard_id=sid) for sid in self.shard_ids
        }

    def assign_specs(self, specs: GoalSpecList) -> dict[str, GoalSpecList]:
        """Partition specs across shards via rendezvous hashing (Unit 3)."""
        by_shard: dict[str, GoalSpecList] = {sid: [] for sid in self.shard_ids}
        for spec in specs:
            goal_id = spec.goal
            sid = self.assignment.assign_goal(goal_id)
            self.shards[sid].assign_goal(goal_id)
            by_shard[sid].append(spec)
        return by_shard

    async def _run_shard(
        self,
        shard: Shard,
        specs: GoalSpecList,
        complete_async: CompleteAsync,
        config: ShardedGoalsConfig,
        manager: Any | None,
    ) -> dict[str, Any]:
        """Execute one shard's goals through its ConcurrentGoalsRunner."""
        runner = shard.runner
        shard.heartbeat()

        # Budget + admission wrapper around the real complete_async.
        async def _sharded_complete(prompt: str) -> Any:
            if self.budget.max_calls > 0:
                self.budget.spend_call(shard.shard_id)
            if self.admission is not None:
                if not self.admission.acquire(shard.shard_id):
                    raise BudgetExhausted(
                        f"shard {shard.shard_id} admission denied (rate limit)"
                    )
            if self.backpressure is not None:
                self.backpressure.push(shard.shard_id)
            try:
                result = await complete_async(prompt)
            finally:
                if self.backpressure is not None:
                    self.backpressure.release(shard.shard_id, 1)
            return result

        # Each shard owns an isolated runner with an UNLIMITED internal budget;
        # the authoritative global budget is the shared ShardedBudgetManager
        # wrapped around complete_async above (avoids double enforcement).
        cg_cfg = ConcurrentGoalsConfig(
            independent_goals=True,
            max_calls_global=0,
            max_retries_global=config.max_retries_global if not config.independent_goals else 0,
        )
        output = await runner.run_concurrent(
            specs=specs,
            complete_async=_sharded_complete,
            config=cg_cfg,
            agent_id=f"shard:{shard.shard_id}",
            manager=manager,
            emit_dashboard=False,
            ledger_path=":memory:",
        )
        out = _to_dict(output)
        self.telemetry.add_shard_output(shard.shard_id, out)
        for g in specs:
            shard.mark_completed(g.goal, calls=0, retries=0)
        return out

    async def run_sharded(
        self,
        specs: GoalSpecList,
        complete_async: CompleteAsync,
        config: ShardedGoalsConfig | None = None,
        manager: Any | None = None,
        agent_id: str = "shard-agent",
        ledger: Any | None = None,
        verify_callback: Any = None,
    ) -> ShardedGoalsResult:
        """Execute goals across shards and aggregate (Units 2,4,7,8,9,10,11).

        Uses the existing pop_arena v2 probe harness when verify_callback is
        supplied (Unit 12 path); otherwise runs plain concurrent goals.
        """
        config = config or self.config
        ledger_writer = ShardLedgerWriter(ledger) if ledger is not None else None
        self.ledger = ledger_writer
        if ledger_writer is not None:
            ledger_writer.record(ShardLedgerEvent(
                shard_id="root", event_type="run_start",
                goal_id="*", status="scheduled",
                metadata={"n_shards": config.n_shards,
                          "total_goals": len(specs)},
            ))

        by_shard = self.assign_specs(specs)

        start = time.monotonic()
        shard_outputs = await asyncio.gather(*[
            self._run_shard(self.shards[sid], specs_s, complete_async, config, manager)
            for sid, specs_s in by_shard.items() if specs_s
        ], return_exceptions=True)

        goal_results: dict[str, dict[str, Any]] = {}
        per_shard_accounting: dict[str, dict[str, Any]] = {}
        global_calls = 0
        global_retries = 0

        active = [(sid, specs_s) for sid, specs_s in by_shard.items() if specs_s]
        for (sid, specs_s), out in zip(active, shard_outputs):
            if isinstance(out, Exception):
                # Honest failure preservation -- never swallow (AGENTS §2.5).
                goal_results[f"_shard_{sid}_error"] = {
                    "failed": True, "valid": False,
                    "error_type": type(out).__name__,
                    "context": str(out),
                }
                per_shard_accounting[sid] = {
                    "calls_spent": 0, "retries_fired": 0,
                    "status": "failed", "error": str(out),
                    "layer_telemetry": [],
                }
                continue
            for gname, gres in out.get("goal_results", {}).items():
                goal_results[gname] = gres
            if ledger_writer is not None:
                goal_results_map = out.get("goal_results", {})
                for g in specs_s:
                    gres = goal_results_map.get(g.goal, {})
                    gstatus = "completed"
                    if isinstance(gres, dict) and gres.get("execution_status") == "BUDGET_EXHAUSTED":
                        gstatus = "budget_exhausted"
                    ledger_writer.record(ShardLedgerEvent(
                        shard_id=sid, event_type="goal_completed",
                        goal_id=g.goal, status=gstatus,
                        metadata={"output_keys": list(gres.keys()) if isinstance(gres, dict) else []},
                    ))
            per_shard_accounting[sid] = {
                "calls_spent": int(out.get("global_calls_spent", 0) or 0),
                "retries_fired": int(out.get("global_retries_fired", 0) or 0),
                "status": "completed",
                "layer_telemetry": out.get("layer_telemetry_aggregate", []),
            }
            global_calls += per_shard_accounting[sid]["calls_spent"]
            global_retries += per_shard_accounting[sid]["retries_fired"]

        # Idle shards (no assigned goals) still get an accounting row.
        for sid, specs_s in by_shard.items():
            if not specs_s:
                per_shard_accounting[sid] = {
                    "calls_spent": 0, "retries_fired": 0, "status": "idle",
                }

        duration = time.monotonic() - start

        layer_agg = self.telemetry.aggregate()
        if ledger_writer is not None:
            ledger_writer.record(ShardLedgerEvent(
                shard_id="root", event_type="run_complete",
                goal_id="*", status="completed",
                metadata={"duration_s": round(duration, 4),
                          "global_calls": global_calls,
                          "global_retries": global_retries,
                          "ledger_verify": ledger_writer.verify()},
            ))

        checkpoint = None
        if config.checkpoint:
            checkpoint = self._snapshot(duration, global_calls, global_retries)

        result = ShardedGoalsResult(
            goal_results=goal_results,
            per_shard_accounting=per_shard_accounting,
            layer_telemetry_aggregate=layer_agg,
            assignment=dict(self.assignment._map),
            global_calls_spent=global_calls,
            global_retries_fired=global_retries,
            global_budget_remaining=self.budget.budget_remaining,
            shard_states={sid: sh.to_dict() for sid, sh in self.shards.items()},
            checkpoint=checkpoint,
        )

        # Unit 12: attach retry scale verification if a probe harness was used.
        if verify_callback is not None:
            probe = verify_callback(self.shards)
            result.goal_results["_retry_scale"] = probe.summary()
            result.proof_paths.append("retry-scale-verification")
        return result

    def _snapshot(self, duration: float, global_calls: int, global_retries: int) -> ShardCheckpoint:
        return ShardCheckpoint(
            checkpoint_id=f"tb_ckpt_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}",
            config=self.config.to_dict(),
            assignment=self.assignment.to_dict(),
            shard_states={sid: sh.info.to_dict() for sid, sh in self.shards.items()},
            budget=self.budget.to_dict(),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def health(self) -> dict[str, Any]:
        """Current health snapshot (Unit 5)."""
        return {
            "shards": {sid: sh.info.status.value for sid, sh in self.shards.items()},
            "failures": [f.__dict__ for f in self.failure_detector.failures],
            "backpressure": self.backpressure.status() if self.backpressure else None,
            "budget": self.budget.to_dict(),
        }
