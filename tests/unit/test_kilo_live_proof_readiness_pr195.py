"""Live-proof readiness honesty for PR #195 enterprise lanes."""

from __future__ import annotations

import json
import subprocess
import unittest

from thinkbox import kilo_pr195_kudbee_sdk_enterprise_lr_energy as pr195
from thinkbox.kilo_live_proof_readiness import REPO_ROOT


class TestKiloLiveProofReadinessPr195(unittest.TestCase):
    def test_pr195_gate(self) -> None:
        self.assertEqual(pr195.GATE_ID, "kudbee-sdk-enterprise-lr-energy-lanes")
        self.assertEqual(pr195.EXPECTED_LANE_COUNT, 25)

    def test_pr195_manifest_valid(self) -> None:
        ok, violations = pr195.validate_lanes_manifest()
        self.assertTrue(ok, violations)

    def test_pr195_verify_script(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_pr195_kudbee_sdk_enterprise_lr_energy.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_pr195_audit_honesty(self) -> None:
        doc = json.loads((REPO_ROOT / pr195.PR195_PASS_REL).read_text(encoding="utf-8"))
        self.assertFalse(doc["live_verified"])
        self.assertEqual(doc.get("tier"), "enterprise")


if __name__ == "__main__":
    unittest.main()
