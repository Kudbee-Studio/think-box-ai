"""Hermetic tests for Autonomous Loop Actions API surface + governance token gate (PR #249).

Covers:
- extract_governance_token: X-Governance-Token present, Bearer token present,
  both absent, whitespace-only values, precedence (header wins over Bearer)
- validate_loop_action: each allowed action, unknown action, empty string
- record_loop_action integration: valid action persists and is retrievable
- Invalid action does not mutate state
- API module markers: action endpoints remain importable
"""

from __future__ import annotations

import unittest

from thinkbox.dashboard_state import (
    AutonomousLoopEntry,
    DashboardState,
    LoopActionEntry,
)
import thinkbox.dashboard_state as ds_mod


def _reset_dashboard() -> None:
    DashboardState._instance = None
    ds_mod._dashboard_state = None


class TestLoopActionTokenGate(unittest.TestCase):
    """Token extraction + action validation (pure helpers, no FastAPI needed)."""

    def test_token_from_x_governance_token_header(self) -> None:
        from backend.api.v1.autonomous_loop import extract_governance_token
        self.assertEqual(extract_governance_token(None, "tok_abc"), "tok_abc")

    def test_token_from_bearer_authorization(self) -> None:
        from backend.api.v1.autonomous_loop import extract_governance_token
        self.assertEqual(extract_governance_token("Bearer tok_xyz", None), "tok_xyz")

    def test_token_missing_when_both_absent(self) -> None:
        from backend.api.v1.autonomous_loop import extract_governance_token
        self.assertEqual(extract_governance_token(None, None), "")

    def test_token_missing_when_whitespace_only(self) -> None:
        from backend.api.v1.autonomous_loop import extract_governance_token
        self.assertEqual(extract_governance_token(None, "   "), "")
        self.assertEqual(extract_governance_token("Bearer    ", None), "")

    def test_token_header_takes_precedence_over_bearer(self) -> None:
        from backend.api.v1.autonomous_loop import extract_governance_token
        self.assertEqual(
            extract_governance_token("Bearer bearer_tok", "header_tok"), "header_tok"
        )

    def test_token_from_non_bearer_authorization_ignored(self) -> None:
        from backend.api.v1.autonomous_loop import extract_governance_token
        self.assertEqual(extract_governance_token("Basic u:p", None), "")

    def test_validate_each_allowed_action(self) -> None:
        from backend.api.v1.autonomous_loop import validate_loop_action
        for action in ("start", "stop", "run", "reset"):
            with self.subTest(action=action):
                self.assertTrue(validate_loop_action(action))

    def test_validate_rejects_unknown_action(self) -> None:
        from backend.api.v1.autonomous_loop import validate_loop_action
        self.assertFalse(validate_loop_action("delete"))
        self.assertFalse(validate_loop_action(""))

    def test_allowed_actions_constant(self) -> None:
        from backend.api.v1.autonomous_loop import ALLOWED_LOOP_ACTIONS
        self.assertEqual(ALLOWED_LOOP_ACTIONS, {"start", "stop", "run", "reset"})


class TestLoopActionPersistence(unittest.TestCase):
    """State-layer integration: recording actions through the dashboard state."""

    def setUp(self) -> None:
        _reset_dashboard()
        self.state = DashboardState()
        self.state.upsert_autonomous_loop(AutonomousLoopEntry(loop_id="loop_target"))

    def tearDown(self) -> None:
        _reset_dashboard()

    def test_record_returns_entry_and_updates_last_action(self) -> None:
        entry = self.state.record_loop_action("loop_target", "run", result={"n": 1})
        self.assertIsInstance(entry, LoopActionEntry)
        self.assertEqual(entry.loop_id, "loop_target")
        self.assertEqual(entry.action, "run")
        self.assertEqual(self.state.autonomous_loops["loop_target"].last_action, "run")

    def test_record_multiple_actions_retrievable_in_order(self) -> None:
        for action in ("start", "run", "stop"):
            self.state.record_loop_action("loop_target", action)
        actions = self.state.get_loop_actions("loop_target")
        self.assertEqual(len(actions), 3)
        self.assertEqual([a.action for a in actions], ["start", "run", "stop"])

    def test_record_unknown_loop_creates_placeholder_entry(self) -> None:
        self.state.record_loop_action("loop_new", "reset")
        self.assertIn("loop_new", self.state.autonomous_loops)
        self.assertEqual(self.state.get_loop_actions("loop_new")[0].action, "reset")

    def test_invalid_actions_do_not_mutate_state(self) -> None:
        from backend.api.v1.autonomous_loop import validate_loop_action
        self.assertFalse(validate_loop_action("delete"))
        self.assertEqual(self.state.get_loop_actions("loop_target"), [])

    def test_get_all_actions_aggregates_across_loops(self) -> None:
        self.state.upsert_autonomous_loop(AutonomousLoopEntry(loop_id="loop_other"))
        self.state.record_loop_action("loop_target", "start")
        self.state.record_loop_action("loop_other", "stop")
        self.assertEqual(len(self.state.get_all_loop_actions()), 2)


class TestActionApiModuleSurface(unittest.TestCase):
    """API module remains importable and exposes action helpers."""

    def test_module_exposes_action_helpers(self) -> None:
        import backend.api.v1.autonomous_loop as api_module
        self.assertTrue(hasattr(api_module, "extract_governance_token"))
        self.assertTrue(hasattr(api_module, "validate_loop_action"))
        self.assertTrue(hasattr(api_module, "ALLOWED_LOOP_ACTIONS"))
        self.assertTrue(hasattr(api_module, "get_autonomous_loop_status_payload"))

    def test_missing_token_detail_constant(self) -> None:
        from backend.api.v1.autonomous_loop import MISSING_TOKEN_DETAIL
        self.assertEqual(MISSING_TOKEN_DETAIL, "Missing governance token")


if __name__ == "__main__":
    unittest.main()
