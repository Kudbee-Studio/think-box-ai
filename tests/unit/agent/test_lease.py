"""Tests for LeaseManager (commit 6: multi-agent lease/heartbeat)."""

import sys
import types
import unittest
from types import SimpleNamespace

sys.modules["grpc"] = types.ModuleType("grpc")
sys.modules["grpc.aio"] = types.ModuleType("grpc.aio")
sys.modules["google.protobuf"] = types.ModuleType("google.protobuf")

from thinkbox.agent.control_plane.lease import Lease, LeaseManager


class TestLeaseManager(unittest.TestCase):

    def test_acquire_lease(self):
        lm = LeaseManager()
        result = lm.acquire("agent-1", "task-1")
        self.assertTrue(result)
        self.assertIn("task-1", lm.active_leases)

    def test_duplicate_task_lease_rejected(self):
        lm = LeaseManager()
        lm.acquire("agent-1", "task-1")
        result = lm.acquire("agent-2", "task-1")
        self.assertFalse(result)

    def test_release_lease(self):
        lm = LeaseManager()
        lm.acquire("agent-1", "task-1")
        result = lm.release("task-1")
        self.assertTrue(result)
        self.assertNotIn("task-1", lm.active_leases)

    def test_release_missing_lease(self):
        lm = LeaseManager()
        self.assertFalse(lm.release("nonexistent"))

    def test_leader_exclusion(self):
        lm = LeaseManager()
        self.assertTrue(lm.acquire("agent-1", "task-1", leader=True))
        self.assertFalse(lm.acquire("agent-1", "task-2", leader=True))
        self.assertTrue(lm.is_leader("agent-1"))

    def test_dual_leader_prevention(self):
        lm = LeaseManager()
        lm.acquire("agent-1", "t1", leader=True)
        self.assertFalse(lm.acquire("agent-2", "t2", leader=True))
        self.assertEqual(len([a for a in lm._leaders]), 1)

    def test_evict_stale(self):
        lm = LeaseManager()
        lm.acquire("agent-1", "task-1")
        import time
        lease = lm.get_lease("task-1")
        lease.acquired_at = time.time() - 400  # expired
        evicted = lm.evict_stale()
        self.assertIn("task-1", evicted)
        self.assertNotIn("task-1", lm.active_leases)

    def test_agent_tasks(self):
        lm = LeaseManager()
        lm.acquire("agent-1", "task-1")
        lm.acquire("agent-1", "task-2")
        tasks = lm.get_agent_tasks("agent-1")
        self.assertEqual(len(tasks), 2)


if __name__ == "__main__":
    unittest.main()
