from __future__ import annotations

import time
import unittest

from agent_features.pr82_heartbeat_rate import TokenBucketRateLimit, WorkerHeartbeat


class TestWorkerHeartbeat(unittest.TestCase):
    def test_register_worker_default(self) -> None:
        wh = WorkerHeartbeat()
        wh.register_worker("w1")
        self.assertIn("w1", wh.get_active_workers())
        self.assertEqual(wh.get_stats()["active_workers"], 1)

    def test_register_worker_with_capabilities(self) -> None:
        wh = WorkerHeartbeat()
        wh.register_worker("w1", ["read", "write"])
        self.assertIn("w1", wh.get_active_workers())

    def test_heartbeat_registered_worker(self) -> None:
        wh = WorkerHeartbeat(heartbeat_timeout_s=10.0)
        wh.register_worker("w1")
        result = wh.heartbeat("w1")
        self.assertTrue(result)

    def test_heartbeat_unknown_worker(self) -> None:
        wh = WorkerHeartbeat()
        result = wh.heartbeat("unknown")
        self.assertFalse(result)

    def test_evict_stale_no_stale_workers(self) -> None:
        wh = WorkerHeartbeat(heartbeat_timeout_s=60.0)
        wh.register_worker("w1")
        evicted = wh.evict_stale()
        self.assertEqual(evicted, [])
        self.assertIn("w1", wh.get_active_workers())

    def test_evict_stale_worker(self) -> None:
        wh = WorkerHeartbeat(heartbeat_timeout_s=0.01)
        wh.register_worker("w1")
        time.sleep(0.02)
        evicted = wh.evict_stale()
        self.assertIn("w1", evicted)
        self.assertNotIn("w1", wh.get_active_workers())

    def test_evict_stale_moves_jobs_to_dlq(self) -> None:
        wh = WorkerHeartbeat(heartbeat_timeout_s=0.01)
        wh.register_worker("w1")
        wh._workers["w1"]["assigned_jobs"] = ["job1", "job2"]
        time.sleep(0.02)
        evicted = wh.evict_stale()
        self.assertIn("w1", evicted)
        dlq = wh.get_dlq()
        self.assertEqual(len(dlq), 2)
        job_ids = [e["job_id"] for e in dlq]
        self.assertIn("job1", job_ids)
        self.assertIn("job2", job_ids)

    def test_evict_stale_preserves_active_workers(self) -> None:
        wh = WorkerHeartbeat(heartbeat_timeout_s=1.0)
        wh.register_worker("w1")
        wh.register_worker("w2")
        wh._workers["w1"]["last_heartbeat"] = "2020-01-01T00:00:00+00:00"
        time.sleep(0.01)
        evicted = wh.evict_stale()
        self.assertIn("w1", evicted)
        self.assertIn("w2", wh.get_active_workers())

    def test_move_to_dlq(self) -> None:
        wh = WorkerHeartbeat()
        entry = wh.move_to_dlq("job1", reason="test failure")
        self.assertEqual(entry["job_id"], "job1")
        self.assertEqual(entry["reason"], "test failure")
        self.assertIn("timestamp", entry)
        dlq = wh.get_dlq()
        self.assertEqual(len(dlq), 1)
        self.assertEqual(dlq[0]["job_id"], "job1")

    def test_get_dlq_returns_copy(self) -> None:
        wh = WorkerHeartbeat()
        wh.move_to_dlq("job1", reason="r1")
        wh.move_to_dlq("job2", reason="r2")
        dlq = wh.get_dlq()
        dlq.clear()
        self.assertEqual(len(wh.get_dlq()), 2)

    def test_get_active_workers_returns_list(self) -> None:
        wh = WorkerHeartbeat()
        wh.register_worker("w1")
        wh.register_worker("w2")
        workers = wh.get_active_workers()
        self.assertEqual(len(workers), 2)
        self.assertIn("w1", workers)
        self.assertIn("w2", workers)

    def test_get_stats(self) -> None:
        wh = WorkerHeartbeat(heartbeat_timeout_s=15.0)
        wh.register_worker("w1")
        wh.register_worker("w2")
        wh.move_to_dlq("job1", reason="r")
        stats = wh.get_stats()
        self.assertEqual(stats["active_workers"], 2)
        self.assertEqual(stats["dlq_size"], 1)
        self.assertEqual(stats["heartbeat_timeout_s"], 15.0)

    def test_empty_initial_state(self) -> None:
        wh = WorkerHeartbeat()
        self.assertEqual(wh.get_active_workers(), [])
        self.assertEqual(wh.get_dlq(), [])
        stats = wh.get_stats()
        self.assertEqual(stats["active_workers"], 0)
        self.assertEqual(stats["dlq_size"], 0)

    def test_multiple_evictions(self) -> None:
        wh = WorkerHeartbeat(heartbeat_timeout_s=0.01)
        wh.register_worker("w1")
        wh.register_worker("w2")
        wh.register_worker("w3")
        for w in ["w1", "w2", "w3"]:
            wh._workers[w]["last_heartbeat"] = "2020-01-01T00:00:00+00:00"
        time.sleep(0.02)
        evicted = wh.evict_stale()
        self.assertEqual(sorted(evicted), ["w1", "w2", "w3"])
        self.assertEqual(wh.get_active_workers(), [])


