"""Deterministic tests for the Think Box sharding layer (``thinkbox/shard.py``).

Every test is hermetic: no network, no provider SDK, no real model. The
end-to-end tests drive the real :mod:`thinkbox.concurrent_goals` engine through
a fake ``complete_async`` backed by the v2 deterministic spec tables in
:mod:`thinkbox.pop_arena`, so outcomes are reproducible from the spec tables
alone.
"""

import asyncio
import json
import os
import re
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone

from thinkbox.concurrent_goals import (
    BudgetContentionPolicy,
    ConcurrentGoalSpec,
    ConcurrentGoalsConfig,
    ConcurrentGoalsResult,
    ConcurrentGoalsRunner,
)
from thinkbox.pop_arena import (
    BudgetExhausted,
    V2_COMPUTE_SPECS,
    _compute_expected,
    extract_json,
    system_prompt_for_v2,
    verify_v2,
)
from thinkbox.shard import (
    ArenaRetryScaleVerification,
    BackpressureSignal,
    Shard,
    ShardAdmissionController,
    ShardAssignment,
    ShardBackpressureController,
    ShardCheckpoint,
    ShardCheckpointStore,
    ShardFailureDetector,
    ShardLedgerEvent,
    ShardLedgerWriter,
    ShardRebalancer,
    ShardRecovery,
    ShardReplay,
    ShardState,
    ShardedBudgetManager,
    ShardedGoalExecutor,
    ShardedRunSummary,
    ShardTelemetryAggregator,
    RendezvousHasher,
)

FAMILY_VARIANTS = list(V2_COMPUTE_SPECS.keys())


def _compute_spec(variant: str):
    p, s = system_prompt_for_v2("compute", variant)
    return {"description": p, "family": "compute", "spec": s}


def _multifield_spec(variant: str):
    p, s = system_prompt_for_v2("multifield", variant)
    return {"description": p, "family": "multifield", "spec": s}


def _distractor_spec(variant: str):
    p, s = system_prompt_for_v2("distractor", variant)
    return {"description": p, "family": "distractor", "spec": s}


def _make_compute_spec(name: str, variant: str = "add_small") -> ConcurrentGoalSpec:
    return ConcurrentGoalSpec(goal=name, subtasks=[_compute_spec(variant)])


def _make_runner() -> ConcurrentGoalsRunner:
    return ConcurrentGoalsRunner(
        enable_deadlines=False,
        enable_starvation_detection=False,
        enable_priority_inversion_detection=False,
        enable_failure_isolation=False,
        enable_provenance_tracking=False,
    )


async def deterministic_complete(prompt: str) -> str:
    """Fake model that returns a v2-valid response by parsing the prompt.

    Handles compute (``Compute a op b``) and multifield (``For the number N``)
    and distractor (``{ "answer": N }`` target) prompts. Pure: no network.
    """
    m = re.search(r"Compute (\d+) ([+\-×]) (\d+)", prompt)
    if m:
        a, sym, b = int(m.group(1)), m.group(2), int(m.group(3))
        op = {"+": "add", "-": "sub", "×": "mul"}[sym]
        return json.dumps({"answer": _compute_expected((a, b, op))})
    m = re.search(r"For the number (\-?\d+)", prompt)
    if m:
        n = int(m.group(1))
        parity = "even" if n % 2 == 0 else "odd"
        return json.dumps({"answer": n, "parity": parity, "double": 2 * n})
    m = re.search(r'\{"answer": (\-?\d+)\}', prompt)
    if m:
        n = int(m.group(1))
        return json.dumps({"answer": n})
    return json.dumps({"answer": 0})


def make_wrongkey_recover_complete(first_key: str = "result"):
    """Stateful fake: odd attempts emit a wrong key (retryable), even attempts
    emit the valid ``answer``. Counter is per-instance so multi-goal tests
    remain deterministic."""
    state = {"attempts": 0}

    async def complete(prompt: str) -> str:
        state["attempts"] += 1
        m = re.search(r'\{"answer": (\-?\d+)\}', prompt)
        n = int(m.group(1)) if m else 0
        if state["attempts"] % 2 == 1:
            bad = {first_key: n}
            return json.dumps(bad)
        return json.dumps({"answer": n})

    return complete


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestRendezvousHasher(unittest.TestCase):
    def test_assign_returns_valid_index(self):
        h = RendezvousHasher(["s0", "s1", "s2"])
        for key in ("goal-a", "goal-b", "goal-999"):
            self.assertIn(h.assign(key), range(3))

    def test_assign_deterministic_for_same_key(self):
        h = RendezvousHasher(["s0", "s1", "s2", "s3"])
        self.assertEqual(h.assign("fixed-key"), h.assign("fixed-key"))

    def test_assign_different_keys_spread(self):
        h = RendezvousHasher([f"s{i}" for i in range(8)])
        buckets = h.distribution([f"goal-{i}" for i in range(80)])
        # With 8 buckets and rendezvous hashing, no single bucket should hoard
        # all keys (a degenerate assignment would indicate a hash bug).
        counts = [len(v) for v in buckets.values()]
        self.assertEqual(len(counts), 8)
        self.assertLess(max(counts) - min(counts), max(counts))

    def test_node_for_returns_existing_node(self):
        nodes = ["s0", "s1", "s2"]
        h = RendezvousHasher(nodes)
        for key in ("a", "b", "c"):
            self.assertIn(h.node_for(key), nodes)

    def test_empty_nodes_raises(self):
        with self.assertRaises(ValueError):
            RendezvousHasher().assign("anything")

    def test_distribution_groups_correctly(self):
        h = RendezvousHasher(["s0", "s1"])
        dist = h.distribution(["a", "b", "c", "d"])
        all_keys = [k for ks in dist.values() for k in ks]
        self.assertEqual(sorted(all_keys), ["a", "b", "c", "d"])

    def test_weight_is_stable(self):
        h = RendezvousHasher(["s0", "s1"])
        self.assertEqual(h.weight("k", "s0"), h.weight("k", "s0"))


