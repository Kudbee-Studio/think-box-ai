"""Hermetic gates for PR #172 CI spine-trust slimming (single-theme)."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_post_season_harden as psh
from thinkbox import kilo_pr172_ci_spine_trust as pr172
from thinkbox.kilo_live_proof_readiness import spine_contract_summary

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestPr172CiSpineTrustLane(unittest.TestCase):
    def test_pr172_gate_id(self) -> None:
        self.assertEqual(pr172.GATE_ID, "ci-spine-trust")
        self.assertEqual(pr172.PR_NUMBER, 172)

    def test_ci_workflow_manifest_pr172(self) -> None:
        text = (REPO_ROOT / pr172.CI_WORKFLOW_REL).read_text(encoding="utf-8")
        ok, violations = pr172.validate_pr172_ci_workflow_manifest(text)
        self.assertTrue(ok, msg=violations)

    def test_post_season_ci_manifest_delegates_pr172(self) -> None:
        text = (REPO_ROOT / psh.CI_WORKFLOW_REL).read_text(encoding="utf-8")
        ok, violations = psh.validate_ci_workflow_manifest(text)
        self.assertTrue(ok, msg=violations)

    def test_no_redundant_verify_scripts_in_ci(self) -> None:
        text = (REPO_ROOT / pr172.CI_WORKFLOW_REL).read_text(encoding="utf-8")
        for script in pr172.FORBIDDEN_REDUNDANT_CI_VERIFY_SCRIPTS:
            self.assertNotIn(script, text, msg=f"redundant CI invocation: {script}")

    def test_spine_includes_pr172_block(self) -> None:
        summary = spine_contract_summary(fast=True)
        block = summary.get("ci_spine_trust_readiness") or {}
        self.assertEqual(block.get("gate_id"), pr172.GATE_ID)
        self.assertTrue(block.get("hermetic_operator_ok"))
        self.assertEqual(summary.get("pr172_gate_id"), pr172.GATE_ID)

    def test_spine_fast_still_hermetic_operator_ok(self) -> None:
        summary = spine_contract_summary(fast=True)
        for block_key, field in (
            ("post_season_harden", "hermetic_operator_ok"),
            ("beyond_kilo_lint_readiness", "hermetic_operator_ok"),
            ("ci_spine_trust_readiness", "hermetic_operator_ok"),
            ("pr169_combined_post168_lane", "hermetic_operator_ok"),
        ):
            block = summary.get(block_key) or {}
            self.assertTrue(
                block.get(field),
                msg=f"{block_key} missing {field}",
            )
        e2e_block = summary.get("control_plane_e2e_deepen") or {}
        self.assertTrue(e2e_block.get("e2e_unittest_skipped_default"))

    def test_pr172_not_combined_umbrella(self) -> None:
        text = (REPO_ROOT / pr172.CI_WORKFLOW_REL).read_text(encoding="utf-8")
        summary = pr172.ci_spine_trust_contract_summary(text)
        self.assertFalse(summary.get("combined_umbrella_nested"))
        self.assertTrue(summary.get("hermetic_operator_ok"))

    def test_verify_pr172_operator_script_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_pr172_ci_spine_trust.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_verify_spine_script_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "-u", "scripts/verify_kilo_spine.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            env={**dict(__import__("os").environ), "PYTHONUNBUFFERED": "1"},
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_pr172_audit_pass_honesty(self) -> None:
        path = REPO_ROOT / "docs/audit/passes/2026-09-24-pr172.json"
        body = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(body["live_verified"])
        self.assertFalse(body["live_api_called"])
        self.assertEqual(body["gate_id"], pr172.GATE_ID)


if __name__ == "__main__":
    unittest.main()
