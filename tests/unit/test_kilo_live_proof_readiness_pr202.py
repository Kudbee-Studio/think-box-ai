"""PR #202 gate tests."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from thinkbox import kilo_pr202_lifecycle_harden as pr202

ROOT = Path(__file__).resolve().parents[2]


class TestPr202LifecycleHarden(unittest.TestCase):
    def test_gate(self) -> None:
        ok, v = pr202.validate_hardens_manifest()
        self.assertTrue(ok, v)

    def test_verify_script(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_kilo_pr202_lifecycle_harden.py")],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        doc = json.loads(proc.stdout)
        self.assertTrue(doc["hermetic_operator_ok"])
        self.assertFalse(doc["live_verified"])
        self.assertEqual(doc["harden_count"], 25)


if __name__ == "__main__":
    unittest.main()