class TestShard(unittest.TestCase):
    def test_shard_identity(self):
        s = Shard(shard_id="shard-001", node_index=1)
        self.assertEqual(s.shard_id, "shard-001")
        self.assertEqual(s.node_index, 1)

    def test_shard_state_values(self):
        self.assertEqual(ShardState.ACTIVE.value, "active")
        self.assertEqual(ShardState.ISOLATED.value, "isolated")


class TestShardAssignment(unittest.TestCase):
    def setUp(self):
        self.hasher = RendezvousHasher(["s0", "s1", "s2"])
        self.specs = [ConcurrentGoalSpec(goal=f"g{i}", subtasks=[]) for i in range(6)]
        self.assignment = ShardAssignment(self.hasher, self.specs)

    def test_groups_goals_by_shard(self):
        total = sum(len(v) for v in self.assignment.by_shard.values())
        self.assertEqual(total, 6)

    def test_for_shard_returns_list(self):
        for sid in self.hasher.nodes:
            self.assertIsInstance(self.assignment.for_shard(sid), list)

    def test_for_shard_unknown_returns_empty(self):
        self.assertEqual(self.assignment.for_shard("nope"), [])

    def test_total_goals(self):
        self.assertEqual(self.assignment.total_goals, 6)

    def test_active_shards_excludes_empty(self):
        active = self.assignment.active_shards
        self.assertTrue(set(active).issubset(set(self.hasher.nodes)))
        for sid in active:
            self.assertEqual(len(self.assignment.for_shard(sid)), len(self.assignment.by_shard[sid]))

    def test_balance_counts_sum(self):
        counts = self.assignment.balance()
        self.assertEqual(sum(counts.values()), 6)


class TestShardedBudgetManager(unittest.TestCase):
    def test_initial_slice_distribution(self):
        bm = ShardedBudgetManager(total_calls=10, num_shards=4)
        # 10 = 2 + 2 + 3 + 3 (floor 2, remainder 2 to first two)
        slices = sorted(bm.slice_for(s) for s in bm.shard_ids)
        self.assertEqual(slices, [2, 2, 3, 3])

    def test_reserve_success(self):
        bm = ShardedBudgetManager(total_calls=10, num_shards=2)
        sid = bm.shard_ids[0]
        self.assertTrue(bm.reserve(sid, 3))
        self.assertEqual(bm.remaining_for(sid), bm.slice_for(sid) - 3)

    def test_reserve_exceeds_slice_rejected(self):
        bm = ShardedBudgetManager(total_calls=4, num_shards=2)
        sid = bm.shard_ids[0]
        self.assertFalse(bm.reserve(sid, 10))

    def test_release_and_reserve_again(self):
        bm = ShardedBudgetManager(total_calls=10, num_shards=2)
        sid = bm.shard_ids[0]
        self.assertTrue(bm.reserve(sid, 5))
        self.assertFalse(bm.reserve(sid, 1))  # slice is exactly 5
        bm.release(sid, 2)
        self.assertTrue(bm.reserve(sid, 2))

    def test_remaining_global(self):
        bm = ShardedBudgetManager(total_calls=10, num_shards=2)
        self.assertEqual(bm.remaining(), 10)
        bm.spend(bm.shard_ids[0], 4)
        self.assertEqual(bm.remaining(), 6)

    def test_remaining_for_shard(self):
        bm = ShardedBudgetManager(total_calls=8, num_shards=2)
        self.assertEqual(bm.remaining_for(bm.shard_ids[0]), 4)
        bm.spend(bm.shard_ids[0], 1)
        self.assertEqual(bm.remaining_for(bm.shard_ids[0]), 3)

    def test_reallocate_surplus(self):
        bm = ShardedBudgetManager(total_calls=10, num_shards=2)
        a, b = bm.shard_ids[0], bm.shard_ids[1]
        bm.spend(a, 1)  # a alloc 5, spent 1, surplus 4
        self.assertTrue(bm.reallocate(a, b, 2))
        # a: alloc 5-2=3, spent 1 -> remaining 2 ; b: alloc 5+2=7, spent 0 -> 7
        self.assertEqual(bm.remaining_for(a), 2)
        self.assertEqual(bm.remaining_for(b), 7)
        self.assertEqual(bm.redistributed(), 2)
        self.assertEqual(bm.total_spent(), 1)

    def test_reallocate_too_much_rejected(self):
        bm = ShardedBudgetManager(total_calls=10, num_shards=2)
        a, b = bm.shard_ids[0], bm.shard_ids[1]
        bm.spend(a, 5)  # a has 0 surplus (slice exactly exhausted)
        self.assertFalse(bm.reallocate(a, b, 1))

    def test_reallocate_never_overspends_global(self):
        bm = ShardedBudgetManager(total_calls=10, num_shards=2)
        a, b = bm.shard_ids[0], bm.shard_ids[1]
        bm.spend(a, 3)  # a slice 5, surplus 2
        self.assertTrue(bm.reallocate(a, b, 2))
        self.assertLessEqual(bm.total_spent(), 10)
        self.assertGreaterEqual(bm.remaining(), 0)

    def test_spend_raises_budget_exhausted(self):
        bm = ShardedBudgetManager(total_calls=2, num_shards=1)
        with self.assertRaises(BudgetExhausted):
            bm.spend(bm.shard_ids[0], 3)

    def test_invalid_args(self):
        with self.assertRaises(ValueError):
            ShardedBudgetManager(total_calls=10, num_shards=0)
        with self.assertRaises(ValueError):
            ShardedBudgetManager(total_calls=-1, num_shards=2)

    def test_total_spent_sum(self):
        bm = ShardedBudgetManager(total_calls=12, num_shards=3)
        bm.spend(bm.shard_ids[0], 2)
        bm.spend(bm.shard_ids[1], 3)
        self.assertEqual(bm.total_spent(), 5)


