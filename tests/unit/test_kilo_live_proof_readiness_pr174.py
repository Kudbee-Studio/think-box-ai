"""Hermetic gates for PR #174 lint scope wave 1 (single-theme)."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_pr174_lint_scope_wave1 as pr174
from thinkbox.beyond_kilo_lint import LINT_SCOPE_REL_PATHS

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestPr174LintScopeWave1Lane(unittest.TestCase):
    def test_pr174_gate_id(self) -> None:
        self.assertEqual(pr174.GATE_ID, "lint-scope-wave1")
        self.assertEqual(pr174.PR_NUMBER, 174)

    def test_wave1_scope_count_25(self) -> None:
        from thinkbox.kilo_pr174_lint_scope_wave1 import load_wave1_scope_manifest

        manifest = load_wave1_scope_manifest()
        self.assertEqual(len(manifest["scope_paths"]), pr174.EXPECTED_SCOPE_COUNT)

    def test_wave1_manifest_parity(self) -> None:
        ok, violations = pr174.validate_wave1_scope_manifest()
        self.assertTrue(ok, msg=[(v.code, v.message) for v in violations])

    def test_pr174_not_combined_umbrella(self) -> None:
        summary = pr174.lint_scope_wave1_contract_summary()
        self.assertFalse(summary.get("combined_umbrella_nested"))
        self.assertTrue(summary.get("hermetic_operator_ok"))

    def test_beyond_kilo_lint_still_passes_with_wave1(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_beyond_kilo_lint.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            env={
                **dict(__import__("os").environ),
                "KILO_BEYOND_KILO_LINT_EXECUTE": "1",
            },
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        body = json.loads(proc.stdout)
        self.assertIn(body.get("beyond_kilo_version"), ("2", "3"))

    def test_pr174_audit_pass_honesty(self) -> None:
        path = REPO_ROOT / pr174.PR174_PASS_REL
        body = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(body["live_verified"])
        self.assertFalse(body["live_api_called"])
        self.assertEqual(body["gate_id"], pr174.GATE_ID)


if __name__ == "__main__":
    unittest.main()
