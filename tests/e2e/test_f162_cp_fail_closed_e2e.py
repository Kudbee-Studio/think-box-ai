"""PR #162 — fail-closed batch body + auth paths (hermetic)."""

from __future__ import annotations

import unittest

from tests.e2e.control_plane_hermetic import auth_headers, control_plane_client


class TestF162ControlPlaneFailClosedE2e(unittest.TestCase):
    def test_batch_empty_receipt_ids_400(self) -> None:
        with control_plane_client() as client:
            resp = client.post(
                "/api/v1/control-plane/receipts/validate/batch",
                json={"receipt_ids": []},
                headers=auth_headers(),
            )
            self.assertEqual(resp.status_code, 400)

    def test_batch_invalid_json_shape_400(self) -> None:
        with control_plane_client() as client:
            resp = client.post(
                "/api/v1/control-plane/receipts/validate/batch",
                json=["not", "an", "object"],
                headers=auth_headers(),
            )
            self.assertEqual(resp.status_code, 400)

    def test_unauthenticated_401(self) -> None:
        with control_plane_client() as client:
            resp = client.get("/api/v1/control-plane/contract")
            self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