class TestShardFailureDetector(unittest.TestCase):
    def test_record_success_observations(self):
        d = ShardFailureDetector()
        d.record_success("s0")
        self.assertEqual(d.observations("s0"), 1)
        self.assertEqual(d.failure_rate("s0"), 0.0)

    def test_record_failure_observations(self):
        d = ShardFailureDetector(min_observations=1)
        d.record_failure("s0")
        self.assertEqual(d.observations("s0"), 1)
        self.assertEqual(d.failures("s0"), 1)
        self.assertEqual(d.failure_rate("s0"), 1.0)

    def test_failure_rate_below_threshold(self):
        d = ShardFailureDetector(failure_threshold=0.5, min_observations=4)
        for _ in range(3):
            d.record_success("s0")
        d.record_failure("s0")  # 1/4 = 0.25 < 0.5
        self.assertFalse(d.should_isolate("s0"))

    def test_failure_rate_triggers_isolation(self):
        d = ShardFailureDetector(failure_threshold=0.5, min_observations=2)
        d.record_failure("s0")
        d.record_failure("s0")  # 2/2 = 1.0 >= 0.5, obs >= 2
        self.assertTrue(d.should_isolate("s0"))

    def test_min_observations_gate(self):
        d = ShardFailureDetector(failure_threshold=0.0, min_observations=5)
        d.record_failure("s0")
        self.assertFalse(d.should_isolate("s0"))  # needs 5 observations

    def test_clear_resets_state(self):
        d = ShardFailureDetector(failure_threshold=0.5, min_observations=1)
        d.record_failure("s0")
        self.assertTrue(d.should_isolate("s0"))
        d.clear("s0")
        self.assertFalse(d.is_isolated("s0"))
        self.assertEqual(d.observations("s0"), 0)

    def test_threshold_out_of_range(self):
        with self.assertRaises(ValueError):
            ShardFailureDetector(failure_threshold=1.5)


class TestShardRebalancer(unittest.TestCase):
    def test_rebalance_no_isolated_returns_same_membership(self):
        h = RendezvousHasher(["s0", "s1", "s2", "s3"])
        specs = [ConcurrentGoalSpec(goal=f"g{i}", subtasks=[]) for i in range(8)]
        assignment = ShardAssignment(h, specs)
        rebalancer = ShardRebalancer(h)
        new_assignment = rebalancer.rebalance(assignment, set())
        # goal set preserved
        before = {s.goal for s in specs}
        after = {s.goal for s in sum(new_assignment.by_shard.values(), [])}
        self.assertEqual(before, after)

    def test_rebalance_moves_isolated_goals(self):
        h = RendezvousHasher(["s0", "s1", "s2"])
        specs = [ConcurrentGoalSpec(goal=f"g{i}", subtasks=[]) for i in range(9)]
        assignment = ShardAssignment(h, specs)
        isolated = {assignment.shard_ids[0]}
        rebalancer = ShardRebalancer(h)
        new_assignment = rebalancer.rebalance(assignment, isolated)
        self.assertEqual(new_assignment.for_shard(isolated.pop()), [])
        total = sum(len(v) for v in new_assignment.by_shard.values())
        self.assertEqual(total, 9)

    def test_rebalance_does_not_remap_healthy(self):
        h = RendezvousHasher(["s0", "s1"])
        specs = [ConcurrentGoalSpec(goal=f"g{i}", subtasks=[]) for i in range(4)]
        assignment = ShardAssignment(h, specs)
        healthy = set(h.nodes)
        new_assignment = ShardRebalancer(h).rebalance(assignment, set())
        for sid in healthy:
            self.assertEqual(
                sorted(s.goal for s in new_assignment.for_shard(sid)),
                sorted(s.goal for s in assignment.for_shard(sid)),
            )


