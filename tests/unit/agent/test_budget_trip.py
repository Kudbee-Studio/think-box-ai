"""Tests for budget-breaker."""

import json
import unittest
from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.budget_trip import (
    BudgetBreaker,
    BudgetBreakerConfig,
    BUDGET_REASON_CODES,
)


class TestBudgetBreaker(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ActionReceiptStore(":memory:")

    def tearDown(self) -> None:
        self.store.close()

    def test_config_not_exhausted(self) -> None:
        config = BudgetBreakerConfig(max_calls=100, max_spend=10.0)
        self.assertFalse(config.is_exhausted())

    def test_config_calls_exceeded(self) -> None:
        config = BudgetBreakerConfig(max_calls=2, cost_per_call=0.01)
        config.calls = 2
        self.assertTrue(config.is_exhausted())
        self.assertEqual(config.reason_code(), "calls_exceeded")

    def test_config_spend_exceeded(self) -> None:
        config = BudgetBreakerConfig(max_spend=0.01, cost_per_call=0.01)
        config.spend = 0.01
        self.assertTrue(config.is_exhausted())
        self.assertEqual(config.reason_code(), "spend_exceeded")

    def test_config_both_exceeded(self) -> None:
        config = BudgetBreakerConfig(max_calls=1, max_spend=0.01, cost_per_call=0.01)
        config.calls = 1
        config.spend = 0.01
        self.assertTrue(config.is_exhausted())
        self.assertEqual(config.reason_code(), "both_exceeded")

    def test_trip_writes_receipt(self) -> None:
        config = BudgetBreakerConfig(max_calls=1, cost_per_call=0.01)
        config.calls = 1
        config.spend = 0.01
        breaker = BudgetBreaker(self.store, config)
        result = breaker.trip("agent-1")
        self.assertTrue(result["tripped"])
        self.assertEqual(self.store.count(), 1)
        self.assertTrue(self.store.verify())

    def test_trip_reason_code_in_metadata(self) -> None:
        config = BudgetBreakerConfig(max_calls=1, cost_per_call=0.01)
        config.calls = 1
        breaker = BudgetBreaker(self.store, config)
        breaker.trip("agent-1")
        with self.store._lock:
            row = self.store._conn.execute(
                "SELECT metadata FROM receipts"
            ).fetchone()
        self.assertIsNotNone(row)
        meta = json.loads(row[0]) if row[0] else {}
        self.assertEqual(meta["reason_code"], "calls_exceeded")

    def test_not_trip_when_budget_ok(self) -> None:
        config = BudgetBreakerConfig(max_calls=10, max_spend=5.0, cost_per_call=0.01)
        breaker = BudgetBreaker(self.store, config)
        result = breaker.trip("agent-1")
        self.assertFalse(result["tripped"])
        self.assertEqual(self.store.count(), 0)

    def test_charge_increases_spend(self) -> None:
        config = BudgetBreakerConfig(max_calls=10, max_spend=5.0, cost_per_call=0.01)
        breaker = BudgetBreaker(self.store, config)
        breaker.charge("agent-1")
        self.assertEqual(breaker.config.calls, 1)
        self.assertAlmostEqual(breaker.config.spend, 0.01, places=6)

    def test_charge_trips_at_limit(self) -> None:
        config = BudgetBreakerConfig(max_calls=1, max_spend=1.0, cost_per_call=0.01)
        breaker = BudgetBreaker(self.store, config)
        breaker.config.calls = 1
        breaker.config.spend = 0.01
        result = breaker.charge("agent-1")
        self.assertTrue(result["tripped"])

    def test_budget_reason_codes_defined(self) -> None:
        for code in ["calls_exceeded", "spend_exceeded", "both_exceeded", "invalid_budget"]:
            self.assertIn(code, BUDGET_REASON_CODES)
