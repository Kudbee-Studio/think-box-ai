"""PR #185 readiness lane tests."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_pr185_think_job_lifecycle_fixes as pr185
from thinkbox.kilo_live_proof_readiness import REPO_ROOT


class TestPr185ThinkJobLifecycleFixesLane(unittest.TestCase):
    def test_pr185_gate_id(self) -> None:
        self.assertEqual(pr185.GATE_ID, "think-job-lifecycle-fixes")
        self.assertEqual(pr185.PR_NUMBER, 185)

    def test_fixes_manifest(self) -> None:
        ok, violations = pr185.validate_fixes_manifest()
        self.assertTrue(ok, violations)

    def test_local_setup_manifest(self) -> None:
        ok, violations = pr185.validate_local_setup_manifest()
        self.assertTrue(ok, violations)

    def test_honesty_flags(self) -> None:
        summary = pr185.think_job_lifecycle_fixes_contract_summary()
        self.assertFalse(summary["live_verified"])
        self.assertFalse(summary["live_api_called"])
        self.assertFalse(summary["combined_umbrella_nested"])

    def test_verify_script(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_pr185_think_job_lifecycle_fixes.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)

    def test_audit_pass(self) -> None:
        body = json.loads((REPO_ROOT / pr185.PR185_PASS_REL).read_text(encoding="utf-8"))
        self.assertEqual(body["fix_count"], 25)
        self.assertEqual(body["gate_id"], pr185.GATE_ID)

    def test_quickstart_runs(self) -> None:
        proc = subprocess.run(
            ["python3", "examples/think_job_lifecycle_fixes_quickstart.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)


if __name__ == "__main__":
    unittest.main()
