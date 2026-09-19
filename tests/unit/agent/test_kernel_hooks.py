"""Tests for kernel/control-plane hooks."""

import json
import unittest
from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.kernel_hooks import (
    HookContext,
    on_admit,
    on_capacity,
    on_secret,
    on_shutdown,
)


class TestKernelHooks(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ActionReceiptStore(":memory:")
        self.ctx = HookContext(agent_id="agent-1", action="admit")

    def tearDown(self) -> None:
        self.store.close()

    def test_on_admit_persists_receipt(self) -> None:
        on_admit(self.store, self.ctx)
        self.assertEqual(self.store.count(), 1)
        latest = self.store.latest(1)[0]
        self.assertEqual(latest["action"], "admit")
        self.assertEqual(latest["status"], "allowed")

    def test_on_capacity_persists_receipt(self) -> None:
        on_capacity(self.store, self.ctx)
        self.assertEqual(self.store.count(), 1)
        latest = self.store.latest(1)[0]
        self.assertEqual(latest["action"], "capacity")

    def test_on_secret_persists_receipt(self) -> None:
        on_secret(self.store, self.ctx)
        self.assertEqual(self.store.count(), 1)
        latest = self.store.latest(1)[0]
        self.assertEqual(latest["action"], "secret")

    def test_on_shutdown_persists_receipt(self) -> None:
        on_shutdown(self.store, self.ctx)
        self.assertEqual(self.store.count(), 1)
        latest = self.store.latest(1)[0]
        self.assertEqual(latest["action"], "shutdown")

    def test_hook_chaining(self) -> None:
        on_admit(self.store, self.ctx)
        on_capacity(self.store, self.ctx)
        on_secret(self.store, self.ctx)
        on_shutdown(self.store, self.ctx)
        self.assertEqual(self.store.count(), 4)
        self.assertTrue(self.store.verify())

    def test_custom_reason(self) -> None:
        ctx = HookContext(
            agent_id="a1",
            action="admit",
            reason="custom reason",
            status="denied",
            evidence_label="_demo",
        )
        on_admit(self.store, ctx)
        latest = self.store.latest(1)[0]
        self.assertEqual(latest["reason"], "custom reason")
        self.assertEqual(latest["status"], "denied")
        self.assertEqual(latest["evidence_label"], "_demo")

    def test_agent_id_isolation(self) -> None:
        ctx_a = HookContext(agent_id="agent-a", action="admit")
        ctx_b = HookContext(agent_id="agent-b", action="admit")
        on_admit(self.store, ctx_a)
        on_admit(self.store, ctx_b)
        self.assertEqual(self.store.count(), 2)

    def test_verify_after_hooks(self) -> None:
        import json
        for i in range(10):
            ctx = HookContext(
                agent_id=f"agent-{i}",
                action="admit",
                reason=f"reason-{i}",
                metadata={"task_id": f"task-{i}"},
            )
            on_admit(self.store, ctx)
        self.assertTrue(self.store.verify())
        rows = self.store._conn.execute(
            "SELECT metadata FROM receipts ORDER BY rowid"
        ).fetchall()
        self.assertEqual(json.loads(rows[0][0])["task_id"], "task-0")
