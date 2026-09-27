"""Hermetic gates for PR #157 API / ops harden."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_api_ops_harden as harden
from thinkbox.kilo_live_proof_readiness import spine_contract_summary

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestApiOpsHardenGate(unittest.TestCase):
    def test_pr157_gate_id(self) -> None:
        self.assertEqual(harden.GATE_ID, "api-ops-harden")
        self.assertEqual(harden.PR_NUMBER, 157)

    def test_hermetic_eval_passes(self) -> None:
        from thinkbox.kilo_env_matrix import EnvMatrixMode

        env = harden.minimal_api_ops_harden_environ()
        result = harden.evaluate_api_ops_harden(EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertTrue(result.ok, msg=result.violations)

    def test_spine_summary_includes_block(self) -> None:
        summary = spine_contract_summary()
        block = summary.get("api_ops_harden") or {}
        self.assertEqual(block.get("gate_id"), harden.GATE_ID)
        self.assertTrue(block.get("hermetic_operator_ok"))
        self.assertEqual(summary.get("pr157_gate_id"), harden.GATE_ID)

    def test_verify_script_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_api_ops_harden.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_checklist_live_verified_false(self) -> None:
        doc = json.loads((REPO_ROOT / harden.CHECKLIST_REL).read_text(encoding="utf-8"))
        self.assertFalse(doc["live_verified"])
        self.assertEqual(doc["ops_harden"], "api-ops-harden")


if __name__ == "__main__":
    unittest.main()
