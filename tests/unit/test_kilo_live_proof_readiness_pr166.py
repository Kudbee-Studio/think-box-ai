"""Hermetic gates for PR #166 combined post-#165 lane."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_pr166_combined_post165_lane as pr166
from thinkbox.kilo_live_proof_readiness import spine_contract_summary

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestPr166CombinedPost165Lane(unittest.TestCase):
    def test_pr166_gate_id(self) -> None:
        self.assertEqual(pr166.GATE_ID, "pr166-combined-post165-lane")
        self.assertEqual(pr166.PR_NUMBER, 166)

    def test_spine_summary_includes_pr166(self) -> None:
        summary = spine_contract_summary()
        block = summary.get("pr166_combined_post165_lane") or {}
        self.assertEqual(block.get("gate_id"), pr166.GATE_ID)
        self.assertTrue(block.get("hermetic_operator_ok"))
        self.assertEqual(summary.get("pr166_gate_id"), pr166.GATE_ID)
        self.assertFalse(block.get("live_verified", True))
        self.assertFalse(block.get("live_api_called", True))

    def test_verify_umbrella_script_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_pr166_combined_post165_lane.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        body = json.loads(proc.stdout)
        self.assertFalse(body.get("live_verified", True))
        self.assertFalse(body.get("live_api_called", True))

    def test_pr166_audit_pass_honesty(self) -> None:
        path = REPO_ROOT / "docs/audit/passes/2026-09-23-pr166.json"
        body = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(body["live_verified"])
        self.assertFalse(body["live_api_called"])
        self.assertEqual(body["gate_id"], pr166.GATE_ID)

    def test_theme_verify_scripts(self) -> None:
        for script in (
            "scripts/verify_kilo_live_proof_operator_prep_deepen.py",
            "scripts/verify_kilo_api_ops_harden_post165.py",
            "scripts/verify_kilo_dashboard_pr165_gates_bind.py",
            "scripts/verify_kilo_swarm_governance_post165_deepen.py",
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
