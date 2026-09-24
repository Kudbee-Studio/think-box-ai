"""PR #184 enhancement wave tests."""

from __future__ import annotations

import unittest

from thinkbox import kilo_pr184_think_job_post_run_deepen as pr184
from thinkbox.think_job_post_run_deepen.cassette import replay_cassette
from thinkbox.think_job_post_run_deepen.enhancements.enhancement_registry import run_enhancement_probes


class TestThinkJobPostRunEnhancements(unittest.TestCase):
    def test_enhancements_manifest(self) -> None:
        ok, violations = pr184.validate_enhancements_manifest()
        self.assertTrue(ok, msg=[(v.code, v.message) for v in violations])

    def test_enhancement_probes(self) -> None:
        summary = run_enhancement_probes()
        self.assertTrue(summary["all_hermetic"])
        self.assertEqual(summary["enhancement_count"], 10)

    def test_auth_flow_cassette(self) -> None:
        tape = replay_cassette("post_run_auth_flow.json")
        self.assertEqual(tape["step_count"], 2)


if __name__ == "__main__":
    unittest.main()
