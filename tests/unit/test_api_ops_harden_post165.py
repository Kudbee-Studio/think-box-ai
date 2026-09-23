"""Unit tests for PR #166 theme B api ops harden post165."""

from __future__ import annotations

import unittest

from thinkbox import kilo_api_ops_harden_post165 as post165
from thinkbox.api_ops_harden_post165 import (
    API_OPS_POST165_LABEL,
    build_post165_fail_closed_envelope,
    validate_post165_ops_envelope,
)


class TestApiOpsHardenPost165(unittest.TestCase):
    def test_gate_constants(self) -> None:
        self.assertEqual(post165.GATE_ID, "api-ops-harden-post165")

    def test_fail_closed_envelope(self) -> None:
        env = build_post165_fail_closed_envelope(gate_id=post165.GATE_ID, detail="test")
        self.assertFalse(env["live_verified"])
        self.assertFalse(env["live_api_called"])

    def test_validate_rejects_live_verified(self) -> None:
        _, errors = validate_post165_ops_envelope({"live_verified": True})
        self.assertTrue(any("live_verified" in e for e in errors))

    def test_hermetic_gate(self) -> None:
        result = post165.hermetic_api_ops_harden_post165_check(
            post165.minimal_api_ops_harden_post165_environ(),
        )
        self.assertTrue(result.ok)

    def test_contract_label(self) -> None:
        summary = post165.api_ops_harden_post165_contract_summary()
        self.assertEqual(summary["post165_label"], API_OPS_POST165_LABEL)


if __name__ == "__main__":
    unittest.main()
