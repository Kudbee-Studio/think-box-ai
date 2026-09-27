"""Tests for Autonomous Loop Session API Surface (PR #246).

Covers:
- list_autonomous_loop_sessions_payload: empty, populated, limit
- get_autonomous_loop_session_payload: found, not found (None)
- get_autonomous_loop_session_summary_payload: counts, averages
- API module import + endpoint registration markers
"""

from __future__ import annotations

import unittest

from thinkbox.dashboard_state import (
    DashboardState,
    AutonomousLoopEntry,
    AutonomousLoopTelemetry,
    LoopSessionEntry,
)
from thinkbox.autonomous_loop_api_surface import (
    AUTONOMOUS_LOOP_API_VERSION,
    AUTONOMOUS_LOOP_SCHEMA_VERSION,
    list_autonomous_loop_sessions_payload,
    get_autonomous_loop_session_payload,
    get_autonomous_loop_session_summary_payload,
)
import thinkbox.dashboard_state as ds_mod
import thinkbox.autonomous_loop_api_surface as api_mod


def _reset_dashboard():
    DashboardState._instance = None
    ds_mod._dashboard_state = None


class TestSessionApiPayloads(unittest.TestCase):
    def setUp(self) -> None:
        _reset_dashboard()
        self.state = DashboardState()

    def tearDown(self) -> None:
        _reset_dashboard()

    def test_list_sessions_empty(self) -> None:
        result = list_autonomous_loop_sessions_payload(self.state)
        self.assertEqual(result, [])

    def test_list_sessions_populated(self) -> None:
        s1 = LoopSessionEntry(
            session_id="sess_001", loop_id="loop_a",
            started_at="2026-01-01T00:00:00Z", closed_at="2026-01-01T01:00:00Z",
            iterations_count=5, avg_throughput=0.8, improved_over_baseline=False,
        )
        s2 = LoopSessionEntry(
            session_id="sess_002", loop_id="loop_a",
            started_at="2026-01-02T00:00:00Z", closed_at="2026-01-02T01:00:00Z",
            iterations_count=8, avg_throughput=1.2, improved_over_baseline=True,
        )
        self.state.record_autonomous_loop_session(s1)
        self.state.record_autonomous_loop_session(s2)

        result = list_autonomous_loop_sessions_payload(self.state)
        self.assertEqual(len(result), 2)
        ids = [r["session_id"] for r in result]
        self.assertIn("sess_001", ids)
        self.assertIn("sess_002", ids)

    def test_list_sessions_respects_limit(self) -> None:
        for i in range(10):
            self.state.record_autonomous_loop_session(
                LoopSessionEntry(
                    session_id=f"sess_{i}", loop_id="loop_a",
                    closed_at=f"2026-01-0{i+1}T01:00:00Z",
                )
            )
        result = list_autonomous_loop_sessions_payload(self.state, limit=3)
        self.assertEqual(len(result), 3)

    def test_get_session_found(self) -> None:
        s = LoopSessionEntry(
            session_id="sess_target", loop_id="loop_b",
            started_at="2026-01-01T00:00:00Z", closed_at="2026-01-01T01:00:00Z",
            iterations_count=3, avg_throughput=0.5, avg_p50_latency=1.0,
        )
        self.state.record_autonomous_loop_session(s)

        payload = get_autonomous_loop_session_payload("sess_target", self.state)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["session_id"], "sess_target")
        self.assertEqual(payload["loop_id"], "loop_b")
        self.assertEqual(payload["iterations_count"], 3)

    def test_get_session_not_found_returns_none(self) -> None:
        payload = get_autonomous_loop_session_payload("nonexistent_sess", self.state)
        self.assertIsNone(payload)

    def test_session_summary_empty(self) -> None:
        summary = get_autonomous_loop_session_summary_payload(self.state)
        self.assertEqual(summary["total_sessions"], 0)
        self.assertEqual(summary["avg_throughput"], 0.0)
        self.assertEqual(summary["avg_total_cycle_time_s"], 0.0)
        self.assertEqual(summary["sessions_with_patterns"], 0)
        self.assertEqual(summary["improved_sessions"], 0)

    def test_session_summary_populated(self) -> None:
        s1 = LoopSessionEntry(
            session_id="sess_001", loop_id="loop_a",
            started_at="2026-01-01T00:00:00Z", closed_at="2026-01-01T01:00:00Z",
            iterations_count=5, avg_throughput=0.8, avg_p50_latency=1.2,
            avg_error_rate=0.02, total_cycle_time_s=300.0, patterns_identified=2,
            improved_over_baseline=True,
        )
        s2 = LoopSessionEntry(
            session_id="sess_002", loop_id="loop_a",
            started_at="2026-01-02T00:00:00Z", closed_at="2026-01-02T01:00:00Z",
            iterations_count=8, avg_throughput=1.2, avg_p50_latency=0.8,
            avg_error_rate=0.01, total_cycle_time_s=480.0, patterns_identified=0,
            improved_over_baseline=False,
        )
        self.state.record_autonomous_loop_session(s1)
        self.state.record_autonomous_loop_session(s2)

        summary = get_autonomous_loop_session_summary_payload(self.state)
        self.assertEqual(summary["total_sessions"], 2)
        self.assertEqual(summary["sessions_with_patterns"], 1)
        self.assertEqual(summary["improved_sessions"], 1)
        self.assertAlmostEqual(summary["avg_throughput"], 1.0, places=6)

    def test_session_payload_includes_schema_version(self) -> None:
        summary = get_autonomous_loop_session_summary_payload(self.state)
        self.assertEqual(summary["api_version"], AUTONOMOUS_LOOP_API_VERSION)
        self.assertEqual(summary["schema_version"], AUTONOMOUS_LOOP_SCHEMA_VERSION)


class TestSessionApiModuleImports(unittest.TestCase):

    def test_session_helpers_exist(self) -> None:
        self.assertTrue(hasattr(api_mod, "list_autonomous_loop_sessions_payload"))
        self.assertTrue(hasattr(api_mod, "get_autonomous_loop_session_payload"))
        self.assertTrue(hasattr(api_mod, "get_autonomous_loop_session_summary_payload"))

    def test_backend_module_session_endpoints(self) -> None:
        try:
            import backend.api.v1.autonomous_loop as api_module
            self.assertTrue(hasattr(api_module, "AUTONOMOUS_LOOP_API_VERSION"))
            self.assertTrue(hasattr(api_module, "get_autonomous_loop_session_summary_payload"))
            self.assertTrue(hasattr(api_module, "list_autonomous_loop_sessions_payload"))
            self.assertTrue(hasattr(api_module, "get_autonomous_loop_session_payload"))
        except ImportError:
            self.skipTest("FastAPI not installed in test environment")


if __name__ == "__main__":
    unittest.main()
