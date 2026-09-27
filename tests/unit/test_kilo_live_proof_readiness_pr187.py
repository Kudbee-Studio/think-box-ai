"""PR #187 readiness lane tests."""

from __future__ import annotations

import json
import subprocess
import unittest

from thinkbox import kilo_pr187_think_job_receipt_major_fixes as pr187
from thinkbox.kilo_live_proof_readiness import REPO_ROOT


class TestPr187ThinkJobReceiptMajorFixesLane(unittest.TestCase):
    def test_pr187_gate_id(self) -> None:
        self.assertEqual(pr187.GATE_ID, "think-job-receipt-major-fixes")
        self.assertEqual(pr187.PR_NUMBER, 187)

    def test_fixes_manifest(self) -> None:
        ok, violations = pr187.validate_fixes_manifest()
        self.assertTrue(ok, violations)

    def test_honesty_flags(self) -> None:
        summary = pr187.think_job_receipt_major_fixes_contract_summary()
        self.assertFalse(summary["live_verified"])
        self.assertFalse(summary["live_api_called"])

    def test_verify_script(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_pr187_think_job_receipt_major_fixes.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)

    def test_audit_pass(self) -> None:
        body = json.loads((REPO_ROOT / pr187.PR187_PASS_REL).read_text(encoding="utf-8"))
        self.assertEqual(body["fix_count"], 25)


if __name__ == "__main__":
    unittest.main()
