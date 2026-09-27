"""Local environment workflow tests (PR #185)."""

from __future__ import annotations

import unittest

from thinkbox import kilo_pr185_think_job_lifecycle_fixes as pr185
from thinkbox.think_job_lifecycle_fixes.local.python_version import python_version_ok
from thinkbox.think_job_lifecycle_fixes.local.workflow import run_local_workflow


class TestThinkJobPr185LocalEnv(unittest.TestCase):
    def test_local_setup_manifest(self) -> None:
        ok, violations = pr185.validate_local_setup_manifest()
        self.assertTrue(ok, violations)

    def test_python_version_step(self) -> None:
        step = python_version_ok()
        self.assertTrue(step["ok"])

    def test_dry_run_workflow(self) -> None:
        summary = run_local_workflow(dry_run=True)
        self.assertTrue(summary["dry_run"])
        self.assertEqual(len(summary["steps"]), 8)