class TestShardRecovery(unittest.TestCase):
    def test_recover_non_isolated_returns_true(self):
        d = ShardFailureDetector()
        self.assertTrue(ShardRecovery().recover(d, "s0", []))

    def test_recover_isolated_unstable_keeps_isolated(self):
        d = ShardFailureDetector(failure_threshold=0.5, min_observations=1)
        d.record_failure("s0")
        self.assertTrue(d.should_isolate("s0"))
        d.isolate("s0")
        self.assertFalse(ShardRecovery().recover(d, "s0", []))
        self.assertTrue(d.is_isolated("s0"))

    def test_recover_stable_clears(self):
        d = ShardFailureDetector(failure_threshold=0.5, min_observations=3)
        for _ in range(3):
            d.record_success("s0")  # failure_rate 0 after 3 obs
        self.assertTrue(d.should_isolate("s0") is False)
        # force isolation then recover
        d.isolate("s0")
        self.assertTrue(d.is_isolated("s0"))
        self.assertTrue(ShardRecovery().recover(d, "s0", []))


class _ResultBuilder:
    """Helper to fabricate ConcurrentGoalsResult values for aggregation tests."""

    @staticmethod
    def build(name, calls, retries, verified_rate=1.0, layer=None, shared=False):
        per_goal = {
            name: {
                "calls_spent": calls,
                "retries_fired": retries,
                "budget_remaining": None,
                "execution_status": "verified",
                "tasks": 1,
                "first_try_successes": 1 if calls == 1 else 0,
                "recovered_successes": 1 if retries else 0,
                "failures": 0,
                "budget_exhausted": 0,
                "verification_rate": verified_rate,
            }
        }
        return ConcurrentGoalsResult(
            goal_results={name: {"verified": {}, "_goal_calls": calls}},
            per_goal_accounting=per_goal,
            cross_goal_summary={
                "total_goals": 1,
                "global_calls_spent": calls,
                "global_retries_fired": retries,
                "global_budget_remaining": None,
                "per_goal_budget_isolation": True,
                "shared_session_used": shared,
                "shared_session_calls_spent": calls if shared else None,
            },
            layer_telemetry_aggregate=[layer] if layer else [
                {"layer_index": 0, "tasks": 1, "first_try_successes": 1,
                 "recovered_successes": 0, "failures": 0, "budget_exhausted": 0,
                 "retries": 0, "verification_rate": verified_rate}
            ],
            global_calls_spent=calls,
            global_retries_fired=retries,
            global_budget_remaining=None,
            shared_session_used=shared,
            proof_paths=[],
            timestamp="",
        )


class TestShardTelemetryAggregator(unittest.TestCase):
    def test_aggregate_merges_goal_results(self):
        a = _ResultBuilder.build("g0", 1, 0)
        b = _ResultBuilder.build("g1", 1, 0)
        merged = ShardTelemetryAggregator.aggregate([a, b])
        self.assertEqual(set(merged.goal_results.keys()), {"g0", "g1"})

    def test_aggregate_sums_global_calls(self):
        a = _ResultBuilder.build("g0", 1, 0)
        b = _ResultBuilder.build("g1", 2, 1)
        merged = ShardTelemetryAggregator.aggregate([a, b])
        self.assertEqual(merged.global_calls_spent, 3)
        self.assertEqual(merged.global_retries_fired, 1)

    def test_aggregate_flattens_layer_telemetry(self):
        a = _ResultBuilder.build("g0", 1, 0, layer={"layer_index": 0, "tasks": 1,
            "first_try_successes": 1, "recovered_successes": 0, "failures": 0,
            "budget_exhausted": 0, "retries": 0, "verification_rate": 1.0})
        b = _ResultBuilder.build("g1", 1, 0, layer={"layer_index": 0, "tasks": 1,
            "first_try_successes": 0, "recovered_successes": 1, "failures": 0,
            "budget_exhausted": 0, "retries": 1, "verification_rate": 0.0})
        merged = ShardTelemetryAggregator.aggregate([a, b])
        self.assertEqual(len(merged.layer_telemetry_aggregate), 1)
        agg_layer = merged.layer_telemetry_aggregate[0]
        self.assertEqual(agg_layer["tasks"], 2)
        self.assertEqual(agg_layer["first_try_successes"], 1)
        self.assertEqual(agg_layer["recovered_successes"], 1)

    def test_aggregate_cross_check_ok(self):
        a = _ResultBuilder.build("g0", 3, 0)  # per_goal calls=3 == global 3
        merged = ShardTelemetryAggregator.aggregate([a])
        self.assertEqual(merged.global_calls_spent, 3)

    def test_aggregate_cross_check_mismatch_raises(self):
        bad = ConcurrentGoalsResult(
            goal_results={"g0": {}},
            per_goal_accounting={"g0": {"calls_spent": 2}},
            cross_goal_summary={},
            layer_telemetry_aggregate=[],
            global_calls_spent=5,  # 2 != 5 -> mismatch
            global_retries_fired=0,
            global_budget_remaining=None,
            shared_session_used=False,
            proof_paths=[],
            timestamp="",
        )
        with self.assertRaises(AssertionError):
            ShardTelemetryAggregator.aggregate([bad])

    def test_aggregate_shared_session_any_true(self):
        a = _ResultBuilder.build("g0", 1, 0, shared=True)
        b = _ResultBuilder.build("g1", 1, 0, shared=False)
        merged = ShardTelemetryAggregator.aggregate([a, b])
        self.assertTrue(merged.shared_session_used)


