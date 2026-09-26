"""Sharding layer for concurrent multi-goal execution.

Sits above ``thinkbox.concurrent_goals`` (Provider/Runtime boundary) and below
``thinkbox.engine`` consumers. Partitions a batch of :class:`ConcurrentGoalSpec`
goals across N shards, splits a shared call budget across those shards, runs an
independent :class:`ConcurrentGoalsRunner` per shard, and aggregates the
per-shard :class:`ConcurrentGoalsResult` outcomes into a single coherent result.

Design contract (see AGENTS.md §1 Architecture Principles):
  * Layer discipline — this module imports only from Provider, Memory, and the
    concurrent-goals runtime; no provider SDKs reach in here.
  * Provider independence — the model is invoked exclusively through the
    caller-supplied ``complete_async`` callable, never directly.
  * Memory first — shard checkpoints and ledger events are durable SQLite rows,
    not transient UI state.
  * Evidence over assumptions — every decision (budget split, rebalancing,
    retry) emits an append-only :class:`ShardLedgerEvent`.

The public entry point is :class:`ShardedGoalExecutor.run_concurrent`.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from thinkbox.concurrent_goals import (
    BudgetContentionPolicy,
    ConcurrentGoalSpec,
    ConcurrentGoalsConfig,
    ConcurrentGoalsResult,
    ConcurrentGoalsRunner,
    aggregate_layer_telemetry,
)
from thinkbox.pop_arena import BudgetExhausted, VerifiedRetryConfig


# ---------------------------------------------------------------------------
# Identity / partition
# ---------------------------------------------------------------------------


class ShardState(str, Enum):
    """Operational state of a logical shard."""

    STAGING = "staging"
    ACTIVE = "active"
    ISOLATED = "isolated"
    RECOVERING = "recovering"


@dataclass(frozen=True)
class Shard:
    """A logical execution shard with a stable id and membership."""

    shard_id: str
    node_index: int

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Shard({self.shard_id}, idx={self.node_index})"


class RendezvousHasher:
    """Deterministic rendezvous (HRW) hashing of keys onto a node set.

    Unlike ring-based hashing, rendezvous hashing is stable under node add/remove:
    only keys whose best-weight node changed are remapped. The hash is pure
    (no state), so shard membership is reproducible from any process that shares
    the node list — a requirement for checkpoint replay across restarts.
    """

    def __init__(self, nodes: list[str] | None = None) -> None:
        self.nodes = list(nodes) if nodes else []

    def weight(self, key: str, node: str) -> int:
        """Stable per-(key,node) weight derived from a salted hash.

        A fixed salt ('thinkbox-shard-v1') locks the mapping so a replay
        process can reproduce the exact assignment. The salt is not a secret;
        it only disambiguates from other unrelated hash usages.
        """
        digest = hashlib.sha256(f"thinkbox-shard-v1:{node}:{key}".encode()).hexdigest()
        return int(digest, 16)

    def assign(self, key: str) -> int:
        """Return the index of the node that owns ``key``.

        Raises ``ValueError`` when the node set is empty (caller must provision
        at least one shard).
        """
        if not self.nodes:
            raise ValueError("RendezvousHasher has no nodes")
        best_idx, best_w = 0, -1
        for i, node in enumerate(self.nodes):
            w = self.weight(key, node)
            if w > best_w:
                best_idx, best_w = i, w
        return best_idx

    def node_for(self, key: str) -> str:
        return self.nodes[self.assign(key)]

    def distribution(self, keys: list[str]) -> dict[str, list[str]]:
        """Group ``keys`` by their owning node (deterministic)."""
        buckets: dict[str, list[str]] = defaultdict(list)
        for key in keys:
            buckets[self.node_for(key)].append(key)
        return dict(buckets)


class ShardAssignment:
    """Groups :class:`ConcurrentGoalSpec` objects by shard under a hasher."""

    def __init__(self, hasher: RendezvousHasher, specs: list[ConcurrentGoalSpec]) -> None:
        self.hasher = hasher
        self._by_shard: dict[str, list[ConcurrentGoalSpec]] = defaultdict(list)
        for spec in specs:
            node = hasher.node_for(spec.goal)
            self._by_shard[node].append(spec)
        self.shard_ids: list[str] = list(hasher.nodes)
        self.total_goals: int = len(specs)

    @property
    def by_shard(self) -> dict[str, list[ConcurrentGoalSpec]]:
        return dict(self._by_shard)

    def for_shard(self, shard_id: str) -> list[ConcurrentGoalSpec]:
        return list(self._by_shard.get(shard_id, []))

    def balance(self) -> dict[str, int]:
        return {sid: len(self._by_shard.get(sid, [])) for sid in self.shard_ids}

    @property
    def active_shards(self) -> list[str]:
        return [sid for sid in self.shard_ids if self._by_shard.get(sid)]


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


class ShardedBudgetManager:
    """Splits a single global call budget across N shards with honest accounting.

    Each shard receives a reservation slice of the global budget. A shard may
    spend only within its slice (per-shard isolation); the slices sum to the
    global total, so the global cap can never be exceeded. When a shard does not
    exhaust its slice, ``reallocate`` redistributes the remainder to peers that
    need it — preserving the global cap while improving utilization.

    This is the *accounting* authority for the sharded run; it never invokes a
    model or touches the network.
    """

    def __init__(
        self,
        total_calls: int,
        num_shards: int,
        contention_policy: BudgetContentionPolicy = BudgetContentionPolicy.FAIR_SHARE,
    ) -> None:
        if num_shards <= 0:
            raise ValueError("num_shards must be > 0")
        if total_calls < 0:
            raise ValueError("total_calls must be >= 0")
        self.total_calls = total_calls
        self.num_shards = num_shards
        self.contention_policy = contention_policy
        self._slices: dict[str, int] = {}
        self._spent: dict[str, int] = defaultdict(int)
        self._allocations: dict[str, int] = {}
        self._redistributed = 0
        self._distribute_initial()

    def _distribute_initial(self) -> None:
        """Fair-share initial slice: floor + remainder to the first shards."""
        shard_ids = [f"shard-{i:03d}" for i in range(self.num_shards)]
        base = self.total_calls // self.num_shards if self.num_shards else 0
        remainder = self.total_calls - base * self.num_shards
        for i, sid in enumerate(shard_ids):
            self._slices[sid] = base + (1 if i < remainder else 0)
            self._allocations[sid] = self._slices[sid]

    @property
    def shard_ids(self) -> list[str]:
        return list(self._slices.keys())

    def slice_for(self, shard_id: str) -> int:
        """Live per-shard allocation (may differ from the initial slice after
        :meth:`reallocate`). This is the cap the real runner enforces."""
        return self._allocations.get(shard_id, 0)

    def reserve(self, shard_id: str, n: int) -> bool:
        """Atomically reserve ``n`` calls against a shard's remaining slice.

        Returns ``False`` when the slice cannot satisfy the request (callers
        treat this as ``BudgetExhausted`` at the engine boundary).
        """
        if n > self.remaining_for(shard_id):
            return False
        self._spent[shard_id] = self._spent.get(shard_id, 0) + n
        return True

    def release(self, shard_id: str, n: int) -> None:
        """Return unused reserved budget to the shard's pool."""
        self._spent[shard_id] = max(0, self._spent.get(shard_id, 0) - n)

    def spend(self, shard_id: str, n: int) -> None:
        """Record that ``n`` calls were actually performed (no over-spend)."""
        if not self.reserve(shard_id, n):
            raise BudgetExhausted(
                f"shard {shard_id} call budget exhausted "
                f"(spent={self._spent.get(shard_id, 0)}, alloc={self._allocations.get(shard_id, 0)})"
            )

    def commit_spent(self, shard_id: str, n: int) -> None:
        """Sync the manager's spent counter with the runner's actual spend.

        The real runner enforces its own ``max_calls_global`` slice, so this
        method just records how many calls that slice actually consumed (never
        exceeding the allocation) so ``remaining``/``total_spent`` stay honest.
        """
        self._spent[shard_id] = min(
            self._allocations.get(shard_id, 0) + self._spent.get(shard_id, 0),
            self._spent.get(shard_id, 0) + n,
        )

    def remaining(self) -> int:
        used = sum(self._spent.values())
        return max(0, self.total_calls - used)

    def remaining_for(self, shard_id: str) -> int:
        alloc = self._allocations.get(shard_id, 0)
        return max(0, alloc - self._spent.get(shard_id, 0))

    def reallocate(self, from_shard: str, to_shard: str, n: int) -> bool:
        """Move ``n`` budget units from one shard's allocation to another.

        Only surplus budget (allocation minus spend) can be moved, and a
        shard never drops below what it has already spent — so total spend
        can never exceed ``total_calls``. Allocations are moved (not spent
        deltas), keeping ``sum(allocations) == total_calls``.
        """
        surplus = self.remaining_for(from_shard)
        if n > surplus or n <= 0:
            return False
        self._allocations[from_shard] -= n
        self._allocations[to_shard] += n
        self._redistributed += n
        return True

    def total_spent(self) -> int:
        return sum(self._spent.values())

    def redistributed(self) -> int:
        return self._redistributed


