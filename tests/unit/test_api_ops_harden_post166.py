"""Unit tests for PR #167 theme B api ops harden post166."""

from __future__ import annotations

import unittest

from thinkbox import kilo_api_ops_harden_post166 as post166
from thinkbox.api_ops_harden_post166 import (
    API_OPS_POST166_LABEL,
    build_post166_fail_closed_envelope,
)


class TestApiOpsHardenPost166(unittest.TestCase):
    def test_gate_constants(self) -> None:
        self.assertEqual(post166.GATE_ID, "api-ops-harden-post166")
        self.assertEqual(post166.PR_NUMBER, 167)

    def test_fail_closed_envelope(self) -> None:
        env = build_post166_fail_closed_envelope(gate_id=post166.GATE_ID, detail="test")
        self.assertFalse(env["live_verified"])
        self.assertFalse(env["live_api_called"])
        self.assertEqual(env["four_state_max"], "TEST_VERIFIED")
        self.assertEqual(API_OPS_POST166_LABEL, "api-ops-harden-post166")

    def test_hermetic_gate_closed(self) -> None:
        result = post166.hermetic_api_ops_harden_post166_check(
            post166.minimal_api_ops_harden_post166_environ(),
        )
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
