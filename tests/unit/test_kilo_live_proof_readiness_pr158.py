"""Hermetic gates for PR #158 END LINK deepen."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_end_link_deepen as deepen
from thinkbox.kilo_live_proof_readiness import spine_contract_summary

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestEndLinkDeepenGate(unittest.TestCase):
    def test_pr158_gate_id(self) -> None:
        self.assertEqual(deepen.GATE_ID, "end-link-deepen")
        self.assertEqual(deepen.PR_NUMBER, 158)

    def test_hermetic_eval_passes(self) -> None:
        from thinkbox.kilo_env_matrix import EnvMatrixMode

        env = deepen.minimal_end_link_deepen_environ()
        result = deepen.evaluate_end_link_deepen(EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertTrue(result.ok, msg=result.violations)

    def test_spine_summary_includes_block(self) -> None:
        summary = spine_contract_summary()
        block = summary.get("end_link_deepen") or {}
        self.assertEqual(block.get("gate_id"), deepen.GATE_ID)
        self.assertTrue(block.get("hermetic_operator_ok"))
        self.assertEqual(summary.get("pr158_gate_id"), deepen.GATE_ID)

    def test_verify_script_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_end_link_deepen.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_checklist_live_verified_false(self) -> None:
        doc = json.loads((REPO_ROOT / deepen.CHECKLIST_REL).read_text(encoding="utf-8"))
        self.assertFalse(doc["live_verified"])
        self.assertEqual(doc["end_link_deepen"], "end-link-deepen")


if __name__ == "__main__":
    unittest.main()
