"""Hermetic gates for PR #169 combined post-#168 lane."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_pr169_combined_post168_lane as pr169
from thinkbox.kilo_live_proof_readiness import spine_contract_summary

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestPr169CombinedPost168Lane(unittest.TestCase):
    def test_pr169_gate_id(self) -> None:
        self.assertEqual(pr169.GATE_ID, "pr169-combined-post168-lane")
        self.assertEqual(pr169.PR_NUMBER, 169)

    def test_spine_summary_includes_pr169(self) -> None:
        summary = spine_contract_summary(fast=True)
        block = summary.get("pr169_combined_post168_lane") or {}
        self.assertEqual(block.get("gate_id"), pr169.GATE_ID)
        self.assertTrue(block.get("hermetic_operator_ok"))
        self.assertEqual(summary.get("pr169_gate_id"), pr169.GATE_ID)
        self.assertFalse(block.get("live_verified", True))
        self.assertFalse(block.get("live_api_called", True))
        e2e_block = summary.get("control_plane_e2e_deepen") or {}
        self.assertTrue(e2e_block.get("e2e_unittest_skipped_default"))

    def test_verify_umbrella_script_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_pr169_combined_post168_lane.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        body = json.loads(proc.stdout)
        self.assertFalse(body.get("live_verified", True))
        self.assertFalse(body.get("live_api_called", True))

    def test_pr169_audit_pass_honesty(self) -> None:
        path = REPO_ROOT / "docs/audit/passes/2026-09-23-pr169.json"
        body = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(body["live_verified"])
        self.assertFalse(body["live_api_called"])
        self.assertEqual(body["gate_id"], pr169.GATE_ID)

    def test_theme_verify_scripts(self) -> None:
        for script in (
            "scripts/verify_kilo_live_proof_operator_audit_flip_post168.py",
            "scripts/verify_kilo_api_ops_harden_post168.py",
            "scripts/verify_kilo_dashboard_pr168_gates_bind.py",
            "scripts/verify_kilo_swarm_governance_post168_deepen.py",
        ):
            proc = subprocess.run(
                ["python3", script],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=script + proc.stderr)


if __name__ == "__main__":
    unittest.main()
