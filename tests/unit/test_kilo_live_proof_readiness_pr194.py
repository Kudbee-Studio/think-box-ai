"""Live-proof readiness honesty for PR #194 lr-energy major fixes."""

from __future__ import annotations

import json
import subprocess
import unittest

from thinkbox import kilo_pr194_kudbee_sdk_longrange_energy_major_fixes as pr194
from thinkbox.kilo_live_proof_readiness import REPO_ROOT


class TestKiloLiveProofReadinessPr194(unittest.TestCase):
    def test_pr194_gate_id(self) -> None:
        self.assertEqual(pr194.GATE_ID, "kudbee-sdk-longrange-energy-major-fixes")
        self.assertEqual(pr194.PR_NUMBER, 194)
        self.assertEqual(pr194.EXPECTED_FIX_COUNT, 25)

    def test_pr194_manifest_valid(self) -> None:
        ok, violations = pr194.validate_fixes_manifest()
        self.assertTrue(ok, violations)

    def test_pr194_verify_script_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_pr194_kudbee_sdk_longrange_energy_major_fixes.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_pr194_audit_pass_honesty(self) -> None:
        doc = json.loads((REPO_ROOT / pr194.PR194_PASS_REL).read_text(encoding="utf-8"))
        self.assertFalse(doc["live_verified"])
        self.assertFalse(doc["live_api_called"])


if __name__ == "__main__":
    unittest.main()
