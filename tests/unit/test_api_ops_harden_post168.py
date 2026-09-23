"""Unit tests for PR #169 theme B api ops harden post168."""

from __future__ import annotations

import unittest

from thinkbox import kilo_api_ops_harden_post168 as post168
from thinkbox.api_ops_harden_post168 import (
    API_OPS_POST168_LABEL,
    build_post168_fail_closed_envelope,
)


class TestApiOpsHardenPost168(unittest.TestCase):
    def test_gate_constants(self) -> None:
        self.assertEqual(post168.GATE_ID, "api-ops-harden-post168")
        self.assertEqual(post168.PR_NUMBER, 169)

    def test_fail_closed_envelope(self) -> None:
        env = build_post168_fail_closed_envelope(gate_id=post168.GATE_ID, detail="test")
        self.assertFalse(env["live_verified"])
        self.assertFalse(env["live_api_called"])
        self.assertEqual(env["four_state_max"], "TEST_VERIFIED")
        self.assertEqual(API_OPS_POST168_LABEL, "api-ops-harden-post168")

    def test_hermetic_gate_closed(self) -> None:
        result = post168.hermetic_api_ops_harden_post168_check(
            post168.minimal_api_ops_harden_post168_environ(),
        )
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
