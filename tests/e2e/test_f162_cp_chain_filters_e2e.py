"""PR #162 — receipt chain list filters (hermetic HTTP)."""

from __future__ import annotations

import unittest

from tests.e2e.control_plane_hermetic import auth_headers, control_plane_client, seed_receipt_id
from thinkbox.control_plane_e2e_assertions import (
    assert_fail_closed_envelope,
    assert_success_envelope_honesty,
)


class TestF162ControlPlaneChainFiltersE2e(unittest.TestCase):
    def test_chain_list_default(self) -> None:
        with control_plane_client() as client:
            seed_receipt_id(client, operation_id="op_f162_chain")
            resp = client.get(
                "/api/v1/control-plane/receipts/chain",
                headers=auth_headers(),
            )
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertEqual(assert_success_envelope_honesty(body), [])
            page = body["data"].get("page") or body["data"]
            self.assertIn("receipts", page)

    def test_chain_filter_status_simulated(self) -> None:
        with control_plane_client() as client:
            seed_receipt_id(client, operation_id="op_f162_filter")
            resp = client.get(
                "/api/v1/control-plane/receipts/chain",
                params={"status": "admitted", "evidence_label": "simulated"},
                headers=auth_headers(),
            )
            self.assertIn(resp.status_code, (200, 400))
            if resp.status_code == 200:
                self.assertEqual(assert_success_envelope_honesty(resp.json()), [])

    def test_chain_filter_invalid_status_400(self) -> None:
        with control_plane_client() as client:
            resp = client.get(
                "/api/v1/control-plane/receipts/chain",
                params={"status": "bad status!"},
                headers=auth_headers(),
            )
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(assert_fail_closed_envelope(resp.json()), [])


if __name__ == "__main__":
    unittest.main()
