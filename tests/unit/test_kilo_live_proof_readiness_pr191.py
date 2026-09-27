"""Live-proof readiness honesty for Kudbee SDK follow-up wave 3 (PR #191)."""

from __future__ import annotations

import json
import subprocess
import unittest

from thinkbox import kilo_pr191_kudbee_sdk_followup_w3 as pr191
from thinkbox.kilo_live_proof_readiness import REPO_ROOT


class TestKiloLiveProofReadinessPr191(unittest.TestCase):
    def test_pr191_gate_id(self) -> None:
        self.assertEqual(pr191.GATE_ID, "kudbee-sdk-followup-w3")
        self.assertEqual(pr191.PR_NUMBER, 191)
        self.assertEqual(pr191.EXPECTED_FEATURE_COUNT, 25)

    def test_pr191_manifest_valid(self) -> None:
        ok, violations = pr191.validate_features_manifest()
        self.assertTrue(ok, violations)

    def test_pr191_not_combined_umbrella(self) -> None:
        summary = pr191.kudbee_sdk_followup_w3_contract_summary()
        self.assertFalse(summary["live_verified"])
        self.assertFalse(summary["live_api_called"])
        self.assertEqual(summary["four_state_max"], "TEST_VERIFIED")
        self.assertFalse(summary["combined_umbrella_nested"])

    def test_pr191_verify_script_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_pr191_kudbee_sdk_followup_w3.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_pr191_audit_pass_honesty(self) -> None:
        path = REPO_ROOT / pr191.PR191_PASS_REL
        self.assertTrue(path.is_file())
        body = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(body["live_verified"])
        self.assertFalse(body["live_api_called"])
        self.assertEqual(body["gate_id"], pr191.GATE_ID)


if __name__ == "__main__":
    unittest.main()
