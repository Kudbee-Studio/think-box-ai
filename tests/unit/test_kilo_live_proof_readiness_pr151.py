"""Hermetic gates for PR #151 KILO post-season-harden (ops harden, not arc gate)."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_post_season_harden as psh
from thinkbox.kilo_live_proof_readiness import spine_contract_summary

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestPostSeasonHardenGate(unittest.TestCase):
    def test_pr151_gate_id(self) -> None:
        self.assertEqual(psh.GATE_ID, "post-season-harden")
        self.assertEqual(psh.PR_NUMBER, 151)

    def test_hermetic_unit_passes(self) -> None:
        env = psh.minimal_post_season_harden_environ()
        result = psh.evaluate_post_season_harden(
            psh.PostSeasonHardenMode.HERMETIC_UNIT, env
        )
        self.assertTrue(result.ok, msg=result.violations)
        assert result.evidence is not None
        self.assertFalse(result.evidence.live_api_called)

    def test_requires_live_proof_exec_layer(self) -> None:
        env = psh.minimal_post_season_harden_environ()
        env = dict(env)
        env.pop("THINKBOX_KILO_MERCURY_MOCK", None)
        env.pop("THINKBOX_MERCURY_BASE_URL", None)
        env["INCEPTION_API_KEY"] = "sk-live-production-shaped-key"
        result = psh.evaluate_post_season_harden(
            psh.PostSeasonHardenMode.HERMETIC_UNIT, env
        )
        self.assertFalse(result.ok)
        self.assertFalse(result.live_proof_exec_ok)

    def test_ci_workflow_manifest(self) -> None:
        text = (REPO_ROOT / psh.CI_WORKFLOW_REL).read_text(encoding="utf-8")
        ok, violations = psh.validate_ci_workflow_manifest(text)
        self.assertTrue(ok, msg=violations)

    def test_checklist_document(self) -> None:
        path = REPO_ROOT / psh.POST_SEASON_CHECKLIST_REL
        doc = json.loads(path.read_text(encoding="utf-8"))
        ok, violations = psh.validate_post_season_checklist_document(doc)
        self.assertTrue(ok, msg=violations)

    def test_spine_summary_includes_post_season(self) -> None:
        summary = spine_contract_summary()
        block = summary.get("post_season_harden") or {}
        self.assertEqual(block.get("gate_id"), psh.GATE_ID)
        self.assertTrue(block.get("hermetic_operator_ok"))

    def test_verify_script_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_post_season_harden.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_branch_hygiene_dry_run(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/cleanup_merged_cursor_branches.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("dry-run", proc.stdout.lower())


class TestBranchHygieneGuards(unittest.TestCase):
    def test_protected_main_in_script(self) -> None:
        text = (REPO_ROOT / psh.BRANCH_HYGIENE_SCRIPT_REL).read_text(encoding="utf-8")
        self.assertIn('"main"', text)
        self.assertIn("PROTECTED_BRANCHES", text)


if __name__ == "__main__":
    unittest.main()
