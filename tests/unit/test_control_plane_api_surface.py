"""Unit tests for control-plane API surface composer (PR #154)."""

from __future__ import annotations

import unittest

from thinkbox.control_plane_api_surface import (
    build_contract_payload,
    create_operation_via_admission,
)
from thinkbox.control_plane_operation_registry import reset_operation_registry


class TestControlPlaneApiSurface(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        reset_operation_registry()

    def test_contract_lists_routes(self) -> None:
        payload = build_contract_payload()
        self.assertFalse(payload["live_api_called"])
        self.assertIn("GET /api/v1/control-plane/contract", payload["routes"])

    async def test_create_operation_admitted(self) -> None:
        op, err = await create_operation_via_admission(
            "surf_op1",
            "demo",
            governance_token="hermetic-token",
        )
        self.assertEqual(err, "")
        self.assertIsNotNone(op)
        assert op is not None
        self.assertIsNotNone(op.receipt_id)
        self.assertIsNotNone(op.etag)

    async def test_create_operation_denied_no_token(self) -> None:
        op, err = await create_operation_via_admission(
            "surf_op2",
            "demo",
            governance_token=None,
        )
        self.assertEqual(err, "admission_denied")
        assert op is not None
        self.assertEqual(op.state.value, "denied")


if __name__ == "__main__":
    unittest.main()