class TestShardBackpressureController(unittest.TestCase):
    def test_admit_under_limits(self):
        ctrl = ShardBackpressureController(max_queue_depth=10, max_latency_ms=100)
        signal = ctrl.should_admit("s0")
        self.assertTrue(signal.admitted)
        self.assertEqual(signal.queue_depth, 0)

    def test_reject_queue_full(self):
        ctrl = ShardBackpressureController(max_queue_depth=2, max_latency_ms=1000)
        ctrl.observe("s0", 1.0, enqueued=True)
        ctrl.observe("s0", 1.0, enqueued=True)
        ctrl.observe("s0", 1.0, enqueued=True)
        signal = ctrl.should_admit("s0")
        self.assertFalse(signal.admitted)
        self.assertEqual(signal.reason, "queue_full")

    def test_reject_latency_exceeded(self):
        ctrl = ShardBackpressureController(max_queue_depth=100, max_latency_ms=10)
        ctrl.observe("s0", 50.0)
        signal = ctrl.should_admit("s0")
        self.assertFalse(signal.admitted)
        self.assertEqual(signal.reason, "latency_exceeded")

    def test_drain_reduces_depth(self):
        ctrl = ShardBackpressureController(max_queue_depth=5, max_latency_ms=1000)
        ctrl.observe("s0", 1.0, enqueued=True)
        ctrl.observe("s0", 1.0, enqueued=True)
        ctrl.drain("s0")
        self.assertEqual(ctrl.should_admit("s0").queue_depth, 1)

    def test_backpressure_signal_fields(self):
        sig = BackpressureSignal(shard_id="s", admitted=False, queue_depth=1, latency_ms=2.0, reason="x")
        self.assertEqual(sig.shard_id, "s")
        self.assertFalse(sig.admitted)


class TestShardAdmissionController(unittest.TestCase):
    def setUp(self):
        self.bm = ShardedBudgetManager(total_calls=10, num_shards=2)
        self.ac = ShardAdmissionController(self.bm)
        self.sid = self.bm.shard_ids[0]

    def test_request_reserves(self):
        self.assertEqual(self.ac.request(self.sid, 3), 3)
        self.assertEqual(self.ac.reserved(self.sid), 3)

    def test_request_exceeds_slice_raises_budget_exhausted(self):
        with self.assertRaises(BudgetExhausted):
            self.ac.request(self.sid, 100)

    def test_release_frees(self):
        self.ac.request(self.sid, 3)
        self.ac.release(self.sid, 2)
        self.assertEqual(self.ac.reserved(self.sid), 1)

    def test_request_then_release_allows_oversubscribed(self):
        self.ac.request(self.sid, 5)
        with self.assertRaises(BudgetExhausted):
            self.ac.request(self.sid, 1)
        self.ac.release(self.sid, 2)
        self.ac.request(self.sid, 2)  # now within slice
        self.assertEqual(self.ac.reserved(self.sid), 5)

    def test_release_never_negative_reserved(self):
        self.ac.request(self.sid, 1)
        self.ac.release(self.sid, 5)
        self.assertEqual(self.ac.reserved(self.sid), 0)


class TestShardLedgerWriter(unittest.TestCase):
    def _writer(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        return ShardLedgerWriter(db_path=path), path

    def test_append_returns_signed_event(self):
        writer, _ = self._writer()
        evt = writer.append(ShardLedgerEvent("s0", "started", "g0", "running"))
        self.assertTrue(evt.entry_hash)
        self.assertEqual(evt.prev_hash, "")
        writer.close()

    def test_hash_chain_links(self):
        writer, _ = self._writer()
        e1 = writer.append(ShardLedgerEvent("s0", "started", "g0", "running"))
        e2 = writer.append(ShardLedgerEvent("s0", "task", "g0", "done"))
        self.assertEqual(e2.prev_hash, e1.entry_hash)
        writer.close()

    def test_verify_clean_chain(self):
        writer, _ = self._writer()
        for i in range(5):
            writer.append(ShardLedgerEvent("s0", "task", f"g{i}", "done"))
        ok, count, bad = writer.verify()
        self.assertTrue(ok)
        self.assertEqual(count, 5)
        self.assertIsNone(bad)
        writer.close()

    def test_verify_detects_tamper(self):
        writer, path = self._writer()
        for i in range(3):
            writer.append(ShardLedgerEvent("s0", "task", f"g{i}", "done"))
        conn = sqlite3.connect(path)
        conn.execute("UPDATE shard_ledger SET entry_hash='tampered' WHERE seq=2")
        conn.commit()
        conn.close()
        ok, count, bad = writer.verify()
        self.assertFalse(ok)
        self.assertEqual(bad, 2)
        writer.close()

    def test_events_roundtrip(self):
        writer, _ = self._writer()
        writer.append(ShardLedgerEvent("s0", "started", "g0", "running", metadata={"k": "v"}))
        writer.append(ShardLedgerEvent("s1", "done", "g1", "completed"))
        events = writer.events()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].shard_id, "s0")
        self.assertEqual(events[0].metadata, {"k": "v"})
        self.assertEqual(events[1].goal_id, "g1")
        writer.close()

    def test_events_empty_when_no_rows(self):
        writer, _ = self._writer()
        self.assertEqual(writer.events(), [])
        ok, count, _ = writer.verify()
        self.assertTrue(ok)
        self.assertEqual(count, 0)
        writer.close()

    def test_metadata_serialized_as_json(self):
        writer, path = self._writer()
        writer.append(ShardLedgerEvent("s0", "task", "g0", "done", metadata={"a": 1, "b": [1, 2]}))
        conn = sqlite3.connect(path)
        row = conn.execute("SELECT metadata FROM shard_ledger WHERE seq=1").fetchone()
        conn.close()
        self.assertEqual(json.loads(row[0]), {"a": 1, "b": [1, 2]})
        writer.close()

    def test_close_does_not_raise(self):
        writer, _ = self._writer()
        writer.append(ShardLedgerEvent("s0", "task", "g0", "done"))
        writer.close()  # should not raise


