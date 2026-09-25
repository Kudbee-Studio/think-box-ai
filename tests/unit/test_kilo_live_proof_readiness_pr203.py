"""PR #203 durable QUEUED resume gate tests."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from thinkbox import kilo_pr203_lifecycle_resume as pr203

ROOT = Path(__file__).resolve().parents[2]


class TestPr203LifecycleResume(unittest.TestCase):
    def test_gate(self) -> None:
        ok, v = pr203.validate_resume_gate()
        self.assertTrue(ok, v)

    def test_verify_script(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_kilo_pr203_lifecycle_resume.py")],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        doc = json.loads(proc.stdout)
        self.assertTrue(doc["hermetic_operator_ok"])
        self.assertFalse(doc["live_verified"])
        self.assertFalse(doc["orphaned_running_reclaim"])


if __name__ == "__main__":
    unittest.main()
