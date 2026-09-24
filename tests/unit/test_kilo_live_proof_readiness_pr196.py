from __future__ import annotations

import subprocess
import unittest

from thinkbox import kilo_pr196_kudbee_cli_enterprise_upgrade as pr196
from thinkbox.kilo_live_proof_readiness import REPO_ROOT


class TestPr196Cli(unittest.TestCase):
    def test_verify_script(self) -> None:
        p = subprocess.run(
            ["python3", "scripts/verify_kilo_pr196_kudbee_cli_enterprise_upgrade.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_gate(self) -> None:
        self.assertEqual(pr196.GATE_ID, "kudbee-cli-enterprise-upgrade")


if __name__ == "__main__":
    unittest.main()
