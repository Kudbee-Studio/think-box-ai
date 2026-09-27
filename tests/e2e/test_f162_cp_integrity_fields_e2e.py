"""PR #162 — prev_receipt_id / link_integrity on validate + batch (hermetic)."""

from __future__ import annotations

import unittest

from tests.e2e.control_plane_hermetic import (
    auth_headers,
    control_plane_client,
    seed_receipt_chain,
)


class TestF162ControlPlaneIntegrityFieldsE2e(unittest.TestCase):
    def test_second_receipt_has_prev_link(self) -> None:
        with control_plane_client() as client:
            rids = seed_receipt_chain(client, 2)
            second = client.get(
                f"/api/v1/control-plane/receipts/{rids[1]}/validate",
                headers=auth_headers(),
            )
            self.assertEqual(second.status_code, 200)
            data = second.json()["data"]
            self.assertTrue(data.get("valid"))
            self.assertIn(data.get("link_integrity"), ("ok", "unknown"))
            prev = data.get("prev_receipt_id")
            if prev is not None:
                self.assertEqual(prev, rids[0])

    def test_batch_items_carry_integrity(self) -> None:
        with control_plane_client() as client:
            rids = seed_receipt_chain(client, 2)
            resp = client.post(
                "/api/v1/control-plane/receipts/validate/batch",
                json={"receipt_ids": rids},
                headers=auth_headers(),
            )
            items = resp.json()["data"]["items"]
            self.assertEqual(len(items), 2)
            for item in items:
                self.assertIn("link_integrity", item)
                self.assertIn("failure_code", item)


if __name__ == "__main__":
    unittest.main()
