"""Unit tests for bounded hermetic subprocess helpers."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

from thinkbox.kilo_hermetic_subprocess import (
    enable_nested_e2e_unittest,
    nested_e2e_unittest_enabled,
    run_bounded_command,
    spine_fast_mode_enabled,
)


class TestKiloHermeticSubprocess(unittest.TestCase):
    def test_spine_fast_mode_env(self) -> None:
        prev = os.environ.get("KILO_SPINE_FAST")
        os.environ["KILO_SPINE_FAST"] = "1"
        try:
            self.assertTrue(spine_fast_mode_enabled())
        finally:
            if prev is None:
                os.environ.pop("KILO_SPINE_FAST", None)
            else:
                os.environ["KILO_SPINE_FAST"] = prev

    def test_nested_e2e_opt_in(self) -> None:
        prev = os.environ.get("KILO_RUN_NESTED_E2E_UNITTEST")
        os.environ.pop("KILO_RUN_NESTED_E2E_UNITTEST", None)
        try:
            self.assertFalse(nested_e2e_unittest_enabled())
            enable_nested_e2e_unittest()
            self.assertTrue(nested_e2e_unittest_enabled())
        finally:
            if prev is None:
                os.environ.pop("KILO_RUN_NESTED_E2E_UNITTEST", None)
            else:
                os.environ["KILO_RUN_NESTED_E2E_UNITTEST"] = prev

    def test_bounded_command_completes(self) -> None:
        result = run_bounded_command(
            [sys.executable, "-c", "print('ok')"],
            cwd=Path(__file__).resolve().parents[2],
            timeout_seconds=30,
        )
        self.assertFalse(result.timed_out)
        self.assertEqual(result.returncode, 0)
        self.assertIn("ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
