"""Hermetic gates for PR #181 Kudbee SDK follow-up wave 2 (single-theme)."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_pr181_kudbee_sdk_followup_w2 as pr181

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestPr181KudbeeSdkFollowupW2Lane(unittest.TestCase):
    def test_pr181_gate_id(self) -> None:
        self.assertEqual(pr181.GATE_ID, "kudbee-sdk-followup-w2")
        self.assertEqual(pr181.PR_NUMBER, 181)
        self.assertEqual(pr181.EXPECTED_FEATURE_COUNT, 25)

    def test_features_manifest(self) -> None:
        ok, violations = pr181.validate_features_manifest()
        self.assertTrue(ok, msg=[(v.code, v.message) for v in violations])

    def test_pr181_not_combined_umbrella(self) -> None:
        summary = pr181.kudbee_sdk_followup_w2_contract_summary()
        self.assertFalse(summary.get("combined_umbrella_nested"))
        self.assertTrue(summary.get("hermetic_operator_ok"))
        self.assertFalse(summary.get("live_verified"))
        self.assertFalse(summary.get("live_api_called"))

    def test_verify_script(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_pr181_kudbee_sdk_followup_w2.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_pr181_audit_pass_honesty(self) -> None:
        path = REPO_ROOT / pr181.PR181_PASS_REL
        body = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(body["live_verified"])
        self.assertFalse(body["live_api_called"])
        self.assertEqual(body["gate_id"], pr181.GATE_ID)
        self.assertEqual(body["feature_count"], 25)

    def test_quickstart_example_runs(self) -> None:
        proc = subprocess.run(
            ["python3", "examples/kudbee_sdk_followup_w2_quickstart.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
