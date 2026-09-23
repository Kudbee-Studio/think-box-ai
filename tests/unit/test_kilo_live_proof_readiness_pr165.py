"""Hermetic gates for PR #165 combined harden + era chronicle."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_pr165_combined_harden_era_chronicle as pr165
from thinkbox.kilo_live_proof_readiness import spine_contract_summary

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestPr165CombinedHardenSpine(unittest.TestCase):
    def test_pr165_gate_id(self) -> None:
        self.assertEqual(pr165.GATE_ID, "pr165-combined-harden-era-chronicle")
        self.assertEqual(pr165.PR_NUMBER, 165)

    def test_spine_summary_includes_pr165(self) -> None:
        summary = spine_contract_summary()
        block = summary.get("pr165_combined_harden_era_chronicle") or {}
        self.assertEqual(block.get("gate_id"), pr165.GATE_ID)
        self.assertTrue(block.get("hermetic_operator_ok"))
        self.assertEqual(summary.get("pr165_gate_id"), pr165.GATE_ID)
        self.assertFalse(block.get("live_verified", True))
        self.assertFalse(block.get("live_api_called", True))

    def test_verify_umbrella_script_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_pr165_combined_harden.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        body = json.loads(proc.stdout)
        self.assertFalse(body.get("live_verified", True))
        self.assertFalse(body.get("live_api_called", True))

    def test_pr165_audit_pass_honesty(self) -> None:
        path = REPO_ROOT / "docs/audit/passes/2026-09-23-pr165.json"
        body = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(body["live_verified"])
        self.assertFalse(body["live_api_called"])
        self.assertEqual(body["gate_id"], pr165.GATE_ID)

    def test_theme_verify_scripts(self) -> None:
        for script in (
            "scripts/verify_kilo_live_smoke_audit_flip_harden.py",
            "scripts/verify_kilo_control_plane_post164_deepen.py",
            "scripts/verify_kilo_receipt_chain_end_link_season_harden.py",
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
