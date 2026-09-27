"""Unit tests for PR #169 theme C dashboard PR168 gates bind."""

from __future__ import annotations

import unittest
from pathlib import Path

from thinkbox import kilo_dashboard_pr168_gates_bind as bind
from thinkbox.dashboard_pr168_gates_bind import DASHBOARD_PR168_BIND_LABEL, PR168_THEME_GATE_IDS
from thinkbox.kilo_live_proof_readiness import REPO_ROOT


class TestDashboardPr168GatesBind(unittest.TestCase):
    def test_gate_constants(self) -> None:
        self.assertEqual(bind.GATE_ID, "dashboard-pr168-gates-bind")
        self.assertEqual(bind.PR_NUMBER, 169)
        self.assertEqual(len(PR168_THEME_GATE_IDS), 4)

    def test_status_html_present(self) -> None:
        path = REPO_ROOT / bind.HTML_REL
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn(DASHBOARD_PR168_BIND_LABEL, text)

    def test_hermetic_gate_closed(self) -> None:
        result = bind.hermetic_dashboard_pr168_gates_bind_check(
            bind.minimal_dashboard_pr168_gates_bind_environ(),
        )
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
