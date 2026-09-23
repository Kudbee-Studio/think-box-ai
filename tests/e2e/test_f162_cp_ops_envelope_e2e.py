"""PR #162 — ops timing / idempotency fields inside 200 envelopes (hermetic)."""

from __future__ import annotations

import unittest

from tests.e2e.control_plane_hermetic import (
    auth_headers,
    control_plane_client,
    seed_receipt_id,
)


class TestF162ControlPlaneOpsEnvelopeE2e(unittest.TestCase):
    def test_validate_ops_stack_layers(self) -> None:
        with control_plane_client() as client:
            rid = seed_receipt_id(client, operation_id="op_f162_ops")
            resp = client.get(
                f"/api/v1/control-plane/receipts/{rid}/validate",
                headers=auth_headers(),
            )
            ops = resp.json()["data"].get("ops") or {}
            self.assertFalse(ops.get("live_verified", True))
            self.assertEqual(ops.get("four_state_max"), "TEST_VERIFIED")
            layers = ops.get("stack_layers") or []
            self.assertTrue(layers)

    def test_batch_ops_idempotency_flag(self) -> None:
        with control_plane_client() as client:
            rid = seed_receipt_id(client, operation_id="op_f162_batch_ops")
            headers = {**auth_headers(), "Idempotency-Key": "f162-ops-flag"}
            resp = client.post(
                "/api/v1/control-plane/receipts/validate/batch",
                json={"receipt_ids": [rid]},
                headers=headers,
            )
            ops = resp.json()["data"].get("ops") or {}
            self.assertTrue(ops.get("idempotency_key_present"))
            self.assertIsNotNone(ops.get("timing_ms"))


if __name__ == "__main__":
    unittest.main()
