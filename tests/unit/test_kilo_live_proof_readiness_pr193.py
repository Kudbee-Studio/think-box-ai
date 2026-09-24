"""Live-proof readiness honesty for Kudbee SDK long-range + energy (PR #193)."""

from __future__ import annotations

import json
import subprocess
import unittest

from thinkbox import kilo_pr193_kudbee_sdk_longrange_energy as pr193
from thinkbox.kilo_live_proof_readiness import REPO_ROOT


class TestKiloLiveProofReadinessPr193(unittest.TestCase):
    def test_pr193_gate_id(self) -> None:
        self.assertEqual(pr193.GATE_ID, "kudbee-sdk-longrange-energy-deepen")
        self.assertEqual(pr193.PR_NUMBER, 193)
        self.assertEqual(pr193.EXPECTED_FEATURE_COUNT, 25)

    def test_pr193_manifest_valid(self) -> None:
        ok, violations = pr193.validate_features_manifest()
        self.assertTrue(ok, violations)

    def test_pr193_not_combined_umbrella(self) -> None:
        summary = pr193.kudbee_sdk_longrange_energy_contract_summary()
        self.assertFalse(summary["live_verified"])
        self.assertFalse(summary["live_api_called"])
        self.assertEqual(summary["four_state_max"], "TEST_VERIFIED")
        self.assertFalse(summary["combined_umbrella_nested"])

    def test_pr193_verify_script_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_pr193_kudbee_sdk_longrange_energy.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_pr193_audit_pass_honesty(self) -> None:
        doc = json.loads((REPO_ROOT / pr193.PR193_PASS_REL).read_text(encoding="utf-8"))
        self.assertFalse(doc["live_verified"])
        self.assertFalse(doc["live_api_called"])
        self.assertEqual(doc["gate_id"], pr193.GATE_ID)


if __name__ == "__main__":
    unittest.main()
