"""PR #183 major fixes wave (20 hermetic fixes)."""

from __future__ import annotations

import unittest

from thinkbox import kilo_pr183_think_job_hermetic_e2e as pr183
from thinkbox.think_job_e2e_deepen.fixes.checklist_honesty import validate_checklist
from thinkbox.think_job_e2e_deepen.fixes.fix_registry_integrate import run_all_fixes
from thinkbox.think_job_e2e_deepen.fixes.nested_e2e_catalog import E2E_MODULES
from thinkbox.think_job_e2e_deepen.fixes.receipt_watch_empty_guard import watchable_receipt


class TestThinkJobE2eMajorFixes(unittest.TestCase):
    def test_fixes_manifest(self) -> None:
        ok, violations = pr183.validate_fixes_manifest()
        self.assertTrue(ok, msg=[(v.code, v.message) for v in violations])
        self.assertEqual(pr183.EXPECTED_FIX_COUNT, 20)

    def test_run_all_major_fixes(self) -> None:
        summary = run_all_fixes()
        self.assertEqual(summary["fix_count"], 20)
        self.assertTrue(summary["all_hermetic"])
        self.assertFalse(summary["live_api_called"])

    def test_checklist_honesty(self) -> None:
        doc = validate_checklist()
        self.assertTrue(doc["valid"])

    def test_nested_e2e_catalog_opt_in(self) -> None:
        self.assertGreaterEqual(len(E2E_MODULES), 2)

    def test_receipt_watch_empty_guard(self) -> None:
        self.assertFalse(watchable_receipt("  ")["watchable"])
        self.assertTrue(watchable_receipt("rcpt-ok")["watchable"])


if __name__ == "__main__":
    unittest.main()
