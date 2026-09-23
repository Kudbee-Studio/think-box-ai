"""PR #162 — single END LINK validate via control-plane HTTP (hermetic)."""

from __future__ import annotations

import unittest

from tests.e2e.control_plane_hermetic import (
    auth_headers,
    control_plane_client,
    seed_receipt_id,
)
from thinkbox.control_plane_e2e_assertions import (
    assert_ops_timing_honesty,
    assert_success_envelope_honesty,
    assert_validate_integrity_fields,
)


class TestF162ControlPlaneValidateSingleE2e(unittest.TestCase):
    def test_validate_success_envelope_and_ops(self) -> None:
        with control_plane_client() as client:
            rid = seed_receipt_id(client, operation_id="op_f162_validate")
            resp = client.get(
                f"/api/v1/control-plane/receipts/{rid}/validate",
                headers=auth_headers(),
            )
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertEqual(assert_success_envelope_honesty(body), [])
            data = body["data"]
            self.assertEqual(assert_validate_integrity_fields(data), [])
            self.assertEqual(assert_ops_timing_honesty(data), [])

    def test_validate_unknown_receipt_404_fail_closed(self) -> None:
        with control_plane_client() as client:
            resp = client.get(
                "/api/v1/control-plane/receipts/receipt_missing_f162/validate",
                headers=auth_headers(),
            )
            self.assertEqual(resp.status_code, 404)
            detail = resp.json().get("detail") or {}
            self.assertFalse(detail.get("ok", True))


if __name__ == "__main__":
    unittest.main()
