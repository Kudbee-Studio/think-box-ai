"""Unit tests for control_plane_e2e_assertions (PR #162)."""

from __future__ import annotations

import unittest

from thinkbox.control_plane_e2e_assertions import (
    assert_ops_timing_honesty,
    assert_success_envelope_honesty,
    assert_validate_integrity_fields,
    control_plane_e2e_contract_snippet,
)


class TestControlPlaneE2eAssertions(unittest.TestCase):
    def test_success_envelope_honesty_ok(self) -> None:
        body = {"ok": True, "live_api_called": False, "data": {"live_api_called": False}}
        self.assertEqual(assert_success_envelope_honesty(body), [])

    def test_success_envelope_rejects_live(self) -> None:
        body = {"ok": True, "live_verified": True}
        self.assertIn("live_verified_true", assert_success_envelope_honesty(body))

    def test_ops_timing(self) -> None:
        data = {
            "ops": {
                "timing_ms": 1,
                "four_state_max": "TEST_VERIFIED",
                "live_verified": False,
                "route": "GET /receipts/{receipt_id}/validate",
                "idempotent_retry_safe": True,
            },
        }
        self.assertEqual(assert_ops_timing_honesty(data), [])

    def test_validate_integrity_fields(self) -> None:
        data = {
            "receipt_id": "r1",
            "valid": True,
            "link_integrity": "ok",
            "evidence_label": "simulated",
        }
        self.assertEqual(assert_validate_integrity_fields(data), [])

    def test_contract_snippet(self) -> None:
        snippet = control_plane_e2e_contract_snippet()
        self.assertFalse(snippet["live_verified"])


if __name__ == "__main__":
    unittest.main()
