"""Kudbee SDK follow-up deepen tests (PR #179)."""

from __future__ import annotations

import unittest

from thinkbox.kudbee_sdk_followup import negotiate, load_config_from_env, bind_receipt_hermetic
from thinkbox.kudbee_sdk_followup.errors import SdkFollowupError
from thinkbox.kudbee_sdk_followup.fixtures import load_fixture
from thinkbox.kudbee_sdk_followup.negotiation import compatible_with_server
from thinkbox.kudbee_sdk_followup.pagination import Page, batch_collect, filter_items, iter_pages
from thinkbox.kudbee_sdk_followup.sdk_status_report import route_catalog, run_hermetic_sdk_demo
from thinkbox.kudbee_sdk_followup.session_mirror import SdkSessionFollowup
from thinkbox.kudbee_sdk_followup.streaming import SseReconnectPolicy
from thinkbox.kudbee_sdk_followup.task_mirror import SdkTaskFollowup, TaskStatus


class TestKudbeeSdkFollowupDeepen(unittest.TestCase):
    def test_config_fail_closed(self) -> None:
        with self.assertRaises(SdkFollowupError):
            load_config_from_env({"KUDBEE_SDK_FOLLOWUP_BASE_URL": "ftp://bad"})
        cfg = load_config_from_env({"KUDBEE_SDK_FOLLOWUP_DRY_RUN": "true"})
        self.assertTrue(cfg.dry_run)

    def test_negotiation_v2(self) -> None:
        caps = negotiate(("sessions", "tasks"), ("tasks", "json"))
        self.assertIn("tasks", caps.capabilities)
        self.assertTrue(compatible_with_server(2))
        self.assertFalse(compatible_with_server(99))

    def test_pagination_batch_and_filter(self) -> None:
        page = Page(items=(1, 2, 3), next_cursor=None)
        filtered = filter_items(page, lambda x: x > 1)
        self.assertEqual(filtered.items, (2, 3))
        collected = batch_collect(
            lambda c: Page(items=(c or "x",), next_cursor="y" if c is None else None),
            max_pages=2,
        )
        self.assertEqual(collected, ("x", "y"))

    def test_sse_reconnect_policy(self) -> None:
        policy = SseReconnectPolicy(max_attempts=2, base_delay_ms=100)
        self.assertTrue(policy.should_retry(1))
        self.assertFalse(policy.should_retry(2))
        self.assertEqual(policy.delay_for_attempt(2), 200)

    def test_session_and_task_edge_cases(self) -> None:
        session = SdkSessionFollowup("s1")
        session.touch_metadata("k", "v")
        self.assertEqual(session.metadata["k"], "v")
        task = SdkTaskFollowup("t1", "demo")
        task.start()
        task.record_event("step", {"n": 1})
        task.complete({"ok": True})
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(len(task.events), 1)

    def test_fixtures_and_receipt(self) -> None:
        doc = load_fixture("health_ok.json")
        self.assertTrue(doc.get("ready"))
        sessions = load_fixture("sessions_page.json")
        self.assertIn("items", sessions)
        proof = bind_receipt_hermetic("r179", {"feature": "F23"})
        self.assertTrue(proof.bound)

    def test_hermetic_demo_bundle(self) -> None:
        demo = run_hermetic_sdk_demo()
        self.assertFalse(demo["live_api_called"])
        routes = route_catalog()
        self.assertIn("/api/sdk/tasks", routes["routes"])


if __name__ == "__main__":
    unittest.main()
