"""PR #109 final integration gate — imports and governance strings."""

from __future__ import annotations

import os
import subprocess
import unittest


class TestPR109IntegrationGate(unittest.TestCase):
    def test_matrix_passes(self) -> None:
        cmd = [
            "python3",
            "-m",
            "unittest",
            "tests.unit.test_pipeline_dashboard",
            "tests.unit.test_pipeline_delta",
            "tests.unit.test_pipeline_adversarial",
            "tests.unit.test_pipeline_concurrency",
            "tests.unit.test_github_webhook",
            "tests.unit.test_org_memory_lifecycle",
            "tests.unit.test_pr109_contract",
            "tests.unit.test_pipeline_e2e_hermetic",
            "tests.unit.test_pipeline_kill_switch",
            "tests.unit.test_pipeline_webhook_replay",
            "-q",
        ]
        env = {**os.environ, "THINKBOX_GITHUB_WEBHOOK_LIVE_TEST": "0"}
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=".", env=env)
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
