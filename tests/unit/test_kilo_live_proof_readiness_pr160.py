"""Hermetic gates for PR #160 receipt-chain / END_LINK docs + audit pack."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_receipt_chain_end_link_docs as docs_gate
from thinkbox.kilo_live_proof_readiness import spine_contract_summary

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestReceiptChainEndLinkDocsSpine(unittest.TestCase):
    def test_pr160_gate_id(self) -> None:
        self.assertEqual(docs_gate.GATE_ID, "receipt-chain-end-link-docs")
        self.assertEqual(docs_gate.PR_NUMBER, 160)

    def test_spine_summary_includes_block(self) -> None:
        summary = spine_contract_summary()
        block = summary.get("receipt_chain_end_link_docs") or {}
        self.assertEqual(block.get("gate_id"), docs_gate.GATE_ID)
        self.assertTrue(block.get("hermetic_operator_ok"))
        self.assertEqual(summary.get("pr160_gate_id"), docs_gate.GATE_ID)
        self.assertFalse(block.get("live_verified", True))

    def test_verify_script_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_receipt_chain_end_link_docs.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        body = json.loads(proc.stdout)
        self.assertFalse(body.get("live_verified", True))
        self.assertFalse(body.get("live_api_called", True))

    def test_pr160_audit_pass_honesty(self) -> None:
        path = REPO_ROOT / "docs/audit/passes/2026-09-23-pr160.json"
        body = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(body["live_verified"])
        self.assertFalse(body["live_api_called"])
        self.assertEqual(body["gate_id"], docs_gate.GATE_ID)


if __name__ == "__main__":
    unittest.main()
