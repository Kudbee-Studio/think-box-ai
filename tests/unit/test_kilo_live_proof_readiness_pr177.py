"""Hermetic gates for PR #177 Kudbee SDK app (single-theme)."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_pr177_kudbee_sdk_app as pr177

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestPr177KudbeeSdkAppLane(unittest.TestCase):
    def test_pr177_gate_id(self) -> None:
        self.assertEqual(pr177.GATE_ID, "kudbee-sdk-app")
        self.assertEqual(pr177.PR_NUMBER, 177)
        self.assertEqual(pr177.EXPECTED_FEATURE_COUNT, 25)

    def test_features_manifest(self) -> None:
        ok, violations = pr177.validate_features_manifest()
        self.assertTrue(ok, msg=[(v.code, v.message) for v in violations])

    def test_pr177_not_combined_umbrella(self) -> None:
        summary = pr177.kudbee_sdk_app_contract_summary()
        self.assertFalse(summary.get("combined_umbrella_nested"))
        self.assertTrue(summary.get("hermetic_operator_ok"))

    def test_verify_script(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_pr177_kudbee_sdk_app.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_pr177_audit_pass_honesty(self) -> None:
        path = REPO_ROOT / pr177.PR177_PASS_REL
        body = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(body["live_verified"])
        self.assertFalse(body["live_api_called"])
        self.assertEqual(body["gate_id"], pr177.GATE_ID)
        self.assertEqual(body["feature_count"], 25)

    def test_quickstart_example_runs(self) -> None:
        proc = subprocess.run(
            ["python3", "examples/kudbee_sdk_quickstart.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
