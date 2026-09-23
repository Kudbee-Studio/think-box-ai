"""Hermetic gates for PR #143 KILO substrate-checklist (gate ``substrate-checklist``)."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from thinkbox import kilo_env_matrix as matrix
from thinkbox import kilo_live_proof_readiness as spine
from thinkbox import kilo_substrate_checklist as substrate

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestSubstrateGate(unittest.TestCase):
    def test_pr143_gate_id(self) -> None:
        gate = spine.gate_for_pr(143)
        self.assertIsNotNone(gate)
        assert gate is not None
        self.assertEqual(gate.gate_id, substrate.GATE_ID)

    def test_hermetic_unit_clean_passes(self) -> None:
        env = substrate.minimal_substrate_hermetic_environ()
        result = substrate.evaluate_substrate_checklist(matrix.EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertTrue(result.ok, msg=result.violations)
        self.assertTrue(result.env_matrix_ok)

    def test_hermetic_mock_url_passes_env_matrix_layer(self) -> None:
        env = substrate.minimal_substrate_hermetic_environ(
            {"UPSTASH_PUBLIC_BOX_URL": "mock://box", "UPSTASH_PUBLIC_BOX_TOKEN": "mock_x"}
        )
        matrix_only = matrix.evaluate_env_matrix(matrix.EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertFalse(matrix_only.ok)
        result = substrate.evaluate_substrate_checklist(matrix.EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertTrue(result.ok, msg=result.violations)
        self.assertTrue(result.env_matrix_ok)

    def test_requires_env_matrix_layer(self) -> None:
        env = substrate.minimal_substrate_hermetic_environ(
            {"THINKBOX_SWARM_LIVE_ACK": "1"}
        )
        result = substrate.evaluate_substrate_checklist(matrix.EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertFalse(result.ok)
        self.assertFalse(result.env_matrix_ok)
        codes = {v.code for v in result.violations}
        self.assertTrue(any(c.startswith("env_matrix_") for c in codes))

    def test_forbidden_live_box_url_in_hermetic(self) -> None:
        env = substrate.minimal_substrate_hermetic_environ(
            {
                "UPSTASH_PUBLIC_BOX_URL": "https://wanted-tuna.preview.box.upstash.com",
                "UPSTASH_PUBLIC_BOX_TOKEN": "mock_token_ok",
            }
        )
        result = substrate.evaluate_substrate_checklist(matrix.EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertFalse(result.ok)

    def test_mock_url_ok_in_hermetic(self) -> None:
        env = substrate.minimal_substrate_hermetic_environ(
            {"UPSTASH_PUBLIC_BOX_URL": "mock://box", "UPSTASH_PUBLIC_BOX_TOKEN": "mock_x"}
        )
        result = substrate.evaluate_substrate_checklist(matrix.EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertTrue(result.ok, msg=result.violations)

    def test_loopback_box_url_ok(self) -> None:
        env = substrate.minimal_substrate_hermetic_environ(
            {
                "UPSTASH_PUBLIC_BOX_URL": "http://127.0.0.1:3000",
                "UPSTASH_PUBLIC_BOX_TOKEN": "hermetic_abc",
            }
        )
        result = substrate.evaluate_substrate_checklist(matrix.EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertTrue(result.ok, msg=result.violations)

    def test_placeholder_example_host_ok(self) -> None:
        env = substrate.minimal_substrate_hermetic_environ(
            {
                "UPSTASH_PUBLIC_BOX_URL": "https://example.preview.box.upstash.com",
                "UPSTASH_PUBLIC_BOX_TOKEN": "token",
            }
        )
        result = substrate.evaluate_substrate_checklist(matrix.EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertTrue(result.ok, msg=result.violations)

    def test_live_prep_missing_box(self) -> None:
        env = substrate.minimal_substrate_hermetic_environ()
        result = substrate.evaluate_substrate_checklist(matrix.EnvMatrixMode.LIVE_PROOF_PREP, env)
        self.assertFalse(result.ok)
        missing = [v for v in result.violations if v.code == "required_missing"]
        keys = {v.env_key for v in missing}
        self.assertIn(substrate.BOX_URL_ENV, keys)
        self.assertIn(substrate.BOX_TOKEN_ENV, keys)

    def test_live_prep_complete_shape(self) -> None:
        env = substrate.minimal_substrate_hermetic_environ(
            {
                "UPSTASH_PUBLIC_BOX_URL": "https://wanted-tuna-71803.preview.box.upstash.com",
                "UPSTASH_PUBLIC_BOX_TOKEN": "abcdefghijklmnop",
            }
        )
        result = substrate.evaluate_substrate_checklist(matrix.EnvMatrixMode.LIVE_PROOF_PREP, env)
        self.assertTrue(result.ok, msg=result.violations)

    def test_live_prep_rejects_short_token(self) -> None:
        env = substrate.minimal_substrate_hermetic_environ(
            {
                "UPSTASH_PUBLIC_BOX_URL": "https://wanted-tuna-71803.preview.box.upstash.com",
                "UPSTASH_PUBLIC_BOX_TOKEN": "short",
            }
        )
        result = substrate.evaluate_substrate_checklist(matrix.EnvMatrixMode.LIVE_PROOF_PREP, env)
        self.assertFalse(result.ok)

    def test_live_prep_rejects_http_box_url(self) -> None:
        env = substrate.minimal_substrate_hermetic_environ(
            {
                "UPSTASH_PUBLIC_BOX_URL": "http://wanted-tuna.preview.box.upstash.com",
                "UPSTASH_PUBLIC_BOX_TOKEN": "abcdefghijklmnop",
            }
        )
        result = substrate.evaluate_substrate_checklist(matrix.EnvMatrixMode.LIVE_PROOF_PREP, env)
        self.assertFalse(result.ok)

    def test_redact_token_masks_live_secret(self) -> None:
        redacted = substrate.redact_box_token("supersecretvalue")
        self.assertNotIn("supersecretvalue", redacted)
        self.assertIn("***", redacted)

    def test_redact_token_preserves_mock_literal(self) -> None:
        self.assertEqual(substrate.redact_box_token("mock_abc"), "mock_abc")

    def test_redact_url_host_only(self) -> None:
        redacted = substrate.redact_box_url(
            "https://wanted-tuna-71803.preview.box.upstash.com/path?q=1"
        )
        self.assertIn("wanted-tuna", redacted)
        self.assertNotIn("q=1", redacted)

    def test_summary_four_state_cap(self) -> None:
        summary = substrate.substrate_checklist_contract_summary(
            substrate.minimal_substrate_hermetic_environ()
        )
        self.assertEqual(summary["four_state_max"], "TEST_VERIFIED")
        self.assertFalse(summary["live_proof_in_this_pr"])
        self.assertTrue(summary["env_matrix_layer"])

    def test_gate_closed_hermetic_default(self) -> None:
        self.assertTrue(substrate.substrate_checklist_gate_closed())

    def test_operator_check_passes_clean(self) -> None:
        result = substrate.hermetic_substrate_operator_check(
            substrate.minimal_substrate_hermetic_environ()
        )
        self.assertTrue(result.ok, msg=result.violations)

    def test_result_to_dict_serializable(self) -> None:
        env = substrate.minimal_substrate_hermetic_environ()
        result = substrate.evaluate_substrate_checklist(matrix.EnvMatrixMode.HERMETIC_UNIT, env)
        payload = result.to_dict()
        self.assertTrue(payload["ok"])
        json.dumps(payload)

    def test_is_live_box_url_positive(self) -> None:
        self.assertTrue(
            substrate.is_live_box_url("https://wanted-tuna-71803.preview.box.upstash.com")
        )

    def test_is_live_box_url_rejects_loopback(self) -> None:
        self.assertFalse(substrate.is_live_box_url("https://127.0.0.1/box"))

    def test_production_pair_blocked_in_ci(self) -> None:
        env = {
            "CI": "true",
            "THINKBOX_KILO_MATRIX_MODE": matrix.EnvMatrixMode.HERMETIC_CI.value,
            "UPSTASH_PUBLIC_BOX_URL": "https://prod-id.preview.box.upstash.com",
            "UPSTASH_PUBLIC_BOX_TOKEN": "1234567890abcdef",
        }
        result = substrate.hermetic_substrate_operator_check(env)
        self.assertFalse(result.ok)


class TestSpineIntegration(unittest.TestCase):
    def test_spine_summary_includes_substrate(self) -> None:
        summary = spine.spine_contract_summary()
        self.assertIn("substrate_checklist", summary)
        block = summary["substrate_checklist"]
        assert isinstance(block, dict)
        self.assertEqual(block.get("gate_id"), substrate.GATE_ID)
        self.assertTrue(block.get("hermetic_operator_ok"))

    def test_spine_pr143_gate_id(self) -> None:
        summary = spine.spine_contract_summary()
        self.assertEqual(summary.get("pr143_gate_id"), substrate.GATE_ID)

    def test_runbook_mentions_substrate_checklist(self) -> None:
        text = spine.load_text(spine.runbook_path())
        self.assertIn("substrate-checklist", text)
        self.assertIn("verify_kilo_substrate_checklist", text)


class TestOperatorScripts(unittest.TestCase):
    def test_verify_substrate_script_exists(self) -> None:
        path = REPO_ROOT / "scripts" / "verify_kilo_substrate_checklist.py"
        self.assertTrue(path.is_file())

    def test_verify_substrate_exit_zero(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "verify_kilo_substrate_checklist.py"),
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload.get("hermetic_operator_ok"))

    def test_verify_spine_includes_substrate(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "verify_kilo_spine.py")],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertIn("substrate_checklist", payload)

    def test_audit_checklist_pr143_exists(self) -> None:
        path = REPO_ROOT / "docs" / "audit" / "checklists" / "kilo-substrate-checklist-pr143.md"
        self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
