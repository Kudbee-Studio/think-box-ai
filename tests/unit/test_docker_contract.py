"""Hermetic Docker enterprise contract tests."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from thinkbox.docker_contract import validate_docker_contract

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestDockerContract(unittest.TestCase):
    def test_contract_valid(self) -> None:
        ok, violations = validate_docker_contract()
        self.assertTrue(ok, msg=[(v.code, v.message) for v in violations])

    def test_verify_script(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_docker_contract.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
