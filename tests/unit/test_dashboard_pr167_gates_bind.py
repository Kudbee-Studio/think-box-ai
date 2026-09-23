"""Unit tests for PR #168 theme C dashboard PR167 gates bind."""

from __future__ import annotations

import unittest

from thinkbox import kilo_dashboard_pr167_gates_bind as bind
from thinkbox.dashboard_pr167_gates_bind import (
    DASHBOARD_PR167_BIND_LABEL,
    PR167_THEME_GATE_IDS,
    bind_pr167_gates_to_slots,
)


class TestDashboardPr167GatesBind(unittest.TestCase):
    def test_gate_constants(self) -> None:
        self.assertEqual(bind.GATE_ID, "dashboard-pr167-gates-bind")
        self.assertEqual(len(PR167_THEME_GATE_IDS), 4)

    def test_bind_slots_honesty(self) -> None:
        rows = bind_pr167_gates_to_slots({gid: True for gid in PR167_THEME_GATE_IDS})
        self.assertEqual(len(rows), 4)
        for row in rows:
            self.assertFalse(row["live_verified"])
            self.assertEqual(row["four_state_max"], "TEST_VERIFIED")

    def test_hermetic_gate_closed(self) -> None:
        result = bind.hermetic_dashboard_pr167_gates_bind_check(
            bind.minimal_dashboard_pr167_gates_bind_environ(),
        )
        self.assertTrue(result.ok)
        self.assertEqual(DASHBOARD_PR167_BIND_LABEL, "dashboard-pr167-gates-bind")


if __name__ == "__main__":
    unittest.main()
