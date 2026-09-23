"""Hermetic gates for PR #156 dashboard receipt-chain bind."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_dashboard_receipt_chain_bind as bind
from thinkbox.kilo_live_proof_readiness import spine_contract_summary

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestDashboardReceiptChainBindGate(unittest.TestCase):
    def test_pr156_gate_id(self) -> None:
        self.assertEqual(bind.GATE_ID, "dashboard-receipt-chain-bind")
        self.assertEqual(bind.PR_NUMBER, 156)

    def test_hermetic_eval_passes(self) -> None:
        from thinkbox.kilo_env_matrix import EnvMatrixMode

        env = bind.minimal_dashboard_receipt_chain_bind_environ()
        result = bind.evaluate_dashboard_receipt_chain_bind(EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertTrue(result.ok, msg=result.violations)

    def test_spine_summary_includes_block(self) -> None:
        summary = spine_contract_summary()
        block = summary.get("dashboard_receipt_chain_bind") or {}
        self.assertEqual(block.get("gate_id"), bind.GATE_ID)
        self.assertTrue(block.get("hermetic_operator_ok"))
        self.assertEqual(summary.get("pr156_gate_id"), bind.GATE_ID)

    def test_verify_script_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_dashboard_receipt_chain_bind.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_checklist_live_verified_false(self) -> None:
        doc = json.loads((REPO_ROOT / bind.CHECKLIST_REL).read_text(encoding="utf-8"))
        self.assertFalse(doc["live_verified"])
        self.assertEqual(doc["end_link_api"], "END_LINK")


if __name__ == "__main__":
    unittest.main()
