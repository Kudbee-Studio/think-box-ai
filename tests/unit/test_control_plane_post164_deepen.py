"""Unit tests for control-plane post-#164 deepen (PR #165 theme B)."""

from __future__ import annotations

import unittest

from thinkbox.control_plane_post164_deepen import (
    assert_hermetic_control_plane_response,
    validate_post164_request_envelope,
)


class TestControlPlanePost164Deepen(unittest.TestCase):
    def test_rejects_live_verified_in_request(self) -> None:
        _, errors = validate_post164_request_envelope({"live_verified": True})
        self.assertIn("live_verified_forbidden_in_hermetic_request", errors)

    def test_response_cap_enforced(self) -> None:
        violations = assert_hermetic_control_plane_response(
            {"four_state_max": "LIVE_VERIFIED"},
        )
        self.assertIn("response_four_state_cap_exceeded", violations)


if __name__ == "__main__":
    unittest.main()
