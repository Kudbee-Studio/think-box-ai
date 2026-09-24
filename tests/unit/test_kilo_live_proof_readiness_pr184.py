"""Hermetic gates for PR #184 Think Job POST /run deepen."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_pr184_think_job_post_run_deepen as pr184

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestPr184ThinkJobPostRunDeepenLane(unittest.TestCase):
    def test_pr184_gate_id(self) -> None:
        self.assertEqual(pr184.GATE_ID, "think-job-post-run-deepen")
        self.assertEqual(pr184.PR_NUMBER, 184)

    def test_features_manifest(self) -> None:
        ok, violations = pr184.validate_features_manifest()
        self.assertTrue(ok, msg=[(v.code, v.message) for v in violations])

    def test_honesty_flags(self) -> None:
        summary = pr184.think_job_post_run_deepen_contract_summary()
        self.assertTrue(summary.get("hermetic_operator_ok"))
        self.assertFalse(summary.get("live_verified"))
        self.assertFalse(summary.get("live_api_called"))

    def test_verify_script(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_pr184_think_job_post_run_deepen.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_audit_pass(self) -> None:
        body = json.loads((REPO_ROOT / pr184.PR184_PASS_REL).read_text(encoding="utf-8"))
        self.assertFalse(body["live_verified"])
        self.assertEqual(body["gate_id"], pr184.GATE_ID)

    def test_quickstart_runs(self) -> None:
        proc = subprocess.run(
            ["python3", "examples/think_job_post_run_deepen_quickstart.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
