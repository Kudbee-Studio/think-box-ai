"""PR #162 — batch END LINK validate + idempotency (hermetic)."""

from __future__ import annotations

import unittest

from tests.e2e.control_plane_hermetic import (
    auth_headers,
    control_plane_client,
    seed_receipt_chain,
)
from thinkbox.control_plane_e2e_assertions import (
    assert_batch_item_shape,
    assert_ops_timing_honesty,
    assert_success_envelope_honesty,
)


class TestF162ControlPlaneBatchValidateE2e(unittest.TestCase):
    def test_batch_mixed_valid_and_missing(self) -> None:
        with control_plane_client() as client:
            rids = seed_receipt_chain(client, 2)
            body = {"receipt_ids": [rids[0], "receipt_missing_f162", rids[1]]}
            resp = client.post(
                "/api/v1/control-plane/receipts/validate/batch",
                json=body,
                headers=auth_headers(),
            )
            self.assertEqual(resp.status_code, 200)
            envelope = resp.json()
            self.assertEqual(assert_success_envelope_honesty(envelope), [])
            data = envelope["data"]
            self.assertEqual(data["total"], 3)
            self.assertGreaterEqual(data["invalid_count"], 1)
            for item in data.get("items") or []:
                self.assertEqual(assert_batch_item_shape(item), [])

    def test_batch_idempotency_replay(self) -> None:
        with control_plane_client() as client:
            rid = seed_receipt_chain(client, 1)[0]
            payload = {"receipt_ids": [rid]}
            headers = {**auth_headers(), "Idempotency-Key": "f162-batch-idem"}
            first = client.post(
                "/api/v1/control-plane/receipts/validate/batch",
                json=payload,
                headers=headers,
            )
            second = client.post(
                "/api/v1/control-plane/receipts/validate/batch",
                json=payload,
                headers=headers,
            )
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)
            d1 = first.json()["data"]
            d2 = second.json()["data"]
            self.assertEqual(d1["total"], d2["total"])
            self.assertEqual(assert_ops_timing_honesty(d1), [])


if __name__ == "__main__":
    unittest.main()