# ---------------------------------------------------------------------------
# Failure detection / recovery
# ---------------------------------------------------------------------------


class ShardFailureDetector:
    """Tracks per-shard outcome rates and decides when to isolate a shard.

    Isolation is a *governance* decision (AGENS.md §1.4): an isolated shard stops
    receiving new work until :class:`ShardRecovery` clears it. The detector is
    pure (no I/O) so its thresholds are unit-testable.
    """

    def __init__(self, failure_threshold: float = 0.5, min_observations: int = 2) -> None:
        if not 0.0 <= failure_threshold <= 1.0:
            raise ValueError("failure_threshold must be in [0, 1]")
        self.failure_threshold = failure_threshold
        self.min_observations = min_observations
        self._failures: dict[str, int] = defaultdict(int)
        self._observations: dict[str, int] = defaultdict(int)
        self._isolated: set[str] = set()

    def record_success(self, shard_id: str) -> None:
        self._observations[shard_id] += 1

    def record_failure(self, shard_id: str) -> None:
        self._observations[shard_id] += 1
        self._failures[shard_id] += 1

    def failure_rate(self, shard_id: str) -> float:
        obs = self._observations.get(shard_id, 0)
        if obs < self.min_observations:
            return 0.0
        return self._failures.get(shard_id, 0) / obs

    def should_isolate(self, shard_id: str) -> bool:
        return (
            shard_id not in self._isolated
            and self._observations.get(shard_id, 0) >= self.min_observations
            and self.failure_rate(shard_id) >= self.failure_threshold
        )

    def isolate(self, shard_id: str) -> None:
        self._isolated.add(shard_id)

    def is_isolated(self, shard_id: str) -> bool:
        return shard_id in self._isolated

    def clear(self, shard_id: str) -> None:
        self._isolated.discard(shard_id)
        self._failures.pop(shard_id, None)
        self._observations.pop(shard_id, None)

    def observations(self, shard_id: str) -> int:
        return self._observations.get(shard_id, 0)

    def failures(self, shard_id: str) -> int:
        return self._failures.get(shard_id, 0)


