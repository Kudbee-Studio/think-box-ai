"""PR #198 gate tests."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from thinkbox import kilo_pr198_cloud_execution_durable_queue as pr198

ROOT = Path(__file__).resolve().parents[2]


class TestPr198DurableQueue(unittest.TestCase):
    def test_gate(self) -> None:
        ok, v = pr198.validate_features_manifest()
        self.assertTrue(ok, v)

    def test_verify_script(self) -> None:
        p = subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_kilo_pr198_cloud_execution_durable_queue.py")],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
