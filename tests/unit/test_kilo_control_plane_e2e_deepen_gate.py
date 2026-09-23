"""KILO gate tests for control-plane E2E deepen (PR #162)."""

from __future__ import annotations

import unittest

from thinkbox.kilo_control_plane_e2e_deepen import (
    GATE_ID,
    PR_NUMBER,
    hermetic_control_plane_e2e_deepen_check,
    minimal_control_plane_e2e_deepen_environ,
)


class TestKiloControlPlaneE2eDeepenGate(unittest.TestCase):
    def test_gate_id(self) -> None:
        self.assertEqual(GATE_ID, "control-plane-e2e-deepen")
        self.assertEqual(PR_NUMBER, 162)

    def test_hermetic_gate_closed(self) -> None:
        result = hermetic_control_plane_e2e_deepen_check(minimal_control_plane_e2e_deepen_environ())
        self.assertTrue(result.ok, msg=[v.message for v in result.violations])


if __name__ == "__main__":
    unittest.main()
