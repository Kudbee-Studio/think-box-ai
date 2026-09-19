"""Tests for BudgetBreaker (commit 3: budget breaker)."""

import sys
import types
import unittest
from types import SimpleNamespace

sys.modules["grpc"] = types.ModuleType("grpc")
sys.modules["grpc.aio"] = types.ModuleType("grpc.aio")
sys.modules["google.protobuf"] = types.ModuleType("google.protobuf")

from thinkbox.agent.control_plane.budget import BudgetBreaker, BudgetState


class TestBudgetBreaker(unittest.TestCase):

    def test_initial_state(self):
        bb = BudgetBreaker(limit=100.0)
        self.assertEqual(bb.state.spent, 0.0)
        self.assertFalse(bb.state.trip)
        self.assertEqual(bb.remaining(), 100.0)

    def test_record_spend_within_budget(self):
        bb = BudgetBreaker(limit=100.0)
        result = bb.record_spend(50.0, "agent-1")
        self.assertTrue(result)
        self.assertEqual(bb.state.spent, 50.0)

    def test_record_spend_exceeds_budget_trips(self):
        bb = BudgetBreaker(limit=100.0)
        bb.record_spend(80.0, "agent-1")
        result = bb.record_spend(30.0, "agent-1")
        self.assertFalse(result)
        self.assertTrue(bb.state.trip)

    def test_trip_callback_called(self):
        calls = []
        bb = BudgetBreaker(limit=10.0)
        bb.set_trip_callback(lambda aid, reason: calls.append((aid, reason)))
        bb.record_spend(11.0, "agent-1")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "agent-1")

    def test_can_spend_false_after_trip(self):
        bb = BudgetBreaker(limit=10.0)
        bb.record_spend(11.0, "agent-1")
        self.assertFalse(bb.can_spend(1.0))

    def test_can_spend_true_within_budget(self):
        bb = BudgetBreaker(limit=100.0)
        bb.record_spend(50.0, "agent-1")
        self.assertTrue(bb.can_spend(40.0))
        self.assertFalse(bb.can_spend(60.0))

    def test_remaining_updates(self):
        bb = BudgetBreaker(limit=100.0)
        bb.record_spend(30.0, "a1")
        self.assertAlmostEqual(bb.remaining(), 70.0)

    def test_reset(self):
        bb = BudgetBreaker(limit=100.0)
        bb.record_spend(80.0, "a1")
        bb.state.trip = True  # force trip
        bb.reset()
        self.assertEqual(bb.state.spent, 0.0)
        self.assertFalse(bb.state.trip)


if __name__ == "__main__":
    unittest.main()