class TestTokenBucketRateLimit(unittest.TestCase):
    def test_consume_allowed_default(self) -> None:
        tb = TokenBucketRateLimit(capacity=10, refill_rate=1.0)
        tb.set_tenant("t1")
        allowed, reason, event = tb.consume("t1", tokens=3)
        self.assertTrue(allowed)
        self.assertEqual(reason, "ok")
        self.assertTrue(event["allowed"])
        self.assertEqual(event["tokens_deducted"], 3)

    def test_consume_denied_insufficient_tokens(self) -> None:
        tb = TokenBucketRateLimit(capacity=2, refill_rate=0.0)
        tb.set_tenant("t1")
        allowed, reason, event = tb.consume("t1", tokens=3)
        self.assertFalse(allowed)
        self.assertEqual(reason, "insufficient tokens")
        self.assertFalse(event["allowed"])
        self.assertEqual(event["tokens_deducted"], 0)

    def test_consume_unknown_tenant(self) -> None:
        tb = TokenBucketRateLimit()
        allowed, reason, event = tb.consume("unknown", tokens=1)
        self.assertFalse(allowed)
        self.assertEqual(reason, "tenant not registered")
        self.assertFalse(event["allowed"])

    def test_consume_invalid_token_count_zero(self) -> None:
        tb = TokenBucketRateLimit()
        tb.set_tenant("t1")
        allowed, reason, _ = tb.consume("t1", tokens=0)
        self.assertFalse(allowed)
        self.assertEqual(reason, "invalid token count")

    def test_consume_invalid_token_count_negative(self) -> None:
        tb = TokenBucketRateLimit()
        tb.set_tenant("t1")
        allowed, reason, _ = tb.consume("t1", tokens=-1)
        self.assertFalse(allowed)
        self.assertEqual(reason, "invalid token count")

    def test_set_tenant_custom_capacity_and_rate(self) -> None:
        tb = TokenBucketRateLimit()
        tb.set_tenant("t1", capacity=100, refill_rate=5.0)
        self.assertEqual(tb.get_balance("t1"), 100.0)

    def test_set_tenant_default_capacity_and_rate(self) -> None:
        tb = TokenBucketRateLimit(capacity=50, refill_rate=2.0)
        tb.set_tenant("t1")
        self.assertEqual(tb.get_balance("t1"), 50.0)

    def test_set_tenant_partial_override(self) -> None:
        tb = TokenBucketRateLimit(capacity=10, refill_rate=1.0)
        tb.set_tenant("t1", capacity=20)
        self.assertEqual(tb.get_balance("t1"), 20.0)
        tb.set_tenant("t2", refill_rate=2.0)
        self.assertEqual(tb.get_balance("t2"), 10.0)

    def test_get_balance_unknown_tenant(self) -> None:
        tb = TokenBucketRateLimit()
        self.assertEqual(tb.get_balance("unknown"), 0.0)

    def test_refill_increases_tokens(self) -> None:
        tb = TokenBucketRateLimit(capacity=10, refill_rate=1.0)
        tb.set_tenant("t1")
        tb.consume("t1", tokens=5)
        balance_before = tb.get_balance("t1")
        time.sleep(1.1)
        tb.refill()
        balance_after = tb.get_balance("t1")
        self.assertGreater(balance_after, balance_before)
        self.assertLessEqual(balance_after, 10.0)

    def test_refill_caps_at_capacity(self) -> None:
        tb = TokenBucketRateLimit(capacity=5, refill_rate=10.0)
        tb.set_tenant("t1")
        tb.consume("t1", tokens=5)
        time.sleep(1.0)
        tb.refill()
        balance = tb.get_balance("t1")
        self.assertLessEqual(balance, 5.0)

    def test_consume_then_refill_then_consume(self) -> None:
        tb = TokenBucketRateLimit(capacity=5, refill_rate=2.0)
        tb.set_tenant("t1")
        allowed1, _, _ = tb.consume("t1", tokens=5)
        self.assertTrue(allowed1)
        allowed2, _, _ = tb.consume("t1", tokens=3)
        self.assertFalse(allowed2)
        time.sleep(2.0)
        tb.refill()
        allowed3, _, _ = tb.consume("t1", tokens=3)
        self.assertTrue(allowed3)

    def test_get_stats(self) -> None:
        tb = TokenBucketRateLimit(capacity=10, refill_rate=1.0)
        tb.set_tenant("t1")
        tb.set_tenant("t2", capacity=20)
        stats = tb.get_stats()
        self.assertEqual(stats["tenant_count"], 2)
        self.assertEqual(stats["default_capacity"], 10)
        self.assertEqual(stats["default_refill_rate"], 1.0)
        self.assertEqual(stats["total_capacity"], 30)

    def test_get_balance_after_consumes(self) -> None:
        tb = TokenBucketRateLimit(capacity=10, refill_rate=100.0)
        tb.set_tenant("t1")
        _, _, _ = tb.consume("t1", tokens=3)
        balance = tb.get_balance("t1")
        self.assertAlmostEqual(balance, 7.0, delta=0.1)

    def test_consume_exact_balance(self) -> None:
        tb = TokenBucketRateLimit(capacity=5, refill_rate=0.0)
        tb.set_tenant("t1")
        allowed, _, _ = tb.consume("t1", tokens=5)
        self.assertTrue(allowed)
        allowed2, _, _ = tb.consume("t1", tokens=1)
        self.assertFalse(allowed2)

    def test_multiple_tenants_independent(self) -> None:
        tb = TokenBucketRateLimit(capacity=10, refill_rate=0.0)
        tb.set_tenant("t1")
        tb.set_tenant("t2")
        _, _, _ = tb.consume("t1", tokens=8)
        _, _, _ = tb.consume("t2", tokens=3)
        self.assertAlmostEqual(tb.get_balance("t1"), 2.0, delta=0.01)
        self.assertAlmostEqual(tb.get_balance("t2"), 7.0, delta=0.01)

    def test_default_constructor_values(self) -> None:
        tb = TokenBucketRateLimit()
        self.assertEqual(tb._default_capacity, 10)
        self.assertEqual(tb._default_refill_rate, 1.0)
        tb.set_tenant("t1")
        self.assertAlmostEqual(tb.get_balance("t1"), 10.0, delta=0.01)


if __name__ == "__main__":
    unittest.main()
