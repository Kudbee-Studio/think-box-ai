"""Hermetic tests: Demo-in-10 control-plane dry-run ceremony (PR #111)."""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path
from thinkbox.control_plane_dry_run import (
    build_control_plane_dry_run_context,
    build_dry_run_four_state,
    run_control_plane_dry_run,
)


class TestControlPlaneDryRun(unittest.TestCase):
    def test_four_state_live_and_prod_blocked(self) -> None:
        fs = build_dry_run_four_state(ceremony_ok=True, chain_verified=True)
        self.assertTrue(fs["CODE_COMPLETE"])
        self.assertTrue(fs["TEST_VERIFIED"])
        self.assertFalse(fs["LIVE_VERIFIED"])
        self.assertFalse(fs["PRODUCTION_READY"])
        self.assertIn("DRY_RUN", fs["live_blocked_reason"])

    def test_ceremony_never_calls_github_merge(self) -> None:
        result = run_control_plane_dry_run(pr_number=111)
        self.assertTrue(result.all_steps_ok())
        self.assertFalse(result.github_merge_called)
        self.assertTrue(result.merge_admitted)
        self.assertTrue(result.chain_verified)
        merge_step = next(s for s in result.steps if s.name == "founder_gated_request_merge")
        self.assertFalse(merge_step.payload.get("github_merge_called"))

    def test_api_handlers_request_merge_no_github(self) -> None:
        ctx = build_control_plane_dry_run_context(pr_number=112)
        result = run_control_plane_dry_run(pr_number=112, context=ctx, exercise_api_handlers=True)
        api_step = next(s for s in result.steps if s.name == "pipeline_api_handlers")
        self.assertTrue(api_step.ok, api_step.detail)
        merge_body = api_step.payload.get("merge_body") or {}
        self.assertFalse(merge_body.get("github_merge_called"))
        self.assertFalse(merge_body.get("merged"))

    def test_script_exists_and_runs(self) -> None:
        path = Path("scripts/demo_in_10_control_plane_dry_run.sh")
        self.assertTrue(path.exists())
        self.assertTrue(os.access(str(path), os.X_OK))
        proc = subprocess.run(
            ["bash", str(path)],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertIn("github_merge_called: False", proc.stdout)
        self.assertIn('"live_verified": false', proc.stdout.lower())


class TestDryRunModuleEntrypoint(unittest.TestCase):
    def test_main_module_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "-m", "thinkbox.control_plane_dry_run"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
