"""Unit tests for the ``python3 -m thinkbox`` package entrypoint.

The README documents invocations such as ``python3 -m thinkbox swarm status``
and ``python3 -m thinkbox env status``. These require ``thinkbox/__main__.py``
to delegate to the KUDBEECLI ``main``; without it the interpreter raises
``No module named thinkbox.__main__``.
"""

import importlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

from thinkbox.cli import main as cli_main
from thinkbox.cli_inspect import CLI_EXIT_OK

ROOT = Path(__file__).resolve().parents[2]


class TestThinkboxModuleEntrypoint(unittest.TestCase):
    def test_main_module_delegates_to_cli_main(self) -> None:
        module = importlib.import_module("thinkbox.__main__")
        self.assertIs(module.main, cli_main)

    def test_module_env_status_json_runs(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "thinkbox", "env", "status", "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, CLI_EXIT_OK, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertIn("substrate", payload)

    def test_module_help_lists_subcommands(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "thinkbox", "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for sub in ("swarm", "ledger", "env", "session", "proof"):
            self.assertIn(sub, proc.stdout)


if __name__ == "__main__":
    unittest.main()
