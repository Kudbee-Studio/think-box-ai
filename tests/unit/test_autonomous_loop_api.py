"""Tests for Autonomous Loop API Surface and Endpoint Logic (PR #244).

Covers:
- get_autonomous_loop_status_payload: idle, healthy, metrics count, revision, versions
- list_autonomous_loops_payload: empty, multiple loops
- get_autonomous_loop_payload: found, not found (None)
- list_autonomous_loop_telemetry_payload: empty, populated
- get_autonomous_loop_telemetry_payload: found, loop not found (None), default fallback
- Fast/hermetic unit tests without requiring external FastAPI package in test runner
"""

from __future__ import annotations

import unittest

from thinkbox.autonomous_loop_api_surface import (
    AUTONOMOUS_LOOP_API_VERSION,
    AUTONOMOUS_LOOP_SCHEMA_VERSION,
    get_autonomous_loop_payload,
    get_autonomous_loop_status_payload,
    get_autonomous_loop_telemetry_payload,
    list_autonomous_loop_telemetry_payload,
    list_autonomous_loops_payload,
)
from thinkbox.dashboard_state import (
    AutonomousLoopEntry,
    AutonomousLoopTelemetry,
    DashboardState,
    get_dashboard_state,
)
import thinkbox.dashboard_state as ds_mod


def _reset_dashboard():
    DashboardState._instance = None
    ds_mod._dashboard_state = None


class TestAutonomousLoopApiSurface(unittest.TestCase):
    def setUp(self) -> None:
        _reset_dashboard()
        self.state = get_dashboard_state()

    def tearDown(self) -> None:
        _reset_dashboard()

    def test_status_payload_idle_when_empty(self) -> None:
        status = get_autonomous_loop_status_payload(self.state)
        self.assertEqual(status["status"], "idle")
        self.assertEqual(status["total_loops"], 0)
        self.assertEqual(status["active_loops"], 0)
        self.assertEqual(status["bootstrapped_loops"], 0)
        self.assertEqual(status["api_version"], AUTONOMOUS_LOOP_API_VERSION)
        self.assertEqual(status["schema_version"], AUTONOMOUS_LOOP_SCHEMA_VERSION)
        self.assertIn("revision", status)

    def test_status_payload_healthy_with_loops(self) -> None:
        e1 = AutonomousLoopEntry(loop_id="loop_1", status="running", bootstrapped=True)
        e2 = AutonomousLoopEntry(loop_id="loop_2", status="idle", bootstrapped=False)
        self.state.upsert_autonomous_loop(e1)
        self.state.upsert_autonomous_loop(e2)

        status = get_autonomous_loop_status_payload(self.state)
        self.assertEqual(status["status"], "healthy")
        self.assertEqual(status["total_loops"], 2)
        self.assertEqual(status["active_loops"], 1)
        self.assertEqual(status["bootstrapped_loops"], 1)

    def test_list_loops_empty(self) -> None:
        loops = list_autonomous_loops_payload(self.state)
        self.assertEqual(loops, [])

    def test_list_loops_populated(self) -> None:
        e = AutonomousLoopEntry(
            loop_id="loop_test",
            status="running",
            iterations_count=4,
            patterns_identified=2,
            tuning_decisions=1,
            bootstrapped=True,
            components={"bootstrap": True, "auto_tuner": True},
        )
        self.state.upsert_autonomous_loop(e)

        loops = list_autonomous_loops_payload(self.state)
        self.assertEqual(len(loops), 1)
        self.assertEqual(loops[0]["loop_id"], "loop_test")
        self.assertEqual(loops[0]["iterations_count"], 4)
        self.assertEqual(loops[0]["patterns_identified"], 2)
        self.assertEqual(loops[0]["tuning_decisions"], 1)
        self.assertTrue(loops[0]["bootstrapped"])
        self.assertTrue(loops[0]["components"]["bootstrap"])

    def test_get_loop_found(self) -> None:
        e = AutonomousLoopEntry(
            loop_id="loop_target",
            status="running",
            current_session_id="sess_abc",
            latest_recommendation={"type": "validation_run"},
        )
        self.state.upsert_autonomous_loop(e)

        payload = get_autonomous_loop_payload("loop_target", self.state)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["loop_id"], "loop_target")
        self.assertEqual(payload["current_session_id"], "sess_abc")
        self.assertEqual(payload["latest_recommendation"]["type"], "validation_run")

    def test_get_loop_not_found_returns_none(self) -> None:
        payload = get_autonomous_loop_payload("nonexistent_loop", self.state)
        self.assertIsNone(payload)

    def test_list_telemetry_empty(self) -> None:
        telemetry_list = list_autonomous_loop_telemetry_payload(self.state)
        self.assertEqual(telemetry_list, [])

    def test_list_telemetry_populated(self) -> None:
        e = AutonomousLoopEntry(loop_id="loop_t")
        self.state.upsert_autonomous_loop(e)
        tel = AutonomousLoopTelemetry(
            total_iterations=10,
            avg_cycle_time_s=1.2,
            convergence_status="converged",
            throughput=0.83,
        )
        self.state.record_loop_telemetry("loop_t", tel)

        items = list_autonomous_loop_telemetry_payload(self.state)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["total_iterations"], 10)
        self.assertEqual(items[0]["convergence_status"], "converged")

    def test_get_telemetry_for_existing_loop(self) -> None:
        e = AutonomousLoopEntry(loop_id="loop_spec")
        self.state.upsert_autonomous_loop(e)
        tel = AutonomousLoopTelemetry(
            total_iterations=5,
            recommendation_types={"explore": 3, "exploit": 2},
            priority_distribution={"high": 4},
            convergence_status="improving",
        )
        self.state.record_loop_telemetry("loop_spec", tel)

        payload = get_autonomous_loop_telemetry_payload("loop_spec", self.state)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["total_iterations"], 5)
        self.assertEqual(payload["convergence_status"], "improving")
        self.assertEqual(payload["recommendation_types"]["explore"], 3)
        self.assertEqual(payload["priority_distribution"]["high"], 4)

    def test_get_telemetry_for_loop_without_explicit_telemetry_returns_defaults(self) -> None:
        e = AutonomousLoopEntry(loop_id="loop_empty_tel")
        self.state.upsert_autonomous_loop(e)

        payload = get_autonomous_loop_telemetry_payload("loop_empty_tel", self.state)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["total_iterations"], 0)
        self.assertEqual(payload["convergence_status"], "pending")

    def test_get_telemetry_for_nonexistent_loop_returns_none(self) -> None:
        payload = get_autonomous_loop_telemetry_payload("does_not_exist", self.state)
        self.assertIsNone(payload)

    def test_api_module_imports_cleanly(self) -> None:
        import backend.api.v1.autonomous_loop as api_mod
        self.assertTrue(hasattr(api_mod, "get_autonomous_loop_status_payload"))
        self.assertTrue(hasattr(api_mod, "list_autonomous_loops_payload"))


if __name__ == "__main__":
    unittest.main()