class TestShardCheckpointStore(unittest.TestCase):
    def _store(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        return ShardCheckpointStore(db_path=path), path

    def test_save_returns_checksum(self):
        store, _ = self._store()
        cp = store.save(ShardCheckpoint("s0", ["g1", "g2"], 5, 1, "active", "2026-01-01T00:00:00+00:00"))
        self.assertTrue(cp.checksum)
        self.assertEqual(cp.goal_ids, ["g1", "g2"])
        store.close()

    def test_load_latest(self):
        store, _ = self._store()
        cp1 = store.save(ShardCheckpoint("s0", ["g1"], 5, 1, "staging", "2026-01-01T00:00:00+00:00"))
        cp2 = store.save(ShardCheckpoint("s0", ["g1", "g2"], 5, 2, "active", "2026-01-01T00:01:00+00:00"))
        loaded = store.load("s0")
        self.assertEqual(loaded.checksum, cp2.checksum)
        self.assertEqual(loaded.goal_ids, ["g1", "g2"])
        store.close()

    def test_load_by_timestamp(self):
        store, _ = self._store()
        store.save(ShardCheckpoint("s0", ["g1"], 5, 1, "staging", "2026-01-01T00:00:00+00:00", checksum="x"))
        store.save(ShardCheckpoint("s0", ["g2"], 5, 2, "active", "2026-01-01T00:01:00+00:00", checksum="y"))
        loaded = store.load("s0", timestamp="2026-01-01T00:00:00+00:00")
        self.assertEqual(loaded.goal_ids, ["g1"])
        store.close()

    def test_load_missing_returns_none(self):
        store, _ = self._store()
        self.assertIsNone(store.load("missing"))
        store.close()

    def test_list_all(self):
        store, _ = self._store()
        store.save(ShardCheckpoint("s0", ["g1"], 5, 1, "active"))
        store.save(ShardCheckpoint("s2", ["g2"], 5, 0, "staging"))
        all_cps = store.list()
        self.assertEqual(len(all_cps), 2)
        store.close()

    def test_verify_checksum_ok(self):
        store, _ = self._store()
        store.save(ShardCheckpoint("s0", ["g1"], 5, 1, "active"))
        self.assertTrue(store.verify("s0"))
        store.close()

    def test_verify_checksum_tamper(self):
        store, path = self._store()
        store.save(ShardCheckpoint("s0", ["g1"], 5, 1, "active"))
        conn = sqlite3.connect(path)
        conn.execute("UPDATE shard_checkpoints SET checksum='deadbeef' WHERE shard_id='s0'")
        conn.commit()
        conn.close()
        self.assertFalse(store.verify("s0"))
        store.close()

    def test_deterministic_checksum(self):
        cp = ShardCheckpoint("s0", ["g1", "g2"], 5, 1, "active")
        self.assertEqual(
            ShardCheckpointStore._compute_checksum(cp),
            ShardCheckpointStore._compute_checksum(cp),
        )

    def test_different_bodies_different_checksum(self):
        cp = ShardCheckpoint("s0", ["g1"], 5, 1, "active")
        cp2 = ShardCheckpoint("s0", ["g2"], 5, 1, "active")
        self.assertNotEqual(
            ShardCheckpointStore._compute_checksum(cp),
            ShardCheckpointStore._compute_checksum(cp2),
        )


class TestShardReplay(unittest.TestCase):
    def test_replay_returns_latest_per_shard(self):
        store = ShardCheckpointStore()
        store.save(ShardCheckpoint("s0", ["g1"], 5, 1, "active", "t1"))
        store.save(ShardCheckpoint("s0", ["g1", "g2"], 5, 2, "active", "t2"))
        store.save(ShardCheckpoint("s1", ["g3"], 5, 0, "staging", "t1"))
        h = RendezvousHasher(["s0", "s1", "s2"])
        replay = ShardReplay(store, h)
        latest, info = replay.replay()
        self.assertEqual(set(latest.keys()), {"s0", "s1"})
        self.assertEqual(latest["s0"].goal_ids, ["g1", "g2"])
        self.assertIn("expected_shards", info)
        self.assertIn("recomputed", info)
        store.close()

    def test_replay_empty_store(self):
        store = ShardCheckpointStore()
        h = RendezvousHasher(["s0"])
        latest, info = ShardReplay(store, h).replay()
        self.assertEqual(latest, {})
        self.assertEqual(info["expected_shards"], ["s0"])
        store.close()

    def test_replay_detects_drift(self):
        store = ShardCheckpointStore()
        # Assign g1 to whatever the hasher picks; then check info.recomputed
        h = RendezvousHasher(["s0", "s1"])
        store.save(ShardCheckpoint("s0", ["g1"], 5, 0, "staging", "t1"))
        latest, info = ShardReplay(store, h).replay()
        # info.recomputed reflects the CURRENT hasher's assignment of g1
        all_recomputed = [k for v in info["recomputed"].values() for k in v]
        self.assertIn("g1", all_recomputed)
        store.close()


class TestArenaRetryScaleVerification(unittest.TestCase):
    def _result(self, calls, retries=0, recovered=0, be=0, rate=1.0):
        return ConcurrentGoalsResult(
            goal_results={"g0": {}},
            per_goal_accounting={
                "g0": {"calls_spent": calls, "retries_fired": retries,
                        "execution_status": "verified", "first_try_successes": 1 if calls == 1 else 0,
                        "recovered_successes": recovered, "failures": 0, "budget_exhausted": be,
                        "verification_rate": rate}
            },
            cross_goal_summary={},
            layer_telemetry_aggregate=[],
            global_calls_spent=calls,
            global_retries_fired=retries,
            global_budget_remaining=None,
            shared_session_used=False,
            proof_paths=[],
            timestamp="",
        )

    def test_verify_matches_expected(self):
        rep = ArenaRetryScaleVerification.verify(self._result(3), expected_calls=3)
        self.assertTrue(rep.ok)
        self.assertEqual(rep.total_calls, 3)

    def test_verify_mismatch(self):
        rep = ArenaRetryScaleVerification.verify(self._result(5), expected_calls=3)
        self.assertFalse(rep.ok)
        self.assertEqual(rep.total_calls, 5)
        self.assertEqual(rep.expected_calls, 3)

    def test_verify_recovered_and_retries(self):
        rep = ArenaRetryScaleVerification.verify(
            self._result(2, retries=1, recovered=1, rate=1.0), expected_calls=2
        )
        self.assertTrue(rep.ok)
        self.assertEqual(rep.retries, 1)
        self.assertEqual(rep.recovered, 1)

    def test_verify_budget_exhausted_count(self):
        r = ConcurrentGoalsResult(
            goal_results={},
            per_goal_accounting={
                "g0": {"calls_spent": 1, "execution_status": "verified"},
                "g1": {"calls_spent": 0, "execution_status": "verified"},
                "g2": {"calls_spent": 0, "execution_status": "verified"},
            },
            cross_goal_summary={},
            layer_telemetry_aggregate=[],
            global_calls_spent=1,
            global_retries_fired=0,
            global_budget_remaining=None,
            shared_session_used=False,
            proof_paths=[],
            timestamp="",
        )
        # Mark two as exhausted
        r.per_goal_accounting["g1"]["budget_exhausted"] = 1
        r.per_goal_accounting["g2"]["budget_exhausted"] = 1
        rep = ArenaRetryScaleVerification.verify(r, expected_calls=1)
        self.assertEqual(rep.budget_exhausted, 2)


class TestShardedGoalExecutorEndToEnd(unittest.IsolatedAsyncioTestCase):
    async def test_single_shard_compute_first_try(self):
        specs = [_make_compute_spec(f"g{i}") for i in range(3)]
        ex = ShardedGoalExecutor(num_shards=1)
        res = await ex.run_concurrent(specs, deterministic_complete)
        self.assertEqual(res.global_calls_spent, 3)
        self.assertEqual(res.global_retries_fired, 0)
        for ga in res.per_goal_accounting.values():
            self.assertEqual(ga["first_try_successes"], 1)
            self.assertEqual(ga["failures"], 0)

    async def test_multi_shard_deterministic_assignment(self):
        specs = [ConcurrentGoalSpec(goal=f"g{i}", subtasks=[_compute_spec("add_small")]) for i in range(12)]
        ex = ShardedGoalExecutor(num_shards=4)
        res1 = await ex.run_concurrent(specs, deterministic_complete)
        # Same hasher => same assignment; re-run yields equal global accounting
        ex2 = ShardedGoalExecutor(num_shards=4, hasher=ex.hasher)
        res2 = await ex2.run_concurrent(specs, deterministic_complete)
        self.assertEqual(res1.global_calls_spent, res2.global_calls_spent)
        self.assertEqual(res1.global_calls_spent, 12)
        # goals partitioned across shards (not all in one)
        counts = [len(v) for v in ShardAssignment(ex.hasher, specs).by_shard.values()]
        self.assertGreater(max(counts), 0)
        self.assertLess(max(counts), 12)

    async def test_shared_budget_exhaustion(self):
        specs = [_make_compute_spec(f"b_{i}") for i in range(5)]
        ex = ShardedGoalExecutor(num_shards=2)
        cfg = ConcurrentGoalsConfig(max_calls_global=3, independent_goals=False)
        res = await ex.run_concurrent(specs, deterministic_complete, config=cfg)
        self.assertEqual(res.global_calls_spent, 3)
        self.assertTrue(res.shared_session_used)
        be_goals = [g for g, ga in res.per_goal_accounting.items() if ga.get("budget_exhausted") == 1]
        self.assertEqual(len(be_goals), 2)
        ok_goals = [g for g, ga in res.per_goal_accounting.items() if ga.get("first_try_successes") == 1]
        self.assertEqual(len(ok_goals), 3)

    async def test_retry_recovery_per_goal(self):
        p, s = system_prompt_for_v2("distractor", "wrongkey")
        specs = [ConcurrentGoalSpec(goal="d_recover", subtasks=[{"description": p, "family": "distractor", "spec": s}])]
        ex = ShardedGoalExecutor(num_shards=2)
        res = await ex.run_concurrent(specs, make_wrongkey_recover_complete())
        ga = res.per_goal_accounting["d_recover"]
        self.assertEqual(ga["calls_spent"], 2)
        self.assertEqual(ga["retries_fired"], 1)
        self.assertEqual(ga["recovered_successes"], 1)
        self.assertEqual(ga["first_try_successes"], 0)
        self.assertGreater(ga["verification_rate"], 0.0)

    async def test_global_accounting_cross_check(self):
        specs = [_make_compute_spec(f"c{i}") for i in range(6)]
        ex = ShardedGoalExecutor(num_shards=3)
        res = await ex.run_concurrent(specs, deterministic_complete)
        # sum of per-goal spending must equal the global counter
        per_goal_sum = sum(ga["calls_spent"] for ga in res.per_goal_accounting.values())
        self.assertEqual(per_goal_sum, res.global_calls_spent)
        self.assertEqual(res.global_calls_spent, 6)

    async def test_multifield_goal_validates(self):
        specs = [ConcurrentGoalSpec(goal="mf", subtasks=[_multifield_spec("double")])]
        ex = ShardedGoalExecutor(num_shards=1)
        res = await ex.run_concurrent(specs, deterministic_complete)
        ga = res.per_goal_accounting["mf"]
        self.assertEqual(ga["first_try_successes"], 1)
        self.assertEqual(ga["failures"], 0)

    async def test_empty_specs_returns_empty(self):
        ex = ShardedGoalExecutor(num_shards=4)
        res = await ex.run_concurrent([], deterministic_complete)
        self.assertEqual(res.global_calls_spent, 0)
        self.assertEqual(len(res.per_goal_accounting), 0)

    async def test_budget_exhaustion_propagates_exactly(self):
        # budget 1, 4 goals, single shard -> exactly 1 success, 3 exhausted
        specs = [_make_compute_spec(f"e{i}") for i in range(4)]
        ex = ShardedGoalExecutor(num_shards=1)
        cfg = ConcurrentGoalsConfig(max_calls_global=1, independent_goals=False)
        res = await ex.run_concurrent(specs, deterministic_complete, config=cfg)
        self.assertEqual(res.global_calls_spent, 1)
        exhausted = sum(1 for ga in res.per_goal_accounting.values() if ga.get("budget_exhausted") == 1)
        self.assertEqual(exhausted, 3)

    async def test_arena_scale_verification_integration(self):
        specs = [_make_compute_spec(f"k{i}") for i in range(5)]
        ex = ShardedGoalExecutor(num_shards=2)
        res = await ex.run_concurrent(specs, deterministic_complete)
        report = ArenaRetryScaleVerification.verify(res, expected_calls=5)
        self.assertTrue(report.ok)
        self.assertEqual(report.total_calls, 5)


class TestShardedGoalExecutorLedgerAndCheckpoint(unittest.IsolatedAsyncioTestCase):
    async def test_ledger_records_shard_events(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        writer = ShardLedgerWriter(db_path=path)
        try:
            specs = [_make_compute_spec(f"l{i}") for i in range(3)]
            ex = ShardedGoalExecutor(num_shards=2, ledger_writer=writer)
            await ex.run_concurrent(specs, deterministic_complete)
            events = writer.events()
            self.assertTrue(any(e.event_type == "shard_started" for e in events))
            self.assertTrue(any(e.event_type == "shard_finished" for e in events))
            ok, _, _ = writer.verify()
            self.assertTrue(ok)
        finally:
            writer.close()
            os.remove(path)

    async def test_checkpoint_snapshot_persisted(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        store = ShardCheckpointStore(db_path=path)
        try:
            specs = [_make_compute_spec(f"q{i}") for i in range(4)]
            ex = ShardedGoalExecutor(num_shards=2, checkpoint_store=store)
            await ex.run_concurrent(specs, deterministic_complete)
            checkpoints = store.list()
            # staging snapshot + active snapshot per shard with specs
            self.assertGreater(len(checkpoints), 0)
            self.assertTrue(any(c.state == "staging" for c in checkpoints))
        finally:
            store.close()
            os.remove(path)

    async def test_shard_run_summary_from_result(self):
        specs = [_make_compute_spec(f"m{i}") for i in range(4)]
        ex = ShardedGoalExecutor(num_shards=2)
        res = await ex.run_concurrent(specs, deterministic_complete)
        summary = ShardedGoalExecutor.from_result(res, shard_count=2, duration_ms=12.5)
        self.assertEqual(summary.total_goals, 4)
        self.assertEqual(summary.global_calls_spent, 4)
        self.assertEqual(summary.shard_count, 2)
        self.assertEqual(summary.duration_ms, 12.5)
        self.assertEqual(summary.first_try_successes, 4)


if __name__ == "__main__":
    unittest.main()
