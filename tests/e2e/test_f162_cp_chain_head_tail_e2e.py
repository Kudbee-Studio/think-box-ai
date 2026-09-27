"""PR #162 — chain head/tail reads (hermetic HTTP)."""

from __future__ import annotations

import unittest

from tests.e2e.control_plane_hermetic import auth_headers, control_plane_client, seed_receipt_id
from thinkbox.control_plane_e2e_assertions import assert_success_envelope_honesty


class TestF162ControlPlaneChainHeadTailE2e(unittest.TestCase):
    def test_head_and_tail_after_seed(self) -> None:
        with control_plane_client() as client:
            rid = seed_receipt_id(client, operation_id="op_f162_head")
            head = client.get(
                "/api/v1/control-plane/receipts/chain/head",
                headers=auth_headers(),
            )
            tail = client.get(
                "/api/v1/control-plane/receipts/chain/tail",
                headers=auth_headers(),
            )
            self.assertEqual(head.status_code, 200)
            self.assertEqual(tail.status_code, 200)
            self.assertEqual(assert_success_envelope_honesty(head.json()), [])
            self.assertEqual(assert_success_envelope_honesty(tail.json()), [])
            tail_row = (tail.json().get("data") or {}).get("tail") or {}
            self.assertEqual(tail_row.get("receipt_id"), rid)


if __name__ == "__main__":
    unittest.main()