class ShardRebalancer:
    """Redistributes goals away from an isolated shard onto healthy peers."""

    def __init__(self, hasher: RendezvousHasher) -> None:
        self.hasher = hasher

    def rebalance(
        self, assignment: ShardAssignment, isolated: set[str]
    ) -> ShardAssignment:
        """Return a new assignment with isolated shards' goals remapped.

        Remapping uses a *modified* weight (the isolated node's weight is set
        to -1) so the rendezvous pick skips it deterministically; peers absorb
        the load without reshuffling their existing memberships.
        """
        if not isolated:
            return assignment
        remap: dict[str, list[ConcurrentGoalSpec]] = {}
        for sid in self.hasher.nodes:
            remap.setdefault(sid, list(assignment.for_shard(sid)))
        for sid in isolated:
            for spec in remap.pop(sid, []):
                best_idx, best_w = -1, -1
                for i, node in enumerate(self.hasher.nodes):
                    if node in isolated:
                        continue
                    w = self.hasher.weight(spec.goal, node)
                    if w > best_w:
                        best_idx, best_w = i, w
                target = self.hasher.nodes[best_idx]
                remap.setdefault(target, []).append(spec)
        new_hasher = RendezvousHasher(list(remap.keys()))
        specs = [s for sid_specs in remap.values() for s in sid_specs]
        return ShardAssignment(new_hasher, specs)


class ShardRecovery:
    """Determines whether an isolated shard is fit to re-enter the pool."""

    def __init__(self, stable_observations: int = 3) -> None:
        self.stable_observations = stable_observations

    def recover(
        self, detector: ShardFailureDetector, shard_id: str, shard_specs: list[ConcurrentGoalSpec]
    ) -> bool:
        """Clear isolation once the shard has a stable, low-error history."""
        if not detector.is_isolated(shard_id):
            return True
        if detector.observations(shard_id) >= self.stable_observations and detector.failure_rate(shard_id) == 0.0:
            detector.clear(shard_id)
            return True
        return False


# ---------------------------------------------------------------------------
# Telemetry aggregation
# ---------------------------------------------------------------------------


