"""Hermetic gates for PR #155 receipt-chain-etag."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_receipt_chain_etag as rce
from thinkbox.kilo_live_proof_readiness import spine_contract_summary

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestReceiptChainEtagGate(unittest.TestCase):
    def test_pr155_gate_id(self) -> None:
        self.assertEqual(rce.GATE_ID, "receipt-chain-etag")
        self.assertEqual(rce.PR_NUMBER, 155)

    def test_hermetic_eval_passes(self) -> None:
        env = rce.minimal_receipt_chain_etag_environ()
        result = rce.evaluate_receipt_chain_etag(
            __import__("thinkbox.kilo_env_matrix", fromlist=["EnvMatrixMode"]).EnvMatrixMode.HERMETIC_UNIT,
            env,
        )
        self.assertTrue(result.ok, msg=result.violations)

    def test_spine_summary_includes_block(self) -> None:
        summary = spine_contract_summary()
        block = summary.get("receipt_chain_etag") or {}
        self.assertEqual(block.get("gate_id"), rce.GATE_ID)
        self.assertTrue(block.get("hermetic_operator_ok"))
        self.assertEqual(summary.get("pr155_gate_id"), rce.GATE_ID)

    def test_verify_script_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_receipt_chain_etag.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_checklist_live_verified_false(self) -> None:
        doc = json.loads((REPO_ROOT / rce.CHECKLIST_REL).read_text(encoding="utf-8"))
        self.assertFalse(doc["live_verified"])


if __name__ == "__main__":
    unittest.main()
