"""Hermetic tests for experiments/run_swarm_convergence.py (no live API)."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HARNESS = ROOT / "experiments/run_swarm_convergence.py"


class TestRunSwarmConvergenceHarness(unittest.TestCase):
    def test_missing_api_key_writes_blocker_artifact(self) -> None:
        env = os.environ.copy()
        env.pop("INCEPTION_API_KEY", None)
        proc = subprocess.run(
            [sys.executable, str(HARNESS), "--runs", "5", "--fresh-ledger"],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("INCEPTION_API_KEY missing", proc.stdout + proc.stderr)
        blocked = sorted((ROOT / "data/thinkboxmd").glob("swarm_convergence_BLOCKED_*.json"))
        self.assertTrue(blocked, "expected blocker artifact")
        doc = json.loads(blocked[-1].read_text())
        self.assertFalse(doc["live_verified"])
        self.assertEqual(doc["live_blockers"], ["INCEPTION_API_KEY missing"])
        self.assertEqual(doc["config"]["runs"], 5)
        self.assertEqual(doc["config"]["primary"], 224)
        self.assertEqual(doc["config"]["validators"], 32)


if __name__ == "__main__":
    unittest.main()
