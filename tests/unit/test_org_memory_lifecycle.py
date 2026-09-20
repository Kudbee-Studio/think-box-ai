"""Hermetic tests: org-memory lifecycle receipts, event hooks, crash-resume."""

from __future__ import annotations

import tempfile
import unittest

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore, redact_mapping
from thinkbox.pr_lifecycle import PRLifecycleConfig, PRLifecycleState
from thinkbox.pr_lifecycle_event_hooks import (
    CIStatusEvent,
    GitHubPREvent,
    HermeticCIStatusEventSource,
    HermeticGitHubPREventSource,
    OrgMemoryResilientRunner,
    PRLifecycleEventCoordinator,
)
from thinkbox.pr_lifecycle_resilience import ResilienceConfig


class TestOrgMemoryReceiptStore(unittest.TestCase):
    def test_append_verify_and_query_by_pr(self) -> None:
        store = OrgMemoryReceiptStore(":memory:")
        store.append_lifecycle(
            run_id="run_a",
            pr_number=106,
            branch="feat/lifecycle-org-memory-ci-hooks",
            from_state="PR_CREATED",
            to_state="IDENTIFY",
            action="identify_pr",
            result="success",
            evidence={"experiment_id": "tb_exp_test_1"},
        )
        store.append_lifecycle(
            run_id="run_a",
            pr_number=106,
            branch="feat/lifecycle-org-memory-ci-hooks",
            from_state="IDENTIFY",
            to_state="EXECUTE",
            action="execute_experiment",
            result="success",
            evidence={"experiment_id": "tb_exp_test_1", "api_key": "secret-value"},
        )
        self.assertTrue(store.verify())
        by_pr = store.query(pr_number=106, limit=10)
        self.assertEqual(len(by_pr), 2)
        self.assertEqual(by_pr[0]["sequence"], 2)
        self.assertEqual(by_pr[0]["evidence"]["api_key"], "[REDACTED]")

        by_exp = store.query(experiment_id="tb_exp_test_1", limit=10)
        self.assertEqual(len(by_exp), 2)

    def test_redact_mapping(self) -> None:
        out = redact_mapping({"authorization": "Bearer x", "nested": {"token": "t"}})
        self.assertEqual(out["authorization"], "[REDACTED]")
        self.assertEqual(out["nested"]["token"], "[REDACTED]")

    def test_time_range_query(self) -> None:
        store = OrgMemoryReceiptStore(":memory:")
        store.append_lifecycle(
            run_id="r",
            pr_number=1,
            branch="b",
            from_state="A",
            to_state="B",
            action="act",
            result="success",
        )
        rows = store.query(since="1970-01-01T00:00:00+00:00", until="2999-01-01T00:00:00+00:00")
        self.assertEqual(len(rows), 1)


class TestEventHooks(unittest.TestCase):
    def _coordinator(self) -> tuple[PRLifecycleEventCoordinator, OrgMemoryReceiptStore]:
        store = OrgMemoryReceiptStore(":memory:")
        coord = PRLifecycleEventCoordinator(store, test_mode=True, default_approvals={"merge": True})
        return coord, store

    def test_github_open_ci_success_learn_never_merge(self) -> None:
        coord, store = self._coordinator()
        gh = HermeticGitHubPREventSource()
        ci = HermeticCIStatusEventSource()
        gh.push(
            GitHubPREvent(
                pr_number=106,
                branch="feat/lifecycle-org-memory-ci-hooks",
                action="opened",
            )
        )
        coord.drain_sources(gh, ci)
        ci.push(
            CIStatusEvent(
                pr_number=106,
                workflow="unittest",
                conclusion="success",
            )
        )
        outcomes = coord.drain_sources(gh, ci)
        self.assertTrue(any(o.get("terminal_state") == PRLifecycleState.LEARN.value for o in outcomes))
        merge = coord.request_merge(106)
        self.assertFalse(merge["merged"])
        self.assertFalse(merge["auto_merge"])
        self.assertTrue(store.verify())

    def test_ci_failure_marks_failed(self) -> None:
        coord, store = self._coordinator()
        gh = HermeticGitHubPREventSource()
        ci = HermeticCIStatusEventSource()
        gh.push(GitHubPREvent(pr_number=107, branch="b", action="opened"))
        coord.drain_sources(gh, ci)
        ci.push(CIStatusEvent(pr_number=107, workflow="unittest", conclusion="failure"))
        outcomes = coord.drain_sources(gh, ci)
        self.assertTrue(any(o.get("action") == "failed" for o in outcomes))
        self.assertTrue(store.verify())


class TestOrgMemoryCrashResume(unittest.TestCase):
    def test_resume_from_org_memory_checkpoint(self) -> None:
        ck = tempfile.mkdtemp()
        org = OrgMemoryReceiptStore(":memory:")
        base = PRLifecycleConfig(
            pr_number=108,
            branch="feat/lifecycle-org-memory-ci-hooks",
            test_mode=True,
            approvals={"merge": True},
        )
        r_cfg = ResilienceConfig(base=base, checkpoint_dir=ck)
        runner = OrgMemoryResilientRunner(r_cfg, org)
        run_id = runner.orchestrator.run_id
        steps = 0
        while runner.orchestrator.current_state not in (
            PRLifecycleState.LEARN.value,
            PRLifecycleState.FAILED.value,
            PRLifecycleState.BLOCKED.value,
        ):
            runner.step_resilient()
            steps += 1
            if steps >= 6:
                break
        self.assertIsNotNone(org.load_checkpoint(run_id))
        resumed = OrgMemoryResilientRunner.resume_from_org_memory(r_cfg, org, run_id)
        result = resumed.continue_after_crash()
        self.assertEqual(result.terminal_state, PRLifecycleState.LEARN.value)
        self.assertTrue(org.verify())
        self.assertGreater(org.count(), 0)


if __name__ == "__main__":
    unittest.main()
