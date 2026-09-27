"""PR #192 readiness lane tests."""

from __future__ import annotations

import json
import subprocess
import unittest

from thinkbox import kilo_pr192_kudbee_sdk_followup_w3_major_fixes as pr192
from thinkbox.kilo_live_proof_readiness import REPO_ROOT


class TestPr192KudbeeSdkFollowupW3MajorFixesLane(unittest.TestCase):
    def test_pr192_gate_id(self) -> None:
        self.assertEqual(pr192.GATE_ID, "kudbee-sdk-followup-w3-major-fixes")
        self.assertEqual(pr192.PR_NUMBER, 192)
        self.assertEqual(pr192.EXPECTED_FIX_COUNT, 35)

    def test_fixes_manifest(self) -> None:
        ok, violations = pr192.validate_fixes_manifest()
        self.assertTrue(ok, violations)

    def test_honesty_flags(self) -> None:
        summary = pr192.kudbee_sdk_followup_w3_major_fixes_contract_summary()
        self.assertFalse(summary["live_verified"])
        self.assertFalse(summary["live_api_called"])

    def test_verify_script(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_pr192_kudbee_sdk_followup_w3_major_fixes.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)

    def test_audit_pass(self) -> None:
        body = json.loads((REPO_ROOT / pr192.PR192_PASS_REL).read_text(encoding="utf-8"))
        self.assertEqual(body["fix_count"], 35)


if __name__ == "__main__":
    unittest.main()
