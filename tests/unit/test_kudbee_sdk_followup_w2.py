"""Kudbee SDK follow-up wave 2 deepen tests (PR #181)."""

from __future__ import annotations

import unittest

from thinkbox.kudbee_sdk_followup_w2 import KudbeeSdkFollowupW2Client, load_config_from_env, negotiate
from thinkbox.kudbee_sdk_followup_w2.cassette import replay_cassette
from thinkbox.kudbee_sdk_followup_w2.errors import SdkFollowupW2Error
from thinkbox.kudbee_sdk_followup_w2.fixtures import load_fixture
from thinkbox.kudbee_sdk_followup_w2.integrate import integration_summary, run_feature_demo
from thinkbox.kudbee_sdk_followup_w2.negotiation import compatible_with_server
from thinkbox.kudbee_sdk_followup_w2.pagination import Page, filter_items, iter_pages
from thinkbox.kudbee_sdk_followup_w2.sdk_status_report import route_catalog_w2, run_hermetic_sdk_w2_demo
from thinkbox.kudbee_sdk_followup_w2.secrets import scan_text_for_secrets
from thinkbox.kudbee_sdk_followup_w2.session_bridge import SessionBridgeW2
from thinkbox.kudbee_sdk_followup_w2.task_bridge import TaskBridgeW2
from thinkbox.kudbee_sdk_followup_w2.webhook_signature import sign_payload, verify_signature


class TestKudbeeSdkFollowupW2Deepen(unittest.TestCase):
    def test_config_fail_closed(self) -> None:
        with self.assertRaises(SdkFollowupW2Error):
            load_config_from_env({"KUDBEE_SDK_FOLLOWUP_W2_BASE_URL": "ftp://bad"})
        cfg = load_config_from_env({"KUDBEE_SDK_FOLLOWUP_W2_DRY_RUN": "true"})
        self.assertTrue(cfg.dry_run)

    def test_negotiation_v3(self) -> None:
        caps = negotiate(("sessions", "webhooks"), ("webhooks", "occupancy"))
        self.assertEqual(caps.capabilities, ("webhooks",))
        self.assertTrue(compatible_with_server(3))
        self.assertFalse(compatible_with_server(99))

    def test_pagination_and_client(self) -> None:
        page = Page(items=(1, 2), next_cursor=None)
        filtered = filter_items(page, lambda x: x > 1)
        self.assertEqual(filtered.items, (2,))
        collected = iter_pages(lambda c: Page(items=((c or "a",)), next_cursor="b" if c is None else None), max_pages=2)
        self.assertEqual(collected, ("a", "b"))
        client = KudbeeSdkFollowupW2Client.from_env()
        health = client.health()
        self.assertTrue(health["ready"])
        self.assertFalse(health["live_api_called"])

    def test_webhook_cassette_bridges(self) -> None:
        sig = sign_payload(b"secret", b"{}")
        result = verify_signature(b"secret", b"{}", sig, dry_run=True)
        self.assertTrue(result.valid)
        tape = replay_cassette("webhook_flow.json")
        self.assertEqual(tape["step_count"], 3)
        session = SessionBridgeW2.open("s-w2")
        session.link_twin("twin-1")
        self.assertTrue(session.summary()["twin_linked"])
        task = TaskBridgeW2.create("t-w2", "demo")
        out = task.run_hermetic()
        self.assertEqual(out["status"], "completed")

    def test_fixtures_integrate_demo(self) -> None:
        doc = load_fixture("health_ok.json")
        self.assertTrue(doc.get("ready"))
        demo = run_hermetic_sdk_w2_demo()
        self.assertFalse(demo["live_api_called"])
        routes = route_catalog_w2()
        self.assertIn("/api/sdk/v2/capabilities", routes["routes"])
        summary = integration_summary()
        self.assertFalse(summary["live_api_called"])
        feat = run_feature_demo("occupancy")
        self.assertIn("cells", feat)

    def test_secret_scan_clean_sample(self) -> None:
        scan = scan_text_for_secrets("export const x = 1;")
        self.assertTrue(scan.clean)


if __name__ == "__main__":
    unittest.main()
