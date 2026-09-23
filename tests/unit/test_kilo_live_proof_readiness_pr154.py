"""Hermetic gates for PR #154 control-plane-api surface."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_control_plane_api as cp
from thinkbox.kilo_live_proof_readiness import spine_contract_summary

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestControlPlaneApiGate(unittest.TestCase):
    def test_pr154_gate_id(self) -> None:
        self.assertEqual(cp.GATE_ID, "control-plane-api")
        self.assertEqual(cp.PR_NUMBER, 154)

    def test_hermetic_eval_passes(self) -> None:
        env = cp.minimal_control_plane_api_environ()
        result = cp.evaluate_control_plane_api(
            __import__("thinkbox.kilo_env_matrix", fromlist=["EnvMatrixMode"]).EnvMatrixMode.HERMETIC_UNIT,
            env,
        )
        self.assertTrue(result.ok, msg=result.violations)

    def test_spine_summary_includes_control_plane_api(self) -> None:
        summary = spine_contract_summary()
        block = summary.get("control_plane_api") or {}
        self.assertEqual(block.get("gate_id"), cp.GATE_ID)
        self.assertTrue(block.get("hermetic_operator_ok"))
        self.assertEqual(summary.get("pr154_gate_id"), cp.GATE_ID)

    def test_verify_script_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_control_plane_api.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_checklist_live_verified_false(self) -> None:
        doc = json.loads((REPO_ROOT / cp.CHECKLIST_REL).read_text(encoding="utf-8"))
        self.assertFalse(doc["live_verified"])


if __name__ == "__main__":
    unittest.main()
