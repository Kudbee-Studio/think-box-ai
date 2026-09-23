"""Hermetic gates for PR #161 END LINK API / ops harden."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_end_link_api_ops_harden as ops_gate
from thinkbox.kilo_live_proof_readiness import spine_contract_summary

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestEndLinkApiOpsHardenSpine(unittest.TestCase):
    def test_pr161_gate_id(self) -> None:
        self.assertEqual(ops_gate.GATE_ID, "end-link-api-ops-harden")
        self.assertEqual(ops_gate.PR_NUMBER, 161)

    def test_spine_summary_includes_block(self) -> None:
        summary = spine_contract_summary()
        block = summary.get("end_link_api_ops_harden") or {}
        self.assertEqual(block.get("gate_id"), ops_gate.GATE_ID)
        self.assertTrue(block.get("hermetic_operator_ok"))
        self.assertEqual(summary.get("pr161_gate_id"), ops_gate.GATE_ID)
        self.assertFalse(block.get("live_verified", True))

    def test_verify_script_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_end_link_api_ops_harden.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        body = json.loads(proc.stdout)
        self.assertFalse(body.get("live_verified", True))
        self.assertFalse(body.get("live_api_called", True))

    def test_pr161_audit_pass_honesty(self) -> None:
        path = REPO_ROOT / "docs/audit/passes/2026-09-23-pr161.json"
        body = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(body["live_verified"])
        self.assertFalse(body["live_api_called"])
        self.assertEqual(body["gate_id"], ops_gate.GATE_ID)


if __name__ == "__main__":
    unittest.main()
