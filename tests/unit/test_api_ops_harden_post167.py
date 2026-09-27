"""Unit tests for PR #168 theme B api ops harden post167."""

from __future__ import annotations

import unittest

from thinkbox import kilo_api_ops_harden_post167 as post167
from thinkbox.api_ops_harden_post167 import (
    API_OPS_POST167_LABEL,
    build_post167_fail_closed_envelope,
)


class TestApiOpsHardenPost167(unittest.TestCase):
    def test_gate_constants(self) -> None:
        self.assertEqual(post167.GATE_ID, "api-ops-harden-post167")
        self.assertEqual(post167.PR_NUMBER, 168)

    def test_fail_closed_envelope(self) -> None:
        env = build_post167_fail_closed_envelope(gate_id=post167.GATE_ID, detail="test")
        self.assertFalse(env["live_verified"])
        self.assertFalse(env["live_api_called"])
        self.assertEqual(env["four_state_max"], "TEST_VERIFIED")
        self.assertEqual(API_OPS_POST167_LABEL, "api-ops-harden-post167")

    def test_hermetic_gate_closed(self) -> None:
        result = post167.hermetic_api_ops_harden_post167_check(
            post167.minimal_api_ops_harden_post167_environ(),
        )
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
