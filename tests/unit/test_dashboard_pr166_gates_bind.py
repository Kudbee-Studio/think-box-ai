"""Unit tests for PR #167 theme C dashboard PR166 gates bind."""

from __future__ import annotations

import unittest

from thinkbox import kilo_dashboard_pr166_gates_bind as bind
from thinkbox.dashboard_pr166_gates_bind import (
    DASHBOARD_PR166_BIND_LABEL,
    PR166_THEME_GATE_IDS,
    bind_pr166_gates_to_slots,
)


class TestDashboardPr166GatesBind(unittest.TestCase):
    def test_gate_constants(self) -> None:
        self.assertEqual(bind.GATE_ID, "dashboard-pr166-gates-bind")
        self.assertEqual(len(PR166_THEME_GATE_IDS), 4)

    def test_bind_slots_honesty(self) -> None:
        rows = bind_pr166_gates_to_slots({gid: True for gid in PR166_THEME_GATE_IDS})
        self.assertEqual(len(rows), 4)
        for row in rows:
            self.assertFalse(row["live_verified"])
            self.assertEqual(row["four_state_max"], "TEST_VERIFIED")

    def test_hermetic_gate_closed(self) -> None:
        result = bind.hermetic_dashboard_pr166_gates_bind_check(
            bind.minimal_dashboard_pr166_gates_bind_environ(),
        )
        self.assertTrue(result.ok)
        self.assertEqual(DASHBOARD_PR166_BIND_LABEL, "dashboard-pr166-gates-bind")


if __name__ == "__main__":
    unittest.main()
