"""Think Job POST /run deepen tests (PR #184)."""

from __future__ import annotations

import unittest

from thinkbox.think_job_post_run_deepen import validate_run_payload
from thinkbox.think_job_post_run_deepen.cassette import replay_cassette
from thinkbox.think_job_post_run_deepen.config import load_config_from_env
from thinkbox.think_job_post_run_deepen.dry_run import dry_run_post_run
from thinkbox.think_job_post_run_deepen.errors import ThinkJobPostRunDeepenError
from thinkbox.think_job_post_run_deepen.integrate import run_feature_demo
from thinkbox.think_job_post_run_deepen.replay import replay_steps
from thinkbox.think_job_post_run_deepen.secrets import scan_text


class TestThinkJobPostRunDeepen(unittest.TestCase):
    def test_config_fail_closed(self) -> None:
        with self.assertRaises(ThinkJobPostRunDeepenError):
            load_config_from_env({"THINK_JOB_POST_RUN_DEEPEN_DRY_RUN": "false"})
        self.assertTrue(load_config_from_env({"THINK_JOB_POST_RUN_DEEPEN_DRY_RUN": "true"}).dry_run)

    def test_payload_and_dry_run(self) -> None:
        bad = validate_run_payload({"goal": "x"})
        self.assertFalse(bad["valid"])
        good = validate_run_payload(
            {"goal": "g", "agent_id": "a", "governance_token": "t"},
        )
        self.assertTrue(good["valid"])
        run = dry_run_post_run()
        self.assertTrue(run["dry_run"])

    def test_cassette_replay_and_secrets(self) -> None:
        tape = replay_cassette("post_run_flow.json")
        self.assertEqual(tape["step_count"], 3)
        self.assertTrue(scan_text("sk-abcdefghijklmnop"))

    def test_integrate_demo(self) -> None:
        demo = run_feature_demo("cassette")
        self.assertEqual(demo["step_count"], 3)
        out = replay_steps([{"body": {"goal": "g", "agent_id": "a", "governance_token": "t"}}])
        self.assertTrue(out["verification"]["valid"])


if __name__ == "__main__":
    unittest.main()
