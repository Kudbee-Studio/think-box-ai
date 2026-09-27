"""Hermetic gates for PR #178 KUDBEECLI Phase 2 (single-theme)."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_pr178_kudbee_cli_phase2 as pr178

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestPr178KudbeeCliPhase2Lane(unittest.TestCase):
    def test_pr178_gate_id(self) -> None:
        self.assertEqual(pr178.GATE_ID, "kudbee-cli-phase2")
        self.assertEqual(pr178.PR_NUMBER, 178)
        self.assertEqual(pr178.EXPECTED_FEATURE_COUNT, 25)

    def test_features_manifest(self) -> None:
        ok, violations = pr178.validate_features_manifest()
        self.assertTrue(ok, msg=[(v.code, v.message) for v in violations])

    def test_pr178_not_combined_umbrella(self) -> None:
        summary = pr178.kudbee_cli_phase2_contract_summary()
        self.assertFalse(summary.get("combined_umbrella_nested"))
        self.assertTrue(summary.get("hermetic_operator_ok"))
        self.assertFalse(summary.get("live_verified"))
        self.assertFalse(summary.get("live_api_called"))

    def test_verify_script(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_pr178_kudbee_cli_phase2.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_pr178_audit_pass_honesty(self) -> None:
        path = REPO_ROOT / pr178.PR178_PASS_REL
        body = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(body["live_verified"])
        self.assertFalse(body["live_api_called"])
        self.assertEqual(body["gate_id"], pr178.GATE_ID)
        self.assertEqual(body["feature_count"], 25)

    def test_quickstart_example_runs(self) -> None:
        proc = subprocess.run(
            ["python3", "examples/kudbee_cli_phase2_quickstart.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
