"""Unit tests for ``backend.api.v1.run_governed`` (hermetic, no HTTP)."""

from __future__ import annotations

import unittest

from fastapi import HTTPException

from backend.api.v1.run_governed import (
    DEFAULT_RUN_CAPABILITY,
    DEFAULT_VERIFIED_CAPABILITY,
    governance_status_snapshot,
    parse_run_admission,
    reset_api_run_governance_for_tests,
    require_http_admission,
    validate_verified_subtasks,
)
from thinkbox.engine import EngineConfig, ThinkBoxEngine


class TestValidateVerifiedSubtasks(unittest.TestCase):
    def test_empty_subtasks_raises_422(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            validate_verified_subtasks([])
        self.assertEqual(ctx.exception.status_code, 422)

    def test_missing_family_raises_422(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            validate_verified_subtasks([{"description": "x", "spec": {}}])
        self.assertEqual(ctx.exception.detail["error"], "invalid_subtask_shape")


class TestParseRunAdmission(unittest.TestCase):
    def test_header_capability_wins_when_body_empty(self) -> None:
        ctx = parse_run_admission(
            agent_id="a",
            governance_token="t",
            header_token=None,
            header_capability="goal:execute",
            capability=None,
            verified=False,
            subtasks=None,
        )
        self.assertEqual(ctx.capability, "goal:execute")


class TestRequireHttpAdmission(unittest.TestCase):
    def test_valid_token_admits(self) -> None:
        gov = reset_api_run_governance_for_tests()
        token = gov.register_agent("unit-agent", [DEFAULT_RUN_CAPABILITY])
        ctx = parse_run_admission(
            agent_id="unit-agent",
            governance_token=token,
            header_token=None,
            header_capability=None,
            capability=None,
            verified=False,
            subtasks=None,
        )
        decision = require_http_admission(ctx)
        self.assertTrue(decision.allowed)

    def test_governance_status_after_registration(self) -> None:
        reset_api_run_governance_for_tests()
        gov = reset_api_run_governance_for_tests()
        gov.register_agent("status-agent", [DEFAULT_VERIFIED_CAPABILITY])
        snap = governance_status_snapshot()
        self.assertGreaterEqual(snap["identities_registered"], 1)
        self.assertTrue(snap["ledger_verified"])


class TestAdmissionGovernedShell(unittest.TestCase):
    def test_admission_shell_reused(self) -> None:
        gov = reset_api_run_governance_for_tests()
        first = gov.admission_governed()
        second = gov.admission_governed()
        self.assertIs(first, second)
        probe = gov.build_governed_engine(ThinkBoxEngine(EngineConfig()))
        self.assertIsNot(probe, first)


if __name__ == "__main__":
    unittest.main()
