"""Tests for PriorityPreemptor (commit 7: priority lane preemption)."""

import sys
import types
import unittest
from types import SimpleNamespace

sys.modules["grpc"] = types.ModuleType("grpc")
sys.modules["grpc.aio"] = types.ModuleType("grpc.aio")
sys.modules["google.protobuf"] = types.ModuleType("google.protobuf")

from thinkbox.agent.control_plane.preemption import (
    Priority, PriorityPreemptor, PreemptionRecord, WorkItem,
)


class TestPriorityPreemptor(unittest.TestCase):

    def test_submit_dispatch_normal(self):
        pp = PriorityPreemptor()
        pp.submit(WorkItem("t1", Priority.NORMAL))
        item = pp.dispatch()
        self.assertEqual(item.task_id, "t1")

    def test_critical_before_best_effort(self):
        pp = PriorityPreemptor()
        pp.submit(WorkItem("t1", Priority.BEST_EFFORT))
        pp.submit(WorkItem("t2", Priority.CRITICAL))
        item = pp.dispatch()
        self.assertEqual(item.task_id, "t2")

    def test_preempt_best_effort(self):
        pp = PriorityPreemptor()
        pp.submit(WorkItem("t1", Priority.BEST_EFFORT))
        pp.submit(WorkItem("t2", Priority.NORMAL))
        pp.dispatch()  # starts t2 (highest priority)
        pp.preempt("t3-critical", reason="critical task")
        self.assertEqual(pp._active, None)
        self.assertIn("t3-critical", [i.task_id for i in pp.get_queue()])

    def test_no_preempt_critical(self):
        pp = PriorityPreemptor()
        pp.submit(WorkItem("t1", Priority.CRITICAL))
        pp.dispatch()  # starts t1
        result = pp.preempt("t2", reason="try preempt")
        self.assertIsNone(result)

    def test_preemption_log(self):
        pp = PriorityPreemptor()
        pp.submit(WorkItem("t1", Priority.BEST_EFFORT))
        pp.dispatch()
        pp.preempt("t2", reason="test")
        log = pp.preemption_log
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0].preempted_task, "t1")
        self.assertEqual(log[0].preemptor_task, "t2")

    def test_no_preempt_when_idle(self):
        pp = PriorityPreemptor()
        result = pp.preempt("t1", reason="test")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
