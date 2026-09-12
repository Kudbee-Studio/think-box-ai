"""Unit tests for thinkbox/capacity.py — elastic cell expansion."""

import unittest
from thinkbox.capacity import CapacityController


class TestCapacityController(unittest.TestCase):
    def test_expand_on_high_load(self):
        cc = CapacityController(floor=1, ceiling=10)
        decision = cc.evaluate(load=0.95, budget_spend=50, budget_limit=1000)
        self.assertEqual(decision.action, "expand")
        self.assertEqual(cc.current(), 2)

    def test_contract_on_budget_exhausted(self):
        cc = CapacityController(floor=1, ceiling=10)
        cc.evaluate(load=0.95, budget_spend=50, budget_limit=1000)
        decision = cc.evaluate(load=0.9, budget_spend=999, budget_limit=1000)
        self.assertEqual(decision.action, "contract")
        self.assertEqual(cc.current(), 1)

    def test_contract_on_low_load(self):
        cc = CapacityController(floor=1, ceiling=10)
        cc.evaluate(load=0.95, budget_spend=50, budget_limit=1000)
        decision = cc.evaluate(load=0.05, budget_spend=50, budget_limit=1000)
        self.assertEqual(decision.action, "contract")
        self.assertEqual(cc.current(), 1)

    def test_hold_when_stable(self):
        cc = CapacityController(floor=1, ceiling=10)
        decision = cc.evaluate(load=0.5, budget_spend=50, budget_limit=1000)
        self.assertEqual(decision.action, "hold")
        self.assertEqual(cc.current(), 1)

    def test_floor_is_respected(self):
        cc = CapacityController(floor=3, ceiling=10)
        cc.evaluate(load=0.1, budget_spend=0, budget_limit=1000)
        cc.evaluate(load=0.1, budget_spend=0, budget_limit=1000)
        self.assertEqual(cc.current(), 3)

    def test_history(self):
        cc = CapacityController()
        cc.evaluate(load=0.95, budget_spend=10, budget_limit=1000)
        self.assertEqual(len(cc.history()), 1)


if __name__ == "__main__":
    unittest.main()