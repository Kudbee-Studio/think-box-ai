"""Unit tests for control-plane operation registry (PR #154)."""

from __future__ import annotations

import unittest

from thinkbox.control_plane_operation_registry import (
    OperationState,
    reset_operation_registry,
)
from thinkbox.control_plane_operation_registry import get_operation_registry


class TestOperationRegistry(unittest.TestCase):
    def setUp(self) -> None:
        reset_operation_registry()

    def test_create_and_get(self) -> None:
        reg = get_operation_registry()
        op = reg.create("op1", "demo.action")
        self.assertIsNotNone(op)
        self.assertEqual(reg.get("op1").action_type, "demo.action")

    def test_duplicate_create(self) -> None:
        reg = get_operation_registry()
        reg.create("op1", "a")
        self.assertIsNone(reg.create("op1", "b"))

    def test_cancel_running(self) -> None:
        reg = get_operation_registry()
        reg.create("op1", "a")
        reg.transition("op1", OperationState.RUNNING)
        cancelled = reg.cancel("op1")
        self.assertEqual(cancelled.state, OperationState.CANCELLED)

    def test_list_limit(self) -> None:
        reg = get_operation_registry()
        for i in range(5):
            reg.create(f"op{i}", "a")
        self.assertEqual(len(reg.list_operations(limit=3)), 3)


if __name__ == "__main__":
    unittest.main()
