"""Tests: Demo-in-10 control-plane admit + capacity binding."""

import os
import unittest
from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.demo_bind import (
    DemoConfig,
    DemoControlPlaneBind,
    DemoAdmitResult,
)


class TestDemoControlPlaneBind(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ActionReceiptStore(":memory:")
        self.config = DemoConfig(agent_id="test-demo")

    def tearDown(self) -> None:
        self.store.close()

    def test_admit_with_mock_token(self) -> None:
        os.environ["THINKBOX_DEMO_TOKEN"] = "dev-only-local-token"
        bind = DemoControlPlaneBind(self.store, self.config)
        result = bind.admit()
        self.assertTrue(result.admitted)
        self.assertEqual(self.store.count(), 1)

    def test_admit_denied_without_token(self) -> None:
        os.environ.pop("THINKBOX_DEMO_TOKEN", None)
        bind = DemoControlPlaneBind(self.store, self.config)
        result = bind.admit()
        self.assertFalse(result.admitted)
        self.assertEqual(self.store.count(), 1)

    def test_admit_stores_receipt(self) -> None:
        os.environ["THINKBOX_DEMO_TOKEN"] = "dev-only-local-token"
        bind = DemoControlPlaneBind(self.store, self.config)
        bind.admit()
        with self.store._lock:
            row = self.store._conn.execute("SELECT metadata FROM receipts").fetchone()
        self.assertIsNotNone(row)

    def test_capacity_granted(self) -> None:
        os.environ["THINKBOX_DEMO_TOKEN"] = "dev-only-local-token"
        bind = DemoControlPlaneBind(self.store, self.config)
        bind.admit()
        granted = bind.request_capacity()
        self.assertTrue(granted)
        self.assertEqual(self.store.count(), 2)

    def test_capacity_denied_if_not_admitted(self) -> None:
        os.environ.pop("THINKBOX_DEMO_TOKEN", None)
        bind = DemoControlPlaneBind(self.store, self.config)
        granted = bind.request_capacity()
        self.assertFalse(granted)
        self.assertEqual(self.store.count(), 1)

    def test_fail_closed(self) -> None:
        """No token → no admit → no capacity → no execution."""
        os.environ.pop("THINKBOX_DEMO_TOKEN", None)
        bind = DemoControlPlaneBind(self.store, self.config)
        admit_result = bind.admit()
        capacity = bind.request_capacity()
        self.assertFalse(admit_result.admitted)
        self.assertFalse(capacity)

    def test_config_fields_populated(self) -> None:
        config = DemoConfig()
        self.assertEqual(config.agent_id, "demo")
        self.assertEqual(config.capability, "demo:run")
        self.assertEqual(config.model, "openai/gpt-oss-20b")
        self.assertEqual(config.pairs, 2)
        self.assertEqual(config.max_calls, 8)
        self.assertEqual(config.budget, 1.0)

    def test_evidence_label_simulated(self) -> None:
        os.environ["THINKBOX_DEMO_TOKEN"] = "dev-only-local-token"
        bind = DemoControlPlaneBind(self.store, self.config)
        result = bind.admit()
        self.assertEqual(result.evidence_label, "simulated")
