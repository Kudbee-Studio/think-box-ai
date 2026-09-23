"""Hermetic gates for PR #162 receipt-chain / END_LINK era audit close."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_receipt_chain_end_link_era_close as era_gate
from thinkbox.kilo_live_proof_readiness import spine_contract_summary

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestReceiptChainEndLinkEraCloseSpine(unittest.TestCase):
    def test_pr162_gate_id(self) -> None:
        self.assertEqual(era_gate.GATE_ID, "receipt-chain-end-link-era-close")
        self.assertEqual(era_gate.PR_NUMBER, 162)

    def test_spine_summary_includes_block(self) -> None:
        summary = spine_contract_summary()
        block = summary.get("receipt_chain_end_link_era_close") or {}
        self.assertEqual(block.get("gate_id"), era_gate.GATE_ID)
        self.assertTrue(block.get("hermetic_operator_ok"))
        self.assertEqual(summary.get("pr162_gate_id"), era_gate.GATE_ID)
        self.assertFalse(block.get("live_verified", True))

    def test_verify_script_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_receipt_chain_end_link_era_close.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        body = json.loads(proc.stdout)
        self.assertFalse(body.get("live_verified", True))

    def test_pr162_audit_pass_honesty(self) -> None:
        path = REPO_ROOT / "docs/audit/passes/2026-09-23-pr162.json"
        body = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(body["live_verified"])
        self.assertFalse(body["live_api_called"])


if __name__ == "__main__":
    unittest.main()
