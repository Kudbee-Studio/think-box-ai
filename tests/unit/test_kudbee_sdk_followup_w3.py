"""Kudbee SDK follow-up wave 3 deepen tests (PR #191)."""

from __future__ import annotations

import unittest

from thinkbox.kudbee_sdk_followup_w3 import (
    DEFAULT_CLIENT_CAPABILITIES,
    KudbeeSdkFollowupW3Client,
    TwinFederationStub,
    load_config_from_env,
    negotiate,
)
from thinkbox.kudbee_sdk_followup_w3.cassette import list_cassette_names, replay_cassette
from thinkbox.kudbee_sdk_followup_w3.errors import SdkFollowupW3Error
from thinkbox.kudbee_sdk_followup_w3.fixtures import fixture_exists, load_fixture
from thinkbox.kudbee_sdk_followup_w3.integrate import integration_summary, run_feature_demo
from thinkbox.kudbee_sdk_followup_w3.negotiation import compatible_with_server
from thinkbox.kudbee_sdk_followup_w3.health import ReadinessTier, classify_readiness
from thinkbox.kudbee_sdk_followup_w3.pagination import Page, decode_cursor, encode_cursor, filter_items, iter_pages
from thinkbox.kudbee_sdk_followup_w3.rate_limit import jitter_backoff_ms
from thinkbox.kudbee_sdk_followup_w3.retry import is_idempotent_method
from thinkbox.kudbee_sdk_followup_w3.sdk_status_report import route_catalog_w3, run_hermetic_sdk_w3_demo
from thinkbox.kudbee_sdk_followup_w3.secrets import scan_text_for_secrets
from thinkbox.kudbee_sdk_followup_w3.session_bridge import SessionBridgeW3
from thinkbox.kudbee_sdk_followup_w3.task_bridge import TaskBridgeW3
from thinkbox.kudbee_sdk_followup_w3.docker_bridge import describe_docker_compose_bridge
from thinkbox.kudbee_sdk_followup_w3.webhook_signature import parse_signature_header, sign_payload, verify_signature


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

    def test_wave3_deepen_helpers(self) -> None:
        cursor = encode_cursor({"page": 2})
        self.assertEqual(decode_cursor(cursor)["page"], 2)
        self.assertIn("twin_federation", DEFAULT_CLIENT_CAPABILITIES)
        self.assertTrue(fixture_exists("health_ok.json"))
        self.assertIn("webhook_flow.json", list_cassette_names())
        algo, _ = parse_signature_header(sign_payload(b"s", b"{}"))
        self.assertEqual(algo, "sha256")
        self.assertTrue(is_idempotent_method("GET"))
        self.assertGreater(jitter_backoff_ms(100, 1), 100)
        client = KudbeeSdkFollowupW3Client.from_env()
        fed = client.twin_federation()
        self.assertEqual(fed["peer_count"], 0)
        self.assertEqual(classify_readiness(True, "dry-run-w3"), ReadinessTier.READY)
        session = SessionBridgeW3.open("s-tag")
        session.set_tag("env", "hermetic")
        self.assertEqual(session.tags["env"], "hermetic")
        task = TaskBridgeW3.create("t-cancel", "x")
        cancelled = task.cancel_hermetic()
        self.assertEqual(cancelled["status"], "failed")
        mesh = TwinFederationStub()
        mesh.register_peer("t1", "s1")
        self.assertEqual(mesh.federation_snapshot()["peer_count"], 1)
        feat = run_feature_demo("twin_federation")
        self.assertEqual(feat["peer_count"], 1)
        self.assertTrue(scan_text_for_secrets("key = REDACTED").clean)


if __name__ == "__main__":
    unittest.main()
