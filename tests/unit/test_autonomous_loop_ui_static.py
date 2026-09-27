"""Hermetic tests for Autonomous Loop control plane UI & static assets (PR #246)."""

from __future__ import annotations

import unittest
from pathlib import Path


class TestAutonomousLoopStaticAssets(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path("public/control-plane")

    def test_html_exists_and_contains_markers_and_scripts(self) -> None:
        html_path = self.root / "autonomous_loop.html"
        self.assertTrue(html_path.exists(), "autonomous_loop.html must exist")
        html = html_path.read_text(encoding="utf-8")

        self.assertIn("autonomous_loop_client.js", html)
        self.assertIn("load_perf.js", html)
        self.assertIn("gate marker: autonomous-loop-learning-curve-sessions", html)
        self.assertIn("gate marker: autonomous-loop-actions-ui", html)
        self.assertIn("/api/v1/autonomous-loop/status", html)
        self.assertIn("/api/v1/autonomous-loop/loops", html)
        self.assertIn("/api/v1/autonomous-loop/telemetry", html)
        self.assertIn("/api/v1/autonomous-loop/sessions", html)
        self.assertIn("/api/v1/autonomous-loop/sessions/summary", html)
        self.assertIn("/api/v1/autonomous-loop/loops/{loop_id}/actions", html)
        self.assertIn("/api/v1/autonomous-loop/actions", html)
        self.assertIn("/api/v1/autonomous-loop/actions/integrity", html)
        self.assertIn("Autonomous Decision Loop", html)
        self.assertIn("btnRefresh", html)
        self.assertIn("btnTogglePolling", html)
        self.assertIn("learningCurveCanvas", html)
        self.assertIn("convergenceHistory", html)
        self.assertIn("sessionList", html)
        self.assertIn("totalSessionsVal", html)
        self.assertIn("actionList", html)
        self.assertIn("actionControls", html)
        self.assertIn("btnActionStart", html)
        self.assertIn("btnActionStop", html)
        self.assertIn("btnActionRun", html)
        self.assertIn("btnActionReset", html)
        self.assertIn("governanceTokenInput", html)
        self.assertIn("integrityBadge", html)
        self.assertIn("integrityDetail", html)
        self.assertIn("Action Audit Chain", html)

    def test_client_js_exists_and_exports_helpers(self) -> None:
        js_path = self.root / "autonomous_loop_client.js"
        self.assertTrue(js_path.exists(), "autonomous_loop_client.js must exist")
        js = js_path.read_text(encoding="utf-8")

        self.assertIn("TBAutonomousLoopClient", js)
        self.assertIn("ALL_COMPONENTS", js)
        self.assertIn("/api/v1/autonomous-loop/status", js)
        self.assertIn("/api/v1/autonomous-loop/loops", js)
        self.assertIn("/api/v1/autonomous-loop/telemetry", js)
        self.assertIn("/api/v1/autonomous-loop/sessions", js)
        self.assertIn("/api/v1/autonomous-loop/sessions/summary", js)
        self.assertIn("/api/v1/autonomous-loop/loops/", js)
        self.assertIn("/api/v1/autonomous-loop/actions", js)
        self.assertIn("/api/v1/autonomous-loop/actions/integrity", js)
        self.assertIn("bootstrap", js)
        self.assertIn("session_manager", js)
        self.assertIn("auto_tuner", js)
        self.assertIn("renderLearningCurve", js)
        self.assertIn("renderSessions", js)
        self.assertIn("renderConvergenceHistory", js)
        self.assertIn("fetchSessions", js)
        self.assertIn("fetchSessionSummary", js)
        self.assertIn("fetchLoopActions", js)
        self.assertIn("fetchAllActions", js)
        self.assertIn("postLoopAction", js)
        self.assertIn("renderActionList", js)
        self.assertIn("showActionStatus", js)
        self.assertIn("sendLoopAction", js)
        self.assertIn("fetchActionIntegrity", js)
        self.assertIn("renderActionIntegrity", js)
        self.assertIn("integrityBadge", js)
        self.assertIn("X-Governance-Token", js)
        self.assertIn("governanceTokenInput", js)

    def test_index_links_autonomous_loop(self) -> None:
        index_path = self.root / "index.html"
        self.assertTrue(index_path.exists())
        index_html = index_path.read_text(encoding="utf-8")
        self.assertIn("autonomous_loop.html", index_html)


if __name__ == "__main__":
    unittest.main()