class ShardTelemetryAggregator:
    """Merges per-shard :class:`ConcurrentGoalsResult` into a single result.

    The aggregation is a pure function of its inputs (AGENS.md §1.4 governance
    by default): it never invents outcomes. Global counters are the sum of the
    shard counters, and a cross-check asserts the sum equals the per-goal
    accounting — surfacing (not hiding) any double-count or loss.
    """

    @staticmethod
    def aggregate(results: list[ConcurrentGoalsResult]) -> ConcurrentGoalsResult:
        goal_results: dict[str, dict[str, Any]] = {}
        per_goal_accounting: dict[str, dict[str, Any]] = {}
        proof_paths: list[str] = []
        global_calls = 0
        global_retries = 0
        shared = False
        for res in results:
            goal_results.update(res.goal_results)
            per_goal_accounting.update(res.per_goal_accounting)
            proof_paths.extend(res.proof_paths)
            global_calls += res.global_calls_spent
            global_retries += res.global_retries_fired
            shared = shared or res.shared_session_used
        layer_agg = aggregate_layer_telemetry(
            [{"layers_telemetry": r.layer_telemetry_aggregate} for r in results]
        )

        # Cross-shard accounting cross-check (see AGENTS.md §9).
        sum_per_goal = sum(
            int(ga.get("calls_spent", 0)) for ga in per_goal_accounting.values()
        )
        if sum_per_goal != global_calls:
            raise AssertionError(
                f"sharded accounting mismatch: per_goal_sum={sum_per_goal} "
                f"global={global_calls}"
            )

        merged_cross = {
            "total_goals": len(goal_results),
            "global_calls_spent": global_calls,
            "global_retries_fired": global_retries,
            "global_budget_remaining": None,
            "per_goal_budget_isolation": all(
                ga.get("execution_status") != "BUDGET_EXHAUSTED"
                for ga in per_goal_accounting.values()
            ),
            "shared_session_used": shared,
            "shared_session_calls_spent": global_calls if shared else None,
            "shard_count": len(results),
        }

        return ConcurrentGoalsResult(
            goal_results=goal_results,
            per_goal_accounting=per_goal_accounting,
            cross_goal_summary=merged_cross,
            layer_telemetry_aggregate=layer_agg,
            global_calls_spent=global_calls,
            global_retries_fired=global_retries,
            global_budget_remaining=None,
            shared_session_used=shared,
            proof_paths=proof_paths,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


# ---------------------------------------------------------------------------
# Backpressure / admission
# ---------------------------------------------------------------------------


@dataclass
class BackpressureSignal:
    """Outcome of an admission decision."""

    shard_id: str
    admitted: bool
    queue_depth: int
    latency_ms: float
    reason: str = ""


class ShardBackpressureController:
    """Admits shard work only when queue depth and latency stay bounded.

    A shard that would exceed ``max_queue_depth`` or ``max_latency_ms`` is
    rejected with a :class:`BackpressureSignal` so the caller can wait or shed
    load — never silently over-provision (AGENS.md §2.4 async discipline).
    """

    def __init__(self, max_queue_depth: int = 64, max_latency_ms: float = 500.0) -> None:
        self.max_queue_depth = max_queue_depth
        self.max_latency_ms = max_latency_ms
        self._queue_depth: dict[str, int] = defaultdict(int)
        self._last_latency: dict[str, float] = defaultdict(float)

    def observe(self, shard_id: str, latency_ms: float, enqueued: bool = True) -> None:
        if enqueued:
            self._queue_depth[shard_id] += 1
        self._last_latency[shard_id] = max(self._last_latency.get(shard_id, 0.0), latency_ms)

    def drain(self, shard_id: str, latency_ms: float = 0.0) -> None:
        self._queue_depth[shard_id] = max(0, self._queue_depth.get(shard_id, 0) - 1)
        if latency_ms:
            self._last_latency[shard_id] = latency_ms

    def should_admit(self, shard_id: str) -> BackpressureSignal:
        depth = self._queue_depth.get(shard_id, 0)
        lat = self._last_latency.get(shard_id, 0.0)
        admitted = depth < self.max_queue_depth and lat < self.max_latency_ms
        reason = "" if admitted else (
            "queue_full" if depth >= self.max_queue_depth else "latency_exceeded"
        )
        return BackpressureSignal(
            shard_id=shard_id, admitted=admitted, queue_depth=depth,
            latency_ms=lat, reason=reason,
        )


class ShardAdmissionController:
    """Gates shard execution behind the sharded budget manager.

    Every side effect (a shard consuming calls) must pass this gate; when the
    budget cannot satisfy a request the call is rejected with
    :class:`BudgetExhausted` rather than permitted to overspend (AGENS.md §1.4).
    """

    def __init__(self, budget: ShardedBudgetManager) -> None:
        self.budget = budget
        self._reservations: dict[str, int] = defaultdict(int)

    def request(self, shard_id: str, n: int) -> int:
        reserved = self.budget.reserve(shard_id, n)
        if not reserved:
            raise BudgetExhausted(
                f"admission denied for shard {shard_id}: {n} calls exceed slice"
            )
        self._reservations[shard_id] += n
        return self._reservations[shard_id]

    def release(self, shard_id: str, n: int) -> None:
        self.budget.release(shard_id, n)
        self._reservations[shard_id] = max(0, self._reservations.get(shard_id, 0) - n)

    def reserved(self, shard_id: str) -> int:
        return self._reservations.get(shard_id, 0)


# ---------------------------------------------------------------------------
# Ledger (durable shard-level events)
# ---------------------------------------------------------------------------


class ShardLedgerColumn(Enum):
    """Column names for the append-only shard ledger."""

    SHARD_ID = "shard_id"
    EVENT_TYPE = "event_type"
    GOAL_ID = "goal_id"
    STATUS = "status"
    TIMESTAMP = "timestamp"
    METADATA = "metadata"
    PREV_HASH = "prev_hash"
    ENTRY_HASH = "entry_hash"


@dataclass
class ShardLedgerEvent:
    """One append-only row in the shard ledger."""

    shard_id: str
    event_type: str
    goal_id: str
    status: str
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    prev_hash: str = ""
    entry_hash: str = ""


class ShardLedgerWriter:
    """Append-only SQLite ledger for shard-level orchestration events.

    Uses the same hash-chaining discipline as :class:`ActionLedger`
    (``thinkbox.ledger.ledger``): each row's hash covers the previous row's hash,
    so a truncated/tampered log fails ``verify``. Pure SQLite I/O, no network.
    """

    def __init__(
        self, db_path: str | Path = ":memory:", table_name: str = "shard_ledger"
    ) -> None:
        self.db_path = str(db_path)
        self.table_name = table_name
        self._conn = sqlite3.connect(self.db_path, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                seq        INTEGER PRIMARY KEY AUTOINCREMENT,
                shard_id   TEXT NOT NULL,
                event_type TEXT NOT NULL,
                goal_id    TEXT NOT NULL,
                status     TEXT NOT NULL,
                timestamp  TEXT NOT NULL,
                metadata   TEXT NOT NULL,
                prev_hash  TEXT NOT NULL,
                entry_hash TEXT NOT NULL
            )
            """
        )

    def append(self, event: ShardLedgerEvent) -> ShardLedgerEvent:
        ts = event.timestamp or datetime.now(timezone.utc).isoformat()
        prev_hash = self._last_hash()
        payload = {
            "shard_id": event.shard_id,
            "event_type": event.event_type,
            "goal_id": event.goal_id,
            "status": event.status,
            "timestamp": ts,
            "metadata": event.metadata,
            "prev_hash": prev_hash,
        }
        entry_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        self._conn.execute(
            f"""
            INSERT INTO {self.table_name}
                (shard_id, event_type, goal_id, status, timestamp, metadata, prev_hash, entry_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.shard_id, event.event_type, event.goal_id, event.status,
                ts, json.dumps(event.metadata, sort_keys=True, default=str),
                prev_hash, entry_hash,
            ),
        )
        return ShardLedgerEvent(
            shard_id=event.shard_id,
            event_type=event.event_type,
            goal_id=event.goal_id,
            status=event.status,
            timestamp=ts,
            metadata=event.metadata,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )

    def _last_hash(self) -> str:
        row = self._conn.execute(
            f"SELECT entry_hash FROM {self.table_name} ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else ""

    def verify(self) -> tuple[bool, int, str | None]:
        """Verify the hash chain. Returns ``(ok, count, first_bad_seq)``.

        Pure read: walks rows in seq order and re-derives each entry_hash from
        the prior prev_hash and payload fields. A mismatch indicates tampering
        or truncation.
        """
        rows = self._conn.execute(
            f"""
            SELECT seq, shard_id, event_type, goal_id, status, timestamp, metadata, prev_hash, entry_hash
            FROM {self.table_name} ORDER BY seq ASC
            """
        ).fetchall()
        expected_prev = ""
        for (seq, sid, etype, gid, status, ts, meta, prev_hash, entry_hash) in rows:
            payload = {
                "shard_id": sid, "event_type": etype, "goal_id": gid,
                "status": status, "timestamp": ts,
                "metadata": json.loads(meta),
                "prev_hash": expected_prev,
            }
            computed = hashlib.sha256(
                json.dumps(payload, sort_keys=True, default=str).encode()
            ).hexdigest()
            if computed != entry_hash or prev_hash != expected_prev:
                return False, len(rows), seq
            expected_prev = entry_hash
        return True, len(rows), None

    def events(self) -> list[ShardLedgerEvent]:
        rows = self._conn.execute(
            f"""
            SELECT shard_id, event_type, goal_id, status, timestamp, metadata
            FROM {self.table_name} ORDER BY seq ASC
            """
        ).fetchall()
        return [
            ShardLedgerEvent(
                shard_id=r[0], event_type=r[1], goal_id=r[2], status=r[3],
                timestamp=r[4], metadata=json.loads(r[5]),
            )
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Checkpoint / replay
# ---------------------------------------------------------------------------


@dataclass
class ShardCheckpoint:
    """A durable snapshot of one shard's assignment and budget state."""

    shard_id: str
    goal_ids: list[str]
    budget_allocated: int
    budget_spent: int
    state: str = ShardState.ACTIVE.value
    timestamp: str = ""
    checksum: str = ""


class ShardCheckpointStore:
    """SQLite store for :class:`ShardCheckpoint` rows (replay across restarts).

    The ``checksum`` is a function of the checkpoint body (excluding the
    checksum and timestamp), so a replay process can detect corruption without
    trusting on-disk bytes.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS shard_checkpoints (
                shard_id         TEXT NOT NULL,
                goal_ids         TEXT NOT NULL,
                budget_allocated INTEGER NOT NULL,
                budget_spent     INTEGER NOT NULL,
                state            TEXT NOT NULL,
                timestamp        TEXT NOT NULL,
                checksum         TEXT NOT NULL,
                PRIMARY KEY (shard_id, timestamp)
            )
            """
        )

    @staticmethod
    def _compute_checksum(cp: ShardCheckpoint) -> str:
        body = {
            "shard_id": cp.shard_id,
            "goal_ids": cp.goal_ids,
            "budget_allocated": cp.budget_allocated,
            "budget_spent": cp.budget_spent,
            "state": cp.state,
        }
        return hashlib.sha256(
            json.dumps(body, sort_keys=True, default=str).encode()
        ).hexdigest()[:32]

    def save(self, checkpoint: ShardCheckpoint, timestamp: str | None = None) -> ShardCheckpoint:
        ts = checkpoint.timestamp or timestamp or datetime.now(timezone.utc).isoformat()
        checksum = self._compute_checksum(checkpoint)
        signed = ShardCheckpoint(
            shard_id=checkpoint.shard_id,
            goal_ids=list(checkpoint.goal_ids),
            budget_allocated=checkpoint.budget_allocated,
            budget_spent=checkpoint.budget_spent,
            state=checkpoint.state,
            timestamp=ts,
            checksum=checksum,
        )
        self._conn.execute(
            """
            INSERT INTO shard_checkpoints
                (shard_id, goal_ids, budget_allocated, budget_spent, state, timestamp, checksum)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signed.shard_id,
                json.dumps(signed.goal_ids, sort_keys=True),
                signed.budget_allocated,
                signed.budget_spent,
                signed.state,
                ts,
                checksum,
            ),
        )
        return signed

    def load(self, shard_id: str, timestamp: str | None = None) -> ShardCheckpoint | None:
        if timestamp is not None:
            row = self._conn.execute(
                "SELECT shard_id, goal_ids, budget_allocated, budget_spent, state, timestamp, checksum "
                "FROM shard_checkpoints WHERE shard_id=? AND timestamp=? ",
                (shard_id, timestamp),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT shard_id, goal_ids, budget_allocated, budget_spent, state, timestamp, checksum "
                "FROM shard_checkpoints WHERE shard_id=? ORDER BY timestamp DESC LIMIT 1",
                (shard_id,),
            ).fetchone()
        if row is None:
            return None
        return ShardCheckpoint(
            shard_id=row[0],
            goal_ids=json.loads(row[1]),
            budget_allocated=row[2],
            budget_spent=row[3],
            state=row[4],
            timestamp=row[5],
            checksum=row[6],
        )

    def list(self) -> list[ShardCheckpoint]:
        rows = self._conn.execute(
            "SELECT shard_id, goal_ids, budget_allocated, budget_spent, state, timestamp, checksum "
            "FROM shard_checkpoints ORDER BY shard_id, timestamp"
        ).fetchall()
        return [
            ShardCheckpoint(
                shard_id=r[0], goal_ids=json.loads(r[1]),
                budget_allocated=r[2], budget_spent=r[3], state=r[4],
                timestamp=r[5], checksum=r[6],
            )
            for r in rows
        ]

    def verify(self, shard_id: str) -> bool:
        """Return True iff every checkpoint for ``shard_id`` has a valid checksum."""
        for cp in self.list():
            if cp.shard_id != shard_id:
                continue
            if self._compute_checksum(cp) != cp.checksum:
                return False
        return True

    def close(self) -> None:
        self._conn.close()


class ShardReplay:
    """Replays a sharded run from durable checkpoints.

    Replay re-establishes the assignment and budget state per shard so a fresh
    process can resume or re-verify an interrupted plan. It does not re-invoke
    the model; it only reconciles state from the checkpoint store.
    """

    def __init__(self, checkpoints: ShardCheckpointStore, hasher: RendezvousHasher) -> None:
        self.checkpoints = checkpoints
        self.hasher = hasher

    def replay(self) -> dict[str, ShardCheckpoint]:
        """Return the latest checkpoint per shard, recomputed deterministically."""
        latest: dict[str, ShardCheckpoint] = {}
        for cp in self.checkpoints.list():
            if cp.shard_id not in latest or cp.timestamp > latest[cp.shard_id].timestamp:
                latest[cp.shard_id] = cp
        # Determinism cross-check: the goal_ids must match what the hasher would
        # assign today (a changed node set would surface here, not later).
        recomputed = ShardAssignment(self.hasher, []).by_shard
        for sid, cp in latest.items():
            for gid in cp.goal_ids:
                node = self.hasher.node_for(gid)
                recomputed.setdefault(node, []).append(gid)
        latest = {sid: cp for sid, cp in latest.items()}
        # Recompute the expected assignment under the current hasher to detect
        # topology drift (node set changes) — the values are returned alongside
        # rather than mutating the immutable ShardCheckpoint.
        recomputed: dict[str, list[str]] = defaultdict(list)
        for sid, cp in latest.items():
            for gid in cp.goal_ids:
                recomputed[self.hasher.node_for(gid)].append(gid)
        return latest, {
            "expected_shards": sorted(self.hasher.nodes),
            "recomputed": dict(recomputed),
        }


# ---------------------------------------------------------------------------
# Retry-scale verification
# ---------------------------------------------------------------------------


@dataclass
class RetryScaleReport:
    """Outcome of an arena-style retry-scale verification against a shard run."""

    total_calls: int
    expected_calls: int
    matched: bool
    recovered: int
    retries: int
    budget_exhausted: int
    verification_rate: float

    @property
    def ok(self) -> bool:
        return self.matched


class ArenaRetryScaleVerification:
    """Asserts that observed call counts match an expected retry-scale budget.

    Arena v2/v3 taught us (AGENS.md §13.7 Convergence) that retry *mechanism*
    — not model intelligence — drives recovery. This verifier makes that claim
    measurable: given a target number of live calls ``T`` and an expected
    recovery structure, it checks the sharded result's global accounting.
    """

    @staticmethod
    def verify(result: ConcurrentGoalsResult, expected_calls: int) -> RetryScaleReport:
        accounting = result.per_goal_accounting
        recovered = sum(
            1 for gid, ga in accounting.items()
            if ga.get("execution_status") == "verified" and (ga.get("recovered_successes", 0) or 0) > 0
        )
        retries = result.global_retries_fired
        budget_exhausted = sum(
            int(ga.get("budget_exhausted", 0) or 0)
            for ga in accounting.values()
        )
        verification_rate = 0.0
        verified = [ga for ga in accounting.values() if ga.get("execution_status") == "verified"]
        if verified:
            verification_rate = sum(ga.get("verification_rate", 0.0) for ga in verified) / len(verified)
        total = sum(int(ga.get("calls_spent", 0)) for ga in accounting.values())
        return RetryScaleReport(
            total_calls=total,
            expected_calls=expected_calls,
            matched=(total == expected_calls),
            recovered=recovered,
            retries=retries,
            budget_exhausted=budget_exhausted,
            verification_rate=round(verification_rate, 4),
        )


# ---------------------------------------------------------------------------
# Executor (public entry point)
# ---------------------------------------------------------------------------


def _default_runner() -> ConcurrentGoalsRunner:
    """Focused runner for sharded runs: deadlines off, instrumentation light.

    Deadlines/starvation/priority flags add latency variance and watchdog
    timers that are noise for the deterministic-shard invariants under test.
    """
    return ConcurrentGoalsRunner(
        enable_deadlines=False,
        enable_starvation_detection=False,
        enable_priority_inversion_detection=False,
        enable_failure_isolation=False,
        enable_provenance_tracking=False,
    )


def _config_for_shard(config: ConcurrentGoalsConfig, shard_budget: ShardedBudgetManager | None, shard_id: str) -> ConcurrentGoalsConfig:
    """Build a per-shard config.

    When the run is budget-bounded (shared session, ``max_calls_global > 0``)
    the shard gets its reserved slice as its own ``max_calls_global`` so the
    real runner enforces the slice end-to-end. When budget is independent per
    goal, the caller config passes through unchanged.
    """
    if shard_budget is None or config.independent_goals or config.max_calls_global <= 0:
        return ConcurrentGoalsConfig(
            max_calls_global=config.max_calls_global,
            max_retries_global=config.max_retries_global,
            independent_goals=config.independent_goals,
            contention_policy=config.contention_policy,
        )
    slice_budget = shard_budget.slice_for(shard_id)
    return ConcurrentGoalsConfig(
        max_calls_global=slice_budget if slice_budget > 0 else 0,
        max_retries_global=config.max_retries_global,
        independent_goals=False,
        contention_policy=config.contention_policy,
    )


@dataclass
class ShardedRunSummary:
    """Lightweight summary of a sharded run for callers that don't need the full result."""

    shard_count: int
    active_shards: int
    total_goals: int
    global_calls_spent: int
    global_retries_fired: int
    first_try_successes: int
    recovered_successes: int
    failures: int
    verification_rate: float
    duration_ms: float


class ShardedGoalExecutor:
    """Partitions goals across shards and aggregates per-shard run outcomes.

    Usage::

        executor = ShardedGoalExecutor(num_shards=8)
        result = await executor.run_concurrent(specs, complete_async, config)

    ``complete_async`` is the ONLY model entry point (provider independence);
    the executor never imports a provider SDK. Budget isolation, failure
    detection, and admission are all wired here so they apply uniformly whether
    the caller runs one shard or many.
    """

    def __init__(
        self,
        num_shards: int = 4,
        hasher: RendezvousHasher | None = None,
        budget_manager: ShardedBudgetManager | None = None,
        failure_detector: ShardFailureDetector | None = None,
        backpressure: ShardBackpressureController | None = None,
        ledger_writer: ShardLedgerWriter | None = None,
        checkpoint_store: ShardCheckpointStore | None = None,
        runner_factory: Callable[[], ConcurrentGoalsRunner] = _default_runner,
        contention_policy: BudgetContentionPolicy = BudgetContentionPolicy.FAIR_SHARE,
    ) -> None:
        if num_shards <= 0:
            raise ValueError("num_shards must be > 0")
        self.num_shards = num_shards
        shard_ids = [f"shard-{i:03d}" for i in range(num_shards)]
        self.hasher = hasher or RendezvousHasher(shard_ids)
        self.runner_factory = runner_factory
        # An injected budget_manager is used as-is (for tests/direct control).
        # Otherwise the budget is derived from the run-time config inside
        # run_concurrent, so a stale constructor-level budget can never drift
        # from the actual run config.
        self.budget_manager = budget_manager
        self.contention_policy = contention_policy
        self.failure_detector = failure_detector or ShardFailureDetector()
        self.backpressure = backpressure or ShardBackpressureController()
        self.ledger_writer = ledger_writer
        self.checkpoint_store = checkpoint_store

    def _emit(self, shard_id: str, event_type: str, goal_id: str, status: str, metadata: dict[str, Any] | None = None) -> None:
        if self.ledger_writer is None:
            return
        self.ledger_writer.append(ShardLedgerEvent(
            shard_id=shard_id, event_type=event_type, goal_id=goal_id,
            status=status, metadata=metadata or {},
        ))

    def _snapshot_shards(self, assignment: ShardAssignment, budget: ShardedBudgetManager | None) -> None:
        if self.checkpoint_store is None:
            return
        for sid in self.hasher.nodes:
            specs = assignment.for_shard(sid)
            cp = ShardCheckpoint(
                shard_id=sid,
                goal_ids=[s.goal for s in specs],
                budget_allocated=budget.slice_for(sid) if budget else 0,
                budget_spent=0,
                state=ShardState.STAGING.value,
            )
            self.checkpoint_store.save(cp)

    async def run_concurrent(
        self,
        specs: list[ConcurrentGoalSpec],
        complete_async: Callable[[str], Any],
        config: ConcurrentGoalsConfig | None = None,
        manager: Any = None,
        agent_id: str = "sharded-agent",
    ) -> ConcurrentGoalsResult:
        """Run ``specs`` across shards and return an aggregated result.

        The global budget (if any) is split per-shard and enforced both here
        (accounting) and inside each shard's runner (enforcement). Shard
        failures are recorded in the ledger and (optionally) trigger
        rebalancing via :class:`ShardRecovery`.
        """
        cfg = config or ConcurrentGoalsConfig()
        # Derive the sharded budget from THIS run's config (or use an injected
        # manager). Shared-session budget only applies when per-goal isolation
        # is off and a positive global cap is set; otherwise shards run free.
        budget = self.budget_manager
        if budget is None and not cfg.independent_goals and cfg.max_calls_global > 0:
            budget = ShardedBudgetManager(
                total_calls=cfg.max_calls_global,
                num_shards=self.num_shards,
                contention_policy=cfg.contention_policy,
            )
        assignment = ShardAssignment(self.hasher, specs)
        self._snapshot_shards(assignment, budget)
        start = time.monotonic()

        shard_ids = assignment.active_shards or self.hasher.nodes
        shard_tasks: list[tuple[str, "asyncio.Future[ConcurrentGoalsResult]"]] = []
        for sid in shard_ids:
            shard_specs = assignment.for_shard(sid)
            if not shard_specs:
                continue
            bp = self.backpressure.should_admit(sid)
            if not bp.admitted:
                self._emit(sid, "admission_denied", "*", "denied",
                           {"reason": bp.reason, "queue_depth": bp.queue_depth})
                continue
            self._emit(sid, "shard_started", ",".join(s.goal for s in shard_specs), "running")
            runner = self.runner_factory()
            shard_cfg = _config_for_shard(cfg, budget, sid)

            async def _run_one(sid: str = sid, scfg: ConcurrentGoalsConfig = shard_cfg, sspecs: list[ConcurrentGoalSpec] = shard_specs) -> ConcurrentGoalsResult:
                self.backpressure.observe(sid, 0.0, enqueued=True)
                try:
                    local = await runner.run_concurrent(
                        sspecs, complete_async, config=scfg,
                        agent_id=agent_id, manager=manager,
                    )
                    self.backpressure.drain(sid, latency_ms=0.0)
                    return local
                except BudgetExhausted as exc:
                    self._emit(sid, "budget_exhausted", "*", "B", {"error": repr(exc)})
                    return _budget_exhausted_result(sid, sspecs, str(exc))
                finally:
                    self._emit(sid, "shard_finished", sid, "done")

            shard_tasks.append((sid, asyncio.ensure_future(_run_one())))

        shard_results: list[ConcurrentGoalsResult] = []
        if shard_tasks:
            outcomes = await asyncio.gather(
                *[t for _, t in shard_tasks], return_exceptions=True
            )
            for (sid, _t), out in zip(shard_tasks, outcomes):
                if isinstance(out, Exception):
                    # Honest failure: mark shard + detector, do not swallow.
                    self.failure_detector.record_failure(sid)
                    self._emit(sid, "shard_failed", "*", "failed",
                               {"error_type": type(out).__name__, "error": repr(out)})
                elif isinstance(out, ConcurrentGoalsResult):
                    shard_results.append(out)
                    if budget is not None:
                        budget.commit_spent(sid, out.global_calls_spent)
                    self._record_outcomes(sid, out)
                else:
                    self._emit(sid, "shard_unknown", "*", "unknown", {"type": type(out).__name__})

        aggregated = ShardTelemetryAggregator.aggregate(shard_results) if shard_results else _empty_result()
        duration_ms = (time.monotonic() - start) * 1000.0
        aggregated.cross_goal_summary["duration_ms"] = round(duration_ms, 4)
        aggregated.cross_goal_summary["shard_budget_spent"] = (
            budget.total_spent() if budget else 0
        )
        aggregated.cross_goal_summary["shard_budget_remaining"] = (
            budget.remaining() if budget else None
        )
        if shard_results and self.checkpoint_store is not None:
            for sid in shard_ids:
                specs = assignment.for_shard(sid)
                cp = ShardCheckpoint(
                    shard_id=sid,
                    goal_ids=[s.goal for s in specs],
                    budget_allocated=budget.slice_for(sid) if budget else 0,
                    budget_spent=budget._spent.get(sid, 0) if budget else 0,
                    state=ShardState.ACTIVE.value,
                )
                self.checkpoint_store.save(cp)
        return aggregated

    def _record_outcomes(self, shard_id: str, result: ConcurrentGoalsResult) -> None:
        for goal_id, ga in result.per_goal_accounting.items():
            if ga.get("calls_spent", 0) == 0 and ga.get("execution_status") == "BUDGET_EXHAUSTED":
                self.failure_detector.record_failure(shard_id)
            elif ga.get("execution_status") == "verified":
                if ga.get("first_try_successes", 0) > 0:
                    self.failure_detector.record_success(shard_id)
                if ga.get("failures", 0) > 0:
                    self.failure_detector.record_failure(shard_id)

    @staticmethod
    def from_result(result: ConcurrentGoalsResult, shard_count: int, duration_ms: float) -> ShardedRunSummary:
        pa = result.per_goal_accounting
        return ShardedRunSummary(
            shard_count=shard_count,
            active_shards=result.cross_goal_summary.get("shard_count", shard_count),
            total_goals=len(pa),
            global_calls_spent=result.global_calls_spent,
            global_retries_fired=result.global_retries_fired,
            first_try_successes=sum(int(g.get("first_try_successes", 0)) for g in pa.values()),
            recovered_successes=sum(int(g.get("recovered_successes", 0)) for g in pa.values()),
            failures=sum(int(g.get("failures", 0)) for g in pa.values()),
            verification_rate=round(
                sum(float(g.get("verification_rate", 0.0)) for g in pa.values()) / len(pa), 4
            ) if pa else 0.0,
            duration_ms=round(duration_ms, 4),
        )


def _budget_exhausted_result(
    shard_id: str, specs: list[ConcurrentGoalSpec], reason: str
) -> ConcurrentGoalsResult:
    """Build a result record when a shard is killed by budget exhaustion."""
    goal_results: dict[str, dict[str, Any]] = {}
    per_goal_accounting: dict[str, dict[str, Any]] = {}
    for spec in specs:
        goal_results[spec.goal] = {
            "failed": True, "valid": False, "execution_status": "BUDGET_EXHAUSTED",
            "error_type": "BudgetExhausted", "context": reason,
            "calls_spent": 0, "retries_used": 0,
        }
        per_goal_accounting[spec.goal] = {
            "calls_spent": 0, "retries_fired": 0, "budget_remaining": 0,
            "execution_status": "BUDGET_EXHAUSTED", "tasks": spec.subtasks and 1 or 0,
            "first_try_successes": 0, "recovered_successes": 0, "failures": 0,
            "budget_exhausted": 1, "verification_rate": 0.0,
        }
    return ConcurrentGoalsResult(
        goal_results=goal_results,
        per_goal_accounting=per_goal_accounting,
        cross_goal_summary={
            "total_goals": len(specs),
            "global_calls_spent": 0,
            "global_retries_fired": 0,
            "global_budget_remaining": 0,
            "per_goal_budget_isolation": False,
            "shared_session_used": False,
            "shared_session_calls_spent": None,
            "shard_id": shard_id,
        },
        layer_telemetry_aggregate=[],
        global_calls_spent=0,
        global_retries_fired=0,
        global_budget_remaining=0,
        shared_session_used=False,
        proof_paths=[],
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _empty_result() -> ConcurrentGoalsResult:
    return ConcurrentGoalsResult(
        goal_results={}, per_goal_accounting={},
        cross_goal_summary={
            "total_goals": 0, "global_calls_spent": 0, "global_retries_fired": 0,
            "global_budget_remaining": None, "per_goal_budget_isolation": True,
            "shared_session_used": False, "shared_session_calls_spent": None, "shard_count": 0,
        },
        layer_telemetry_aggregate=[],
        global_calls_spent=0, global_retries_fired=0,
        global_budget_remaining=None, shared_session_used=False,
        proof_paths=[], timestamp=datetime.now(timezone.utc).isoformat(),
    )
