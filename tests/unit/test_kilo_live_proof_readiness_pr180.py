"""Hermetic gates for PR #180 KUDBEECLI Phase 3 (single-theme)."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_pr180_kudbee_cli_phase3 as pr180

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestPr180KudbeeCliPhase3Lane(unittest.TestCase):
    def test_pr180_gate_id(self) -> None:
        self.assertEqual(pr180.GATE_ID, "kudbee-cli-phase3")
        self.assertEqual(pr180.PR_NUMBER, 180)
        self.assertEqual(pr180.EXPECTED_FEATURE_COUNT, 25)

    def test_features_manifest(self) -> None:
        ok, violations = pr180.validate_features_manifest()
        self.assertTrue(ok, msg=[(v.code, v.message) for v in violations])

    def test_pr180_not_combined_umbrella(self) -> None:
        summary = pr180.kudbee_cli_phase3_contract_summary()
        self.assertFalse(summary.get("combined_umbrella_nested"))
        self.assertTrue(summary.get("hermetic_operator_ok"))
        self.assertFalse(summary.get("live_verified"))
        self.assertFalse(summary.get("live_api_called"))

    def test_verify_script(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_pr180_kudbee_cli_phase3.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_pr180_audit_pass_honesty(self) -> None:
        path = REPO_ROOT / pr180.PR180_PASS_REL
        body = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(body["live_verified"])
        self.assertFalse(body["live_api_called"])
        self.assertEqual(body["gate_id"], pr180.GATE_ID)
        self.assertEqual(body["feature_count"], 25)

    def test_quickstart_example_runs(self) -> None:
        proc = subprocess.run(
            ["python3", "examples/kudbee_cli_phase3_quickstart.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
