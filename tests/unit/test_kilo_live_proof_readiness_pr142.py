"""Hermetic gates for PR #142 KILO env-matrix (gate ``env-matrix``)."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from thinkbox import kilo_env_matrix as matrix
from thinkbox import kilo_live_proof_readiness as spine

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestEnvMatrixGate(unittest.TestCase):
    def test_pr142_gate_id(self) -> None:
        gate = spine.gate_for_pr(142)
        self.assertIsNotNone(gate)
        assert gate is not None
        self.assertEqual(gate.gate_id, matrix.GATE_ID)

    def test_contract_count_minimum(self) -> None:
        contracts = matrix.list_contracts()
        self.assertGreaterEqual(len(contracts), 10)

    def test_hermetic_unit_clean_passes(self) -> None:
        env = matrix.minimal_hermetic_environ()
        result = matrix.evaluate_env_matrix(matrix.EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertTrue(result.ok, msg=result.violations)

    def test_forbidden_live_ack_fails(self) -> None:
        env = matrix.minimal_hermetic_environ({"THINKBOX_SWARM_LIVE_ACK": "1"})
        result = matrix.evaluate_env_matrix(matrix.EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertFalse(result.ok)
        codes = {v.code for v in result.violations}
        self.assertIn("forbidden_present", codes)

    def test_forbidden_claim_live_env_fails_operator(self) -> None:
        env = matrix.minimal_hermetic_environ({"THINKBOX_KILO_CLAIM_LIVE": "1"})
        result = matrix.hermetic_operator_check(env)
        self.assertFalse(result.ok)

    def test_provider_key_forbidden_in_hermetic_unit(self) -> None:
        env = matrix.minimal_hermetic_environ({"INCEPTION_API_KEY": "test-key"})
        result = matrix.evaluate_env_matrix(matrix.EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertFalse(result.ok)

    def test_loopback_mercury_ok_in_hermetic(self) -> None:
        env = matrix.minimal_hermetic_environ(
            {"THINKBOX_MERCURY_BASE_URL": "http://127.0.0.1:8001"}
        )
        result = matrix.evaluate_env_matrix(matrix.EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertTrue(result.ok, msg=result.violations)

    def test_public_mercury_fails_in_hermetic(self) -> None:
        env = matrix.minimal_hermetic_environ(
            {"THINKBOX_MERCURY_BASE_URL": "http://203.0.113.1:8001"}
        )
        result = matrix.evaluate_env_matrix(matrix.EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertFalse(result.ok)

    def test_mock_endpoint_token_ok(self) -> None:
        env = matrix.minimal_hermetic_environ(
            {"THINKBOX_PROVIDER_BASE_URL": "mock://mercury"}
        )
        result = matrix.evaluate_env_matrix(matrix.EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertTrue(result.ok, msg=result.violations)

    def test_live_proof_prep_missing_substrate(self) -> None:
        env = matrix.minimal_hermetic_environ()
        result = matrix.evaluate_env_matrix(matrix.EnvMatrixMode.LIVE_PROOF_PREP, env)
        self.assertFalse(result.ok)
        missing = [v for v in result.violations if v.code == "required_missing"]
        keys = {v.env_key for v in missing}
        self.assertIn("UPSTASH_PUBLIC_BOX_URL", keys)
        self.assertIn("UPSTASH_PUBLIC_BOX_TOKEN", keys)

    def test_live_proof_prep_complete_shape(self) -> None:
        env = matrix.minimal_hermetic_environ(
            {
                "UPSTASH_PUBLIC_BOX_URL": "https://example.preview.box.upstash.com",
                "UPSTASH_PUBLIC_BOX_TOKEN": "token",
            }
        )
        result = matrix.evaluate_env_matrix(matrix.EnvMatrixMode.LIVE_PROOF_PREP, env)
        self.assertTrue(result.ok, msg=result.violations)

    def test_detect_mode_ci(self) -> None:
        mode = matrix.detect_matrix_mode({"CI": "true"})
        self.assertEqual(mode, matrix.EnvMatrixMode.HERMETIC_CI)

    def test_summary_four_state_cap(self) -> None:
        summary = matrix.env_matrix_contract_summary(matrix.minimal_hermetic_environ())
        self.assertEqual(summary["four_state_max"], "TEST_VERIFIED")
        self.assertFalse(summary["live_proof_in_this_pr"])

    def test_gate_closed_hermetic_default(self) -> None:
        self.assertTrue(matrix.env_matrix_gate_closed())

    def test_forbidden_public_bind(self) -> None:
        env = matrix.minimal_hermetic_environ(
            {"THINKBOX_MERCURY_BASE_URL": "http://0.0.0.0:8001"}
        )
        result = matrix.evaluate_env_matrix(matrix.EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertFalse(result.ok)

    def test_production_ready_claim_forbidden(self) -> None:
        env = matrix.minimal_hermetic_environ({"THINKBOX_KILO_PRODUCTION_READY": "yes"})
        result = matrix.hermetic_operator_check(env)
        self.assertFalse(result.ok)

    def test_explicit_matrix_mode_override(self) -> None:
        mode = matrix.detect_matrix_mode(
            {"THINKBOX_KILO_MATRIX_MODE": "live_proof_prep"}
        )
        self.assertEqual(mode, matrix.EnvMatrixMode.LIVE_PROOF_PREP)

    def test_list_contracts_by_category(self) -> None:
        substrate = matrix.list_contracts(matrix.EnvCategory.SUBSTRATE)
        keys = {c.key for c in substrate}
        self.assertIn("UPSTASH_PUBLIC_BOX_URL", keys)

    def test_result_to_dict_serializable(self) -> None:
        env = matrix.minimal_hermetic_environ()
        result = matrix.evaluate_env_matrix(matrix.EnvMatrixMode.HERMETIC_UNIT, env)
        payload = result.to_dict()
        self.assertTrue(payload["ok"])
        json.dumps(payload)

    def test_operator_allows_provider_keys_in_ci(self) -> None:
        env = {
            "CI": "true",
            "INCEPTION_API_KEY": "present-but-not-used",
        }
        result = matrix.hermetic_operator_check(env)
        self.assertTrue(result.ok, msg=result.violations)


class TestSpineIntegration(unittest.TestCase):
    def test_spine_summary_includes_env_matrix(self) -> None:
        summary = spine.spine_contract_summary()
        self.assertIn("env_matrix", summary)
        block = summary["env_matrix"]
        assert isinstance(block, dict)
        self.assertEqual(block.get("gate_id"), matrix.GATE_ID)
        self.assertTrue(block.get("hermetic_operator_ok"))

    def test_runbook_mentions_env_matrix(self) -> None:
        text = spine.load_text(spine.runbook_path())
        self.assertIn("env-matrix", text)
        self.assertIn("verify_kilo_env_matrix", text)


class TestOperatorScripts(unittest.TestCase):
    def test_verify_env_matrix_script_exists(self) -> None:
        path = REPO_ROOT / "scripts" / "verify_kilo_env_matrix.py"
        self.assertTrue(path.is_file())

    def test_verify_env_matrix_exit_zero(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "verify_kilo_env_matrix.py")],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload.get("hermetic_operator_ok"))

    def test_verify_spine_includes_env_matrix(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "verify_kilo_spine.py")],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertIn("env_matrix", payload)

    def test_audit_checklist_pr142_exists(self) -> None:
        path = REPO_ROOT / "docs" / "audit" / "checklists" / "kilo-env-matrix-pr142.md"
        self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
