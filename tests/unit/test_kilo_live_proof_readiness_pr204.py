"""PR #204 durable RUNNING reclaim gate tests."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from thinkbox import kilo_pr204_lifecycle_reclaim as pr204

ROOT = Path(__file__).resolve().parents[2]


class TestPr204LifecycleReclaim(unittest.TestCase):
    def test_gate(self) -> None:
        ok, v = pr204.validate_reclaim_gate()
        self.assertTrue(ok, v)

    def test_verify_script(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_kilo_pr204_lifecycle_reclaim.py")],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        doc = json.loads(proc.stdout)
        self.assertTrue(doc["hermetic_operator_ok"])
        self.assertFalse(doc["live_verified"])
        self.assertFalse(doc["worker_pool"])


if __name__ == "__main__":
    unittest.main()
