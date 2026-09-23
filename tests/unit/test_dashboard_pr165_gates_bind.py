"""Unit tests for PR #166 theme C dashboard PR165 gates bind."""

from __future__ import annotations

import unittest

from thinkbox import kilo_dashboard_pr165_gates_bind as bind
from thinkbox.dashboard_pr165_gates_bind import bind_pr165_gates_to_slots


class TestDashboardPr165GatesBind(unittest.TestCase):
    def test_bind_slot_count(self) -> None:
        from thinkbox.dashboard_pr165_gates_bind import PR165_THEME_GATE_IDS

        rows = bind_pr165_gates_to_slots({g: True for g in PR165_THEME_GATE_IDS})
        self.assertEqual(len(rows), 4)
        for row in rows:
            self.assertFalse(row["live_verified"])

    def test_hermetic_gate(self) -> None:
        result = bind.hermetic_dashboard_pr165_gates_bind_check(
            bind.minimal_dashboard_pr165_gates_bind_environ(),
        )
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
