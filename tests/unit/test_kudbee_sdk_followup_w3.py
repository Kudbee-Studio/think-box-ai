"""Kudbee SDK follow-up wave 3 deepen tests (PR #191)."""

from __future__ import annotations

import unittest

from thinkbox.kudbee_sdk_followup_w3 import KudbeeSdkFollowupW3Client, load_config_from_env, negotiate
from thinkbox.kudbee_sdk_followup_w3.cassette import replay_cassette
from thinkbox.kudbee_sdk_followup_w3.errors import SdkFollowupW3Error
from thinkbox.kudbee_sdk_followup_w3.fixtures import load_fixture
from thinkbox.kudbee_sdk_followup_w3.integrate import integration_summary, run_feature_demo
from thinkbox.kudbee_sdk_followup_w3.negotiation import compatible_with_server
from thinkbox.kudbee_sdk_followup_w3.pagination import Page, filter_items, iter_pages
from thinkbox.kudbee_sdk_followup_w3.sdk_status_report import route_catalog_w3, run_hermetic_sdk_w3_demo
from thinkbox.kudbee_sdk_followup_w3.secrets import scan_text_for_secrets
from thinkbox.kudbee_sdk_followup_w3.session_bridge import SessionBridgeW3
from thinkbox.kudbee_sdk_followup_w3.task_bridge import TaskBridgeW3
from thinkbox.kudbee_sdk_followup_w3.docker_bridge import describe_docker_compose_bridge
from thinkbox.kudbee_sdk_followup_w3.webhook_signature import sign_payload, verify_signature


class TestKudbeeSdkFollowupW3Deepen(unittest.TestCase):
    def test_config_fail_closed(self) -> None:
        with self.assertRaises(SdkFollowupW3Error):
            load_config_from_env({"KUDBEE_SDK_FOLLOWUP_W3_BASE_URL": "ftp://bad"})
        cfg = load_config_from_env({"KUDBEE_SDK_FOLLOWUP_W3_DRY_RUN": "true"})
        self.assertTrue(cfg.dry_run)

    def test_negotiation_v4(self) -> None:
        caps = negotiate(
            ("sessions", "webhooks", "twin_federation"),
            ("webhooks", "occupancy", "twin_federation"),
        )
        self.assertEqual(caps.capabilities, ("twin_federation", "webhooks"))
        self.assertTrue(compatible_with_server(4))
        self.assertFalse(compatible_with_server(99))

    def test_pagination_and_client(self) -> None:
        page = Page(items=(1, 2), next_cursor=None)
        filtered = filter_items(page, lambda x: x > 1)
        self.assertEqual(filtered.items, (2,))
        collected = iter_pages(lambda c: Page(items=((c or "a",)), next_cursor="b" if c is None else None), max_pages=2)
        self.assertEqual(collected, ("a", "b"))
        client = KudbeeSdkFollowupW3Client.from_env()
        health = client.health()
        self.assertTrue(health["ready"])
        self.assertFalse(health["live_api_called"])
        caps = client.capabilities()
        self.assertIn("twin_federation", caps["capabilities"])

    def test_webhook_cassette_bridges(self) -> None:
        sig = sign_payload(b"secret", b"{}")
        result = verify_signature(b"secret", b"{}", sig, dry_run=True)
        self.assertTrue(result.valid)
        tape = replay_cassette("webhook_flow.json")
        self.assertEqual(tape["step_count"], 3)
        session = SessionBridgeW3.open("s-w3")
        session.link_twin("twin-1")
        self.assertTrue(session.summary()["twin_linked"])
        task = TaskBridgeW3.create("t-w3", "demo")
        out = task.run_hermetic()
        self.assertEqual(out["status"], "completed")

    def test_fixtures_integrate_demo(self) -> None:
        doc = load_fixture("health_ok.json")
        self.assertTrue(doc.get("ready"))
        demo = run_hermetic_sdk_w3_demo()
        self.assertFalse(demo["live_api_called"])
        routes = route_catalog_w3()
        self.assertIn("/api/sdk/v3/capabilities", routes["routes"])
        summary = integration_summary()
        self.assertFalse(summary["live_api_called"])
        feat = run_feature_demo("occupancy")
        self.assertIn("cells", feat)

    def test_secret_scan_clean_sample(self) -> None:
        scan = scan_text_for_secrets("export const x = 1;")
        self.assertTrue(scan.clean)

    def test_docker_bridge_hermetic(self) -> None:
        doc = describe_docker_compose_bridge()
        self.assertEqual(doc["compose_service"], "api")
        self.assertFalse(doc["live_api_called"])


if __name__ == "__main__":
    unittest.main()
