"""Unit tests for beyond-KILO lint primitives (PR #170)."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from thinkbox.beyond_kilo_lint import (
    LINT_SCOPE_REL_PATHS,
    execute_beyond_kilo_lint_suite,
    lint_execution_enabled,
    lint_tools_required,
    pyproject_lint_sections_present,
    validate_lint_scope_paths,
)
from thinkbox.kilo_live_proof_readiness import REPO_ROOT


class TestBeyondKiloLintPrimitives(unittest.TestCase):
    def test_scope_paths_exist(self) -> None:
        violations = validate_lint_scope_paths()
        self.assertEqual(violations, [])

    def test_pyproject_sections(self) -> None:
        ok, missing = pyproject_lint_sections_present()
        self.assertTrue(ok, msg=str(missing))

    def test_lint_execution_disabled_by_default(self) -> None:
        env = dict(os.environ)
        env.pop("KILO_BEYOND_KILO_LINT_EXECUTE", None)
        self.assertFalse(lint_execution_enabled(env))

    def test_lint_tools_required_in_ci(self) -> None:
        self.assertTrue(lint_tools_required({"CI": "true"}))

    def test_execute_skips_without_flag(self) -> None:
        env = {"KILO_BEYOND_KILO_LINT_EXECUTE": "0"}
        runs, viols = execute_beyond_kilo_lint_suite(env)
        self.assertEqual(runs, [])
        self.assertEqual(viols, [])

    def test_scope_paths_cover_gate_modules(self) -> None:
        for rel in LINT_SCOPE_REL_PATHS:
            self.assertTrue((REPO_ROOT / rel).is_file(), msg=rel)


class TestBeyondKiloLintExecution(unittest.TestCase):
    def test_missing_tool_fails_when_required(self) -> None:
        env = {
            "KILO_BEYOND_KILO_LINT_EXECUTE": "1",
            "KILO_BEYOND_KILO_LINT_REQUIRE_TOOLS": "1",
        }
        with mock.patch("thinkbox.beyond_kilo_lint.detect_lint_tool", return_value=None):
            _, viols = execute_beyond_kilo_lint_suite(env)
        codes = {v.code for v in viols}
        self.assertIn("tool_missing", codes)


if __name__ == "__main__":
    unittest.main()
