"""PR #201 gate tests."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from thinkbox import kilo_pr201_upstash_box_access as pr201

ROOT = Path(__file__).resolve().parents[2]


class TestPr201UpstashBoxAccess(unittest.TestCase):
    def test_gate(self) -> None:
        ok, violations = pr201.validate_features_manifest()
        self.assertTrue(ok, violations)

    def test_verify_script(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_kilo_pr201_upstash_box_access.py")],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_honesty_caps(self) -> None:
        summary = pr201.upstash_box_access_contract_summary()
        self.assertFalse(summary["live_verified"])
        self.assertFalse(summary["live_api_called"])
        self.assertEqual(summary["four_state_max"], "TEST_VERIFIED")
        self.assertEqual(summary["upstream_pr"], 200)


if __name__ == "__main__":
    unittest.main()
