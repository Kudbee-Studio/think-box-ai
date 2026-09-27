"""PR #188 readiness lane tests."""

from __future__ import annotations

import json
import subprocess
import unittest

from thinkbox import kilo_pr188_think_job_governed_run_major_fixes as pr188
from thinkbox.kilo_live_proof_readiness import REPO_ROOT


class TestPr188ThinkJobGovernedRunMajorFixesLane(unittest.TestCase):
    def test_pr188_gate_id(self) -> None:
        self.assertEqual(pr188.GATE_ID, "think-job-governed-run-major-fixes")
        self.assertEqual(pr188.PR_NUMBER, 188)

    def test_fixes_manifest(self) -> None:
        ok, violations = pr188.validate_fixes_manifest()
        self.assertTrue(ok, violations)

    def test_honesty_flags(self) -> None:
        summary = pr188.think_job_governed_run_major_fixes_contract_summary()
        self.assertFalse(summary["live_verified"])
        self.assertFalse(summary["live_api_called"])

    def test_verify_script(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_pr188_think_job_governed_run_major_fixes.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)

    def test_audit_pass(self) -> None:
        body = json.loads((REPO_ROOT / pr188.PR188_PASS_REL).read_text(encoding="utf-8"))
        self.assertEqual(body["fix_count"], 25)


if __name__ == "__main__":
    unittest.main()
