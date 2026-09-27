"""Think Job hermetic e2e deepen tests (PR #183)."""

from __future__ import annotations

import unittest

from thinkbox.think_job_e2e_deepen import HermeticThinkJob, advance_job, create_job
from thinkbox.think_job_e2e_deepen.backoff import backoff_schedule
from thinkbox.think_job_e2e_deepen.cassette import replay_cassette
from thinkbox.think_job_e2e_deepen.config import load_config_from_env
from thinkbox.think_job_e2e_deepen.dry_run import dry_run_job_lifecycle, dry_run_status_page
from thinkbox.think_job_e2e_deepen.errors import ThinkJobE2eDeepenError
from thinkbox.think_job_e2e_deepen.fixtures import load_fixture
from thinkbox.think_job_e2e_deepen.integrate import integration_summary, run_feature_demo
from thinkbox.think_job_e2e_deepen.lifecycle_catalog import can_transition, transition_stub
from thinkbox.think_job_e2e_deepen.negotiation import compatible_with_server, negotiate
from thinkbox.think_job_e2e_deepen.receipt_bind import bind_receipt_to_job
from thinkbox.think_job_e2e_deepen.redact import export_jobs_redacted
from thinkbox.think_job_e2e_deepen.replay import replay_actions
from thinkbox.think_job_e2e_deepen.retry import apply_retry_stub
from thinkbox.think_job_e2e_deepen.secrets import scan_text_for_secrets
from thinkbox.think_job_e2e_deepen.status_catalog import lookup_status


class TestThinkJobHermeticE2e(unittest.TestCase):
    def test_config_fail_closed(self) -> None:
        with self.assertRaises(ThinkJobE2eDeepenError):
            load_config_from_env({"THINK_JOB_E2E_DEEPEN_DRY_RUN": "false"})
        cfg = load_config_from_env({"THINK_JOB_E2E_DEEPEN_DRY_RUN": "true"})
        self.assertTrue(cfg.dry_run)

    def test_runner_and_lifecycle(self) -> None:
        job = create_job("j-1")
        self.assertIsInstance(job, HermeticThinkJob)
        out = advance_job(job, "start")
        self.assertEqual(out["state"], "RUNNING")
        self.assertTrue(can_transition("CONFIGURED", "RUNNING"))
        stub = transition_stub("RUNNING", "COMPLETE")
        self.assertTrue(stub["allowed"])

    def test_redact_and_secrets(self) -> None:
        row = {"job_id": "j", "reason": "Bearer secret-token", "metadata": {}}
        exported = export_jobs_redacted([row])
        self.assertTrue(exported["redacted"])
        hits = scan_text_for_secrets("sk-abcdefghijklmnop")
        self.assertTrue(hits)

    def test_cassette_fixture_dry_run(self) -> None:
        tape = replay_cassette("job_lifecycle_flow.json")
        self.assertEqual(tape["step_count"], 3)
        doc = load_fixture("sample_job_status.json")
        self.assertEqual(len(doc["jobs"]), 1)
        lifecycle = dry_run_job_lifecycle()
        self.assertTrue(lifecycle["dry_run"])
        page = dry_run_status_page(limit=5)
        self.assertTrue(page["dry_run"])

    def test_retry_backoff_receipt(self) -> None:
        retry = apply_retry_stub({"taxonomy": "transient", "attempt": 1, "action": "step"})
        self.assertTrue(retry["should_retry"])
        self.assertEqual(backoff_schedule(3), (50, 100, 200))
        bound = bind_receipt_to_job("rcpt-1", "job-1")
        self.assertTrue(bound["bound"])

    def test_integrate_and_status(self) -> None:
        caps = negotiate(("dry_run", "cassette"), ("cassette", "replay"))
        self.assertEqual(caps.capabilities, ("cassette",))
        self.assertTrue(compatible_with_server(1))
        demo = run_feature_demo("dry_run")
        self.assertTrue(demo["dry_run"])
        summary = integration_summary()
        self.assertFalse(summary["live_api_called"])
        status = lookup_status("COMPLETE")
        self.assertTrue(status["found"])

    def test_replay_actions(self) -> None:
        out = replay_actions([{"step": "start"}, {"step": "complete"}])
        self.assertTrue(out["verification"]["valid"])


if __name__ == "__main__":
    unittest.main()
