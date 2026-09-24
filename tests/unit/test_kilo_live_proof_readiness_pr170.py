"""Hermetic gates for PR #170 beyond-KILO lint lane."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_beyond_kilo_lint as pr170
from thinkbox.kilo_live_proof_readiness import spine_contract_summary

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestPr170BeyondKiloLintLane(unittest.TestCase):
    def test_pr170_gate_id(self) -> None:
        self.assertEqual(pr170.GATE_ID, "beyond-kilo-lint-readiness")
        self.assertEqual(pr170.PR_NUMBER, 170)

    def test_spine_summary_includes_pr170(self) -> None:
        summary = spine_contract_summary(fast=True)
        block = summary.get("beyond_kilo_lint_readiness") or {}
        self.assertEqual(block.get("gate_id"), pr170.GATE_ID)
        self.assertTrue(block.get("hermetic_operator_ok"))
        self.assertEqual(summary.get("pr170_gate_id"), pr170.GATE_ID)
        self.assertFalse(block.get("live_verified", True))
        self.assertFalse(block.get("live_api_called", True))
        e2e_block = summary.get("control_plane_e2e_deepen") or {}
        self.assertTrue(e2e_block.get("e2e_unittest_skipped_default"))

    def test_verify_script_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_beyond_kilo_lint.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        body = json.loads(proc.stdout)
        self.assertFalse(body.get("live_verified", True))
        self.assertFalse(body.get("live_api_called", True))

    def test_pr170_audit_pass_honesty(self) -> None:
        path = REPO_ROOT / "docs/audit/passes/2026-09-23-pr170.json"
        body = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(body["live_verified"])
        self.assertFalse(body["live_api_called"])
        self.assertEqual(body["gate_id"], pr170.GATE_ID)


if __name__ == "__main__":
    unittest.main()
