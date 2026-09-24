"""Hermetic gates for PR #175 lint scope wave 2 (single-theme)."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_pr175_lint_scope_wave2 as pr175
from thinkbox.beyond_kilo_lint import LINT_SCOPE_REL_PATHS

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestPr175LintScopeWave2Lane(unittest.TestCase):
    def test_pr175_gate_id(self) -> None:
        self.assertEqual(pr175.GATE_ID, "lint-scope-wave2")
        self.assertEqual(pr175.PR_NUMBER, 175)

    def test_full_scope_count_38(self) -> None:
        self.assertEqual(len(LINT_SCOPE_REL_PATHS), pr175.EXPECTED_FULL_SCOPE_COUNT)

    def test_wave2_manifest_parity(self) -> None:
        ok, violations = pr175.validate_wave2_scope_manifest()
        self.assertTrue(ok, msg=[(v.code, v.message) for v in violations])

    def test_wave1_still_subset_after_wave2(self) -> None:
        from thinkbox.kilo_pr174_lint_scope_wave1 import validate_wave1_scope_manifest

        ok, violations = validate_wave1_scope_manifest()
        self.assertTrue(ok, msg=[(v.code, v.message) for v in violations])

    def test_pr175_not_combined_umbrella(self) -> None:
        summary = pr175.lint_scope_wave2_contract_summary()
        self.assertFalse(summary.get("combined_umbrella_nested"))
        self.assertTrue(summary.get("hermetic_operator_ok"))

    def test_beyond_kilo_lint_v3_execute(self) -> None:
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
        self.assertEqual(body.get("beyond_kilo_version"), "3")

    def test_pr175_audit_pass_honesty(self) -> None:
        path = REPO_ROOT / pr175.PR175_PASS_REL
        body = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(body["live_verified"])
        self.assertFalse(body["live_api_called"])
        self.assertEqual(body["gate_id"], pr175.GATE_ID)


if __name__ == "__main__":
    unittest.main()
