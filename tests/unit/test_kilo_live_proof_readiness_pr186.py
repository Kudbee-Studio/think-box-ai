"""PR #186 readiness lane tests."""

from __future__ import annotations

import json
import subprocess
import unittest

from thinkbox import kilo_pr186_think_job_run_receipt_deepen as pr186
from thinkbox.kilo_live_proof_readiness import REPO_ROOT


class TestPr186ThinkJobRunReceiptDeepenLane(unittest.TestCase):
    def test_pr186_gate_id(self) -> None:
        self.assertEqual(pr186.GATE_ID, "think-job-run-receipt-deepen")
        self.assertEqual(pr186.PR_NUMBER, 186)

    def test_features_manifest(self) -> None:
        ok, violations = pr186.validate_features_manifest()
        self.assertTrue(ok, violations)

    def test_honesty_flags(self) -> None:
        summary = pr186.think_job_run_receipt_deepen_contract_summary()
        self.assertFalse(summary["live_verified"])
        self.assertFalse(summary["live_api_called"])

    def test_verify_script(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_pr186_think_job_run_receipt_deepen.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)

    def test_audit_pass(self) -> None:
        body = json.loads((REPO_ROOT / pr186.PR186_PASS_REL).read_text(encoding="utf-8"))
        self.assertEqual(body["feature_count"], 25)
        self.assertEqual(body["gate_id"], pr186.GATE_ID)

    def test_quickstart_runs(self) -> None:
        proc = subprocess.run(
            ["python3", "examples/think_job_run_receipt_deepen_quickstart.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)


if __name__ == "__main__":
    unittest.main()
