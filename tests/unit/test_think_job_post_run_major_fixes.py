"""PR #184 post-run major fixes (10)."""

from __future__ import annotations

import unittest

from thinkbox import kilo_pr184_think_job_post_run_deepen as pr184
from thinkbox.think_job_post_run_deepen.fixes.fix_registry import run_all_fixes
from thinkbox.think_job_post_run_deepen.idempotency_stub import apply_idempotency
from thinkbox.think_job_post_run_deepen.response_envelope import success_envelope


class TestThinkJobPostRunMajorFixes(unittest.TestCase):
    def test_fixes_manifest(self) -> None:
        ok, violations = pr184.validate_fixes_manifest()
        self.assertTrue(ok, msg=[(v.code, v.message) for v in violations])

    def test_run_all_fixes(self) -> None:
        summary = run_all_fixes()
        self.assertEqual(summary["fix_count"], 10)
        self.assertTrue(summary["all_hermetic"])

    def test_new_stubs(self) -> None:
        env = success_envelope("j", "r")
        self.assertTrue(env["ok"])
        dup = apply_idempotency("g", "a", set())
        self.assertFalse(dup["duplicate"])


if __name__ == "__main__":
    unittest.main()
