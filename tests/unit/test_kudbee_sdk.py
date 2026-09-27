"""Unit tests for thinkbox.kudbee_sdk (PR #177)."""

from __future__ import annotations

import unittest

from thinkbox.kudbee_sdk import (
    KudbeeHttpClient,
    bind_receipt_hermetic,
    load_config_from_env,
    negotiate,
)
from thinkbox.kudbee_sdk.degradation import call_or_degrade
from thinkbox.kudbee_sdk.dry_run import build_dry_run_transport, simulate_post
from thinkbox.kudbee_sdk.errors import config_error, validation_error
from thinkbox.kudbee_sdk.fixtures import load_fixture
from thinkbox.kudbee_sdk.health import fetch_health
from thinkbox.kudbee_sdk.pagination import Page, iter_pages
from thinkbox.kudbee_sdk.rate_limit import exponential_backoff, parse_retry_after
from thinkbox.kudbee_sdk.redact import redact_mapping
from thinkbox.kudbee_sdk.retry import default_retry_policy
from thinkbox.kudbee_sdk.sanitize import sanitize_goal_text, sanitize_relative_path
from thinkbox.kudbee_sdk.schema import validate_json
from thinkbox.kudbee_sdk.secrets import scan_for_secrets
from thinkbox.kudbee_sdk.session import SdkSession, SessionState
from thinkbox.kudbee_sdk.streaming import parse_sse_block, parse_sse_chunk
from thinkbox.kudbee_sdk.tasks import SdkTask, TaskStatus
from thinkbox.kudbee_sdk.transport import HttpResponse, InMemoryTransport
from thinkbox.kudbee_sdk.websocket_envelope import validate_ws_message


class TestKudbeeSdkConfig(unittest.TestCase):
    def test_load_config_fail_closed(self) -> None:
        with self.assertRaises(Exception):
            load_config_from_env({"KUDBEE_SDK_BASE_URL": "ftp://bad"})
        cfg = load_config_from_env({"KUDBEE_SDK_DRY_RUN": "true"})
        self.assertTrue(cfg.dry_run)
        summary = cfg.redacted_summary()
        self.assertIn("base_url", summary)

    def test_redact_secrets(self) -> None:
        out = redact_mapping({"api_key": "secret", "note": "Bearer abcdefghijklmnop"})
        self.assertEqual(out["api_key"], "[REDACTED]")


class TestKudbeeSdkHttp(unittest.TestCase):
    def test_retry_on_500(self) -> None:
        config = load_config_from_env({"KUDBEE_SDK_BASE_URL": "http://127.0.0.1:9"})
        calls = {"n": 0}

        class FlakyTransport:
            def request(self, method, url, headers, body, timeout_s):
                calls["n"] += 1
                if calls["n"] == 1:
                    return HttpResponse(status=503, headers={}, body=b"{}")
                return HttpResponse(
                    status=200,
                    headers={},
                    body=b'{"ok":true}',
                )

        client = KudbeeHttpClient(config=config, transport=FlakyTransport())
        body = client.get_json("/api/health")
        self.assertTrue(body["ok"])
        self.assertGreaterEqual(calls["n"], 2)

    def test_dry_run_health(self) -> None:
        config = load_config_from_env({"KUDBEE_SDK_DRY_RUN": "1"})
        transport = build_dry_run_transport(config)
        client = KudbeeHttpClient(config=config, transport=transport)
        health = fetch_health(client)
        self.assertTrue(health.ready)


class TestKudbeeSdkFeatures(unittest.TestCase):
    def test_schema_validation(self) -> None:
        validate_json({"type": "x"}, {"type": "object", "required": ["type"], "properties": {"type": {"type": "string"}}})
        with self.assertRaises(Exception):
            validate_json({}, {"type": "object", "required": ["type"]})

    def test_pagination(self) -> None:
        pages = list(
            iter_pages(
                lambda c: Page(items=(c or "a",), next_cursor="b" if c is None else None),
                max_pages=3,
            ),
        )
        self.assertEqual(len(pages), 2)

    def test_sse_parse(self) -> None:
        ev = parse_sse_block("event: ping\ndata: hello")
        self.assertIsNotNone(ev)
        self.assertEqual(ev.data, "hello")
        parsed, rem = parse_sse_chunk("event: a\ndata: 1\n\n")
        self.assertEqual(len(parsed), 1)
        self.assertEqual(rem, "")

    def test_ws_envelope(self) -> None:
        validate_ws_message({"type": "TOKEN", "data": {}})
        with self.assertRaises(Exception):
            validate_ws_message({"data": {}})

    def test_session_task_lifecycle(self) -> None:
        s = SdkSession("s1")
        s.activate()
        self.assertEqual(s.state, SessionState.ACTIVE)
        t = SdkTask("t1", "demo")
        t.start()
        t.complete({"ok": True})
        self.assertEqual(t.status, TaskStatus.COMPLETED)

    def test_sanitize(self) -> None:
        self.assertEqual(sanitize_relative_path("foo/bar"), "foo/bar")
        with self.assertRaises(Exception):
            sanitize_relative_path("../etc/passwd")
        self.assertEqual(sanitize_goal_text("  hi  "), "hi")

    def test_secrets_scan_clean(self) -> None:
        self.assertEqual(scan_for_secrets("hello world"), ())
        self.assertTrue(scan_for_secrets("sk-abcdefghijklmnopqrstuvwxyz"))

    def test_negotiation_and_receipt(self) -> None:
        caps = negotiate(("a", "b"), ("b", "c"))
        self.assertEqual(caps.capabilities, ("b",))
        proof = bind_receipt_hermetic("r1", {"x": 1})
        self.assertTrue(proof.bound)

    def test_degradation(self) -> None:
        def boom() -> str:
            raise ConnectionError("down")

        out = call_or_degrade(boom, lambda: "local")
        self.assertTrue(out.degraded)
        self.assertEqual(out.value, "local")

    def test_fixture_and_dry_post(self) -> None:
        fx = load_fixture("health_ok.json")
        self.assertTrue(fx["ready"])
        sim = simulate_post("/x", {"a": 1})
        self.assertTrue(sim.simulated)

    def test_rate_limit_and_retry_policy(self) -> None:
        advice = parse_retry_after({"Retry-After": "1.5"})
        self.assertIsNotNone(advice)
        pol = default_retry_policy(2)
        self.assertTrue(pol.should_retry("GET", 1, True))
        self.assertFalse(pol.should_retry("POST", 1, True))

    def test_in_memory_transport_404(self) -> None:
        t = InMemoryTransport(routes={})
        resp = t.request("GET", "http://x/", {}, None, 1.0)
        self.assertEqual(resp.status, 404)


if __name__ == "__main__":
    unittest.main()
