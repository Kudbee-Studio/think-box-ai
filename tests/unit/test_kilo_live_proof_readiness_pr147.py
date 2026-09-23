"""Hermetic gates for PR #147 KILO swarm-instrumentation (gate ``swarm-instrumentation``)."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from thinkbox import kilo_live_proof_readiness as spine
from thinkbox import kilo_mercury_hermetic as mercury
from thinkbox import kilo_swarm_instrumentation as swarm
from thinkbox.kilo_env_matrix import EnvMatrixMode
from thinkbox.swarm_instrumentation_checks import (
    HERMETIC_INSTRUMENTATION_CHECK_COUNT,
    run_hermetic_instrumentation_checks,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestSwarmGate(unittest.TestCase):
    def test_pr147_gate_id(self) -> None:
        gate = spine.gate_for_pr(147)
        self.assertIsNotNone(gate)
        assert gate is not None
        self.assertEqual(gate.gate_id, swarm.GATE_ID)
        self.assertEqual(swarm.PR_NUMBER, 147)

    def test_arc_includes_swarm_instrumentation(self) -> None:
        self.assertIn("swarm-instrumentation", spine.gate_ids())

    def test_catalog_has_eleven_entries(self) -> None:
        catalog = swarm.swarm_instrumentation_catalog()
        self.assertEqual(len(catalog), swarm.EXPECTED_INSTRUMENTATION_CATALOG_SIZE)
        self.assertEqual(catalog[-1]["check_id"], "inst-11")

    def test_hermetic_unit_passes_clean_env(self) -> None:
        env = swarm.minimal_swarm_instrumentation_environ()
        result = swarm.evaluate_swarm_instrumentation(EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertTrue(result.ok, msg=result.violations)
        self.assertTrue(result.mercury_hermetic_ok)
        assert result.evidence is not None
        self.assertFalse(result.evidence.live_api_called)
        self.assertFalse(result.evidence.live_swarm_invoked)
        self.assertEqual(result.passed_count, HERMETIC_INSTRUMENTATION_CHECK_COUNT)

    def test_live_swarm_invoked_denied(self) -> None:
        env = swarm.minimal_swarm_instrumentation_environ()
        result = swarm.evaluate_swarm_instrumentation(
            EnvMatrixMode.HERMETIC_UNIT,
            env,
            live_swarm_invoked=True,
        )
        self.assertFalse(result.ok)
        codes = {v.code for v in result.violations}
        self.assertIn("live_swarm_forbidden", codes)

    def test_requires_mercury_layer(self) -> None:
        from thinkbox.kilo_governance_evidence import minimal_governance_hermetic_environ

        env = minimal_governance_hermetic_environ(
            {"INCEPTION_API_KEY": "sk-live-production-shaped-key"}
        )
        result = swarm.evaluate_swarm_instrumentation(EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertFalse(result.ok)
        self.assertFalse(result.mercury_hermetic_ok)


class TestInstrumentationChecks(unittest.TestCase):
    def test_ten_hermetic_checks_pass(self) -> None:
        results = run_hermetic_instrumentation_checks()
        self.assertEqual(len(results), HERMETIC_INSTRUMENTATION_CHECK_COUNT)
        self.assertTrue(all(r.ok for r in results), msg=[r for r in results if not r.ok])

    def test_gate_contract_ok(self) -> None:
        ok, detail = swarm.gate_contract_check(live_swarm_invoked=False)
        self.assertTrue(ok, msg=detail)

    def test_gate_contract_rejects_live(self) -> None:
        ok, _detail = swarm.gate_contract_check(live_swarm_invoked=True)
        self.assertFalse(ok)

    def test_verifier_script_path(self) -> None:
        path = swarm.experiments_verify_script_path()
        self.assertTrue(path.is_file())
        self.assertEqual(path.name, "verify_instrumentation.py")


class TestOperatorAndSummary(unittest.TestCase):
    def test_hermetic_operator_ok_clean_env(self) -> None:
        env = swarm.minimal_swarm_instrumentation_environ()
        op = swarm.hermetic_swarm_operator_check(env)
        self.assertTrue(op.ok, msg=op.violations)

    def test_forbidden_provider_without_mock(self) -> None:
        env = swarm.minimal_swarm_instrumentation_environ()
        env = dict(env)
        env.pop("THINKBOX_KILO_MERCURY_MOCK", None)
        env.pop("THINKBOX_MERCURY_BASE_URL", None)
        env["INCEPTION_API_KEY"] = "sk-live-production-shaped-key"
        op = swarm.hermetic_swarm_operator_check(env)
        self.assertFalse(op.ok)

    def test_contract_summary_redacted(self) -> None:
        summary = swarm.swarm_instrumentation_contract_summary(
            {"INCEPTION_API_KEY": "must-not-appear-in-summary"}
        )
        dumped = json.dumps(summary)
        self.assertNotIn("must-not-appear-in-summary", dumped)
        self.assertEqual(summary["gate_id"], swarm.GATE_ID)
        self.assertFalse(summary["live_api_called"])
        self.assertFalse(summary["live_swarm_invoked"])

    def test_gate_closed_default(self) -> None:
        self.assertTrue(swarm.swarm_instrumentation_gate_closed())

    def test_spine_summary_includes_pr147(self) -> None:
        summary = spine.spine_contract_summary()

