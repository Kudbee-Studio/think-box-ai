"""Gate module tests for PR #161 end-link-api-ops-harden."""

from __future__ import annotations

import unittest

from thinkbox.kilo_end_link_api_ops_harden import (
    GATE_ID,
    hermetic_end_link_api_ops_harden_check,
    minimal_end_link_api_ops_harden_environ,
)


class TestKiloEndLinkApiOpsHardenGate(unittest.TestCase):
    def test_gate_closed(self) -> None:
        result = hermetic_end_link_api_ops_harden_check(minimal_end_link_api_ops_harden_environ())
        self.assertTrue(result.ok, msg=[v.message for v in result.violations])
        self.assertEqual(GATE_ID, "end-link-api-ops-harden")


if __name__ == "__main__":
    unittest.main()
