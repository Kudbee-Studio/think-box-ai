"""PR #199 gate tests."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from thinkbox import kilo_pr199_cloud_execution_worker_orchestrator as pr199

ROOT = Path(__file__).resolve().parents[2]


class TestPr199WorkerOrchestrator(unittest.TestCase):
    def test_gate(self) -> None:
        ok, v = pr199.validate_features_manifest()
        self.assertTrue(ok, v)

    def test_verify_script(self) -> None:
        p = subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_kilo_pr199_cloud_execution_worker_orchestrator.py")],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
