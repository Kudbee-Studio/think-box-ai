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
        self.assertEqual(summary.get("pr147_gate_id"), swarm.GATE_ID)
        block = summary.get("swarm_instrumentation")
        self.assertIsInstance(block, dict)
        assert isinstance(block, dict)
        self.assertTrue(block.get("hermetic_operator_ok"))
        self.assertTrue(block.get("eleven_of_eleven_hermetic"))

    def test_eleven_of_eleven_flag(self) -> None:
        summary = swarm.swarm_instrumentation_contract_summary(
            swarm.minimal_swarm_instrumentation_environ()
        )
        self.assertTrue(summary["eleven_of_eleven_hermetic"])
        self.assertEqual(summary["instrumentation_catalog_size"], 11)


class TestRunbookAndDocs(unittest.TestCase):
    def test_runbook_swarm_section(self) -> None:
        text = spine.load_text(spine.runbook_path())
        self.assertIn("swarm-instrumentation", text)
        self.assertIn("PR #147", text)

    def test_runbook_h11_prerequisite(self) -> None:
        text = spine.load_text(spine.runbook_path())
        self.assertIn("verify_kilo_swarm_instrumentation", text)

    def test_arc_doc_pr147_theme(self) -> None:
        text = spine.load_text(spine.arc_doc_path())
        self.assertIn("swarm-instrumentation", text)
        self.assertIn("#147", text)

    def test_no_forbidden_literals_in_swarm_module_doc(self) -> None:
        self.assertEqual(spine.find_forbidden_literal_claims(swarm.__doc__ or ""), [])


class TestVerifyScripts(unittest.TestCase):
    def test_verify_swarm_script_exists(self) -> None:
        path = REPO_ROOT / "scripts" / "verify_kilo_swarm_instrumentation.py"
        self.assertTrue(path.is_file())

    def test_verify_swarm_exit_zero(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "verify_kilo_swarm_instrumentation.py")],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

    def test_verify_spine_still_exit_zero(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "verify_kilo_spine.py")],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

    def test_experiments_verify_hermetic_ten_of_ten(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "experiments" / "verify_instrumentation.py")],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout)
        self.assertIn("10/10 checks passed", proc.stdout)


class TestAuditArtifacts(unittest.TestCase):
    def test_audit_checklist_pr147_exists(self) -> None:
        path = REPO_ROOT / "docs/audit/checklists/kilo-swarm-instrumentation-pr147.md"
        self.assertTrue(path.is_file())

    def test_audit_pass_pr147_live_verified_false(self) -> None:
        path = REPO_ROOT / "docs/audit/passes/2026-09-23-pr147.json"
        self.assertTrue(path.is_file())
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(data["four_state"]["live_verified"])


class TestEvidenceSerialization(unittest.TestCase):
    def test_evidence_to_dict_no_live_flags(self) -> None:
        env = swarm.minimal_swarm_instrumentation_environ()
        result = swarm.evaluate_swarm_instrumentation(EnvMatrixMode.HERMETIC_UNIT, env)
        payload = json.dumps(result.to_dict())
        self.assertIn("swarm-instrumentation", payload)
        self.assertIn('"live_api_called": false', payload)
        self.assertNotIn("KILO LIVE VERIFIED", payload)

    def test_instrumentation_results_shape(self) -> None:
        env = swarm.minimal_swarm_instrumentation_environ()
        result = swarm.evaluate_swarm_instrumentation(EnvMatrixMode.HERMETIC_UNIT, env)
        assert result.evidence is not None
        self.assertEqual(len(result.evidence.instrumentation_results), 10)

    def test_redact_swarm_summary(self) -> None:
        text = swarm.redact_swarm_summary('{"INCEPTION_API_KEY": "secret"}')
        self.assertNotIn("secret", text)

    def test_prep_mode_without_running_checks(self) -> None:
        env = swarm.minimal_swarm_instrumentation_environ()
        prep = swarm.evaluate_swarm_instrumentation(
            EnvMatrixMode.LIVE_PROOF_PREP,
            env,
            run_instrumentation=False,
        )
        self.assertEqual(prep.passed_count, 0)
        self.assertTrue(prep.mercury_hermetic_ok)


class TestFourStateHonesty(unittest.TestCase):
    def test_summary_four_state_cap(self) -> None:
        summary = swarm.swarm_instrumentation_contract_summary()
        self.assertEqual(summary["four_state_max"], "TEST_VERIFIED")
        self.assertFalse(summary["live_proof_in_this_pr"])

    def test_result_four_state_cap(self) -> None:
        env = swarm.minimal_swarm_instrumentation_environ()
        result = swarm.evaluate_swarm_instrumentation(EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertEqual(result.to_dict()["four_state_max"], "TEST_VERIFIED")


if __name__ == "__main__":
    unittest.main()
