"""Unit tests for PR #201 Upstash Box access verification."""

from __future__ import annotations

import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from thinkbox.execution_adapter import ENV_TOKEN, ENV_URL, _sha256_bytes
from thinkbox.upstash_box_access import (
    ADAPTER_REQUIRED_KEYS,
    DOCUMENT_ONLY_UNUSED_KEYS,
    AccessClass,
    HttpProbeResult,
    assert_no_secret_material,
    binding_blocker_suffix,
    binding_gate_status,
    classify_access,
    classify_http_body_reason,
    cursor_secret_catalog_listed,
    endpoint_identity,
    parse_cursor_secret_catalog,
    presence_inventory,
    run_access_probe,
)


class _BoxOkHandler(BaseHTTPRequestHandler):
    artifact_content = '{"proof":"KUD_BEE_UPSTASH_ACCESS_PROOF"}'
    artifact_hash = _sha256_bytes(artifact_content.encode("utf-8"))

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        _ = self.rfile.read(length)
        body = json.dumps(
            {
                "exit_code": 0,
                "hostname": "box",
                "os": "linux",
                "output": self.artifact_content,
                "artifact_name": "access_proof.json",
                "artifact_content": self.artifact_content,
                "artifact_hash": self.artifact_hash,
            }
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args: object) -> None:
        return


class TestCursorSecretCatalog(unittest.TestCase):
    def test_parse_catalog_json_list_names_only(self) -> None:
        env = {
            "CLOUD_AGENT_ALL_SECRET_NAMES": '["UPSTASH_PUBLIC_BOX_URL","UPSTASH_BOX_API_KEY"]',
        }
        catalog = parse_cursor_secret_catalog(env)
        self.assertEqual(catalog, ("UPSTASH_PUBLIC_BOX_URL", "UPSTASH_BOX_API_KEY"))

    def test_catalog_listed_flags(self) -> None:
        env = {"CLOUD_AGENT_ALL_SECRET_NAMES": "UPSTASH_BOX_API_KEY,UPSTASH_PUBLIC_BOX_TOKEN"}
        listed = cursor_secret_catalog_listed(environ=env)
        self.assertFalse(listed[ENV_URL])
        self.assertTrue(listed[ENV_TOKEN])

    def test_binding_gate_registration_when_not_listed(self) -> None:
        ready, stage = binding_gate_status(
            catalog_listed={ENV_URL: False, ENV_TOKEN: False},
            presence={ENV_URL: False, ENV_TOKEN: False},
            catalog_available=True,
        )
        self.assertFalse(ready)
        self.assertEqual(stage, "REGISTRATION")

    def test_binding_gate_injection_when_listed_not_present(self) -> None:
        ready, stage = binding_gate_status(
            catalog_listed={ENV_URL: True, ENV_TOKEN: True},
            presence={ENV_URL: True, ENV_TOKEN: False},
            catalog_available=True,
        )
        self.assertFalse(ready)
        self.assertEqual(stage, "INJECTION")

    def test_binding_suffix_when_names_not_in_catalog(self) -> None:
        suffix = binding_blocker_suffix(
            url_present=False,
            token_present=False,
            catalog_listed={ENV_URL: False, ENV_TOKEN: False},
            catalog_available=True,
        )
        self.assertIn("not registered", suffix)

    def test_run_probe_includes_catalog_when_env_set(self) -> None:
        env = {
            "CLOUD_AGENT_ALL_SECRET_NAMES": "UPSTASH_BOX_API_KEY",
            ENV_URL: "",
            ENV_TOKEN: "",
        }
        report = run_access_probe(environ=env, allow_execute=True)
        self.assertTrue(report.cursor_secret_catalog_available)
        self.assertFalse(report.cursor_secret_catalog_listed[ENV_URL])
        self.assertIn("cursor_secret_catalog", report.blocker)


class TestPresenceAndIdentity(unittest.TestCase):
    def test_presence_names_only_booleans(self) -> None:
        inv = presence_inventory(
            {"UPSTASH_PUBLIC_BOX_URL": "https://example.box.upstash.com", "UPSTASH_BOX_API_KEY": "x"},
        )
        self.assertEqual(set(inv), set(ADAPTER_REQUIRED_KEYS + DOCUMENT_ONLY_UNUSED_KEYS))
        self.assertTrue(inv[ENV_URL])
        self.assertFalse(inv[ENV_TOKEN])
        self.assertTrue(inv["UPSTASH_BOX_API_KEY"])
        dumped = json.dumps(inv)
        self.assertNotIn("https://", dumped)
        self.assertNotIn("example", dumped)

    def test_presence_treats_whitespace_as_absent(self) -> None:
        inv = presence_inventory({ENV_URL: "   ", ENV_TOKEN: "\n"})
        self.assertFalse(inv[ENV_URL])
        self.assertFalse(inv[ENV_TOKEN])

    def test_endpoint_identity_drops_userinfo_and_query(self) -> None:
        ident = endpoint_identity("https://user:secret@wanted.preview.box.upstash.com/run?token=abc")
        assert ident is not None
        self.assertTrue(ident["has_userinfo"])
        self.assertEqual(ident["hostname"], "wanted.preview.box.upstash.com")
        dumped = json.dumps(ident)
        self.assertNotIn("secret", dumped)
        self.assertNotIn("token=abc", dumped)
        self.assertNotIn("user:", dumped)
        self.assertNotIn("/run", dumped)

    def test_endpoint_identity_empty(self) -> None:
        self.assertIsNone(endpoint_identity(""))
        self.assertIsNone(endpoint_identity(None))


class TestClassification(unittest.TestCase):
    def test_a_missing_both(self) -> None:
        cls, reason = classify_access(
            url_present=False,
            token_present=False,
            http_result=None,
            receipt_status="NOT_CONFIGURED",
            receipt_verified=False,
        )
        self.assertEqual(cls, AccessClass.ENV_NOT_CONFIGURED)
        self.assertIn(ENV_URL, reason)
        self.assertIn(ENV_TOKEN, reason)

    def test_a_url_without_token(self) -> None:
        cls, reason = classify_access(
            url_present=True,
            token_present=False,
            http_result=HttpProbeResult(200, "ok"),
            receipt_status="NOT_CONFIGURED",
            receipt_verified=False,
        )
        self.assertEqual(cls, AccessClass.ENV_NOT_CONFIGURED)
        self.assertIn(ENV_TOKEN, reason)

    def test_b_auth_rejected(self) -> None:
        cls, _ = classify_access(
            url_present=True,
            token_present=True,
            http_result=HttpProbeResult(401, "unauthorized"),
            receipt_status="REMOTE_FAILED",
            receipt_verified=False,
        )
        self.assertEqual(cls, AccessClass.ENDPOINT_REACHABLE_AUTH_FAILED)

    def test_c_reachable_without_execution(self) -> None:
        cls, _ = classify_access(
            url_present=True,
            token_present=True,
            http_result=HttpProbeResult(200, "ok"),
            receipt_status=None,
            receipt_verified=False,
        )
        self.assertEqual(cls, AccessClass.ENDPOINT_REACHABLE)

    def test_d_requires_verified_completed(self) -> None:
        cls, _ = classify_access(
            url_present=True,
            token_present=True,
            http_result=HttpProbeResult(200, "ok"),
            receipt_status="COMPLETED",
            receipt_verified=True,
        )
        self.assertEqual(cls, AccessClass.REMOTE_EXECUTION_VERIFIED)

    def test_http_200_is_not_d_without_receipt(self) -> None:
        cls, _ = classify_access(
            url_present=True,
            token_present=True,
            http_result=HttpProbeResult(200, "ok"),
            receipt_status="REMOTE_FAILED",
            receipt_verified=False,
        )
        self.assertEqual(cls, AccessClass.ENDPOINT_REACHABLE)

    def test_e_preview_not_found(self) -> None:
        cls, reason = classify_access(
            url_present=True,
            token_present=True,
            http_result=HttpProbeResult(404, "preview_not_found"),
            receipt_status="REMOTE_FAILED",
            receipt_verified=False,
        )
        self.assertEqual(cls, AccessClass.BLOCKED)
        self.assertIn("preview not found", reason)

    def test_e_network(self) -> None:
        cls, _ = classify_access(
            url_present=True,
            token_present=True,
            http_result=HttpProbeResult(None, "network_error", error_type="gaierror"),
            receipt_status=None,
            receipt_verified=False,
        )
        self.assertEqual(cls, AccessClass.BLOCKED)

    def test_preview_reason_requires_exact_public_body(self) -> None:
        self.assertEqual(classify_http_body_reason(404, "preview not found"), "preview_not_found")
        self.assertEqual(classify_http_body_reason(404, "nope"), "not_found")


class TestRunAccessProbe(unittest.TestCase):
    def test_unconfigured_is_a_without_http(self) -> None:
        report = run_access_probe(
            environ={"UPSTASH_BOX_API_KEY": "must-not-be-used-as-token"},
            allow_network=True,
            allow_execute=True,
            live_http_used=True,
        )
        self.assertEqual(report.classification, AccessClass.ENV_NOT_CONFIGURED)
        self.assertFalse(report.adapter_configured)
        self.assertFalse(report.http_called)
        self.assertFalse(report.live_verified)
        self.assertFalse(report.live_api_called)
        self.assertTrue(report.unused_document_only_present["UPSTASH_BOX_API_KEY"])
        payload = report.to_public_dict()
        assert_no_secret_material(payload, {"UPSTASH_BOX_API_KEY": "must-not-be-used-as-token"})
        self.assertNotIn("must-not-be-used-as-token", json.dumps(payload))
        self.assertEqual(payload["receipt"]["status"], "NOT_CONFIGURED")

    def test_api_key_does_not_configure_adapter(self) -> None:
        report = run_access_probe(
            environ={
                ENV_URL: "https://wanted.preview.box.upstash.com",
                "UPSTASH_BOX_API_KEY": "not-the-adapter-token",
            },
        )
        self.assertFalse(report.adapter_configured)
        self.assertEqual(report.classification, AccessClass.ENV_NOT_CONFIGURED)
        dumped = json.dumps(report.to_public_dict())
        self.assertNotIn("not-the-adapter-token", dumped)

    def test_hermetic_completed_is_not_live_verified(self) -> None:
        server = HTTPServer(("127.0.0.1", 0), _BoxOkHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}"
            report = run_access_probe(
                environ={ENV_URL: url, ENV_TOKEN: "stub-token"},
                allow_network=True,
                allow_execute=True,
                live_http_used=False,
                http_transport=lambda _u, _m: HttpProbeResult(200, "ok"),
            )
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(report.classification, AccessClass.REMOTE_EXECUTION_VERIFIED)
        self.assertFalse(report.live_verified)
        self.assertFalse(report.live_api_called)
        self.assertEqual(report.four_state_max, "TEST_VERIFIED")
        self.assertTrue(report.receipt and report.receipt["verified"])

    def test_secret_leak_detector(self) -> None:
        with self.assertRaises(ValueError):
            assert_no_secret_material({"oops": "super-secret-token"}, {ENV_TOKEN: "super-secret-token"})

    def test_process_env_unconfigured_matches_this_runtime(self) -> None:
        report = run_access_probe(allow_network=False, allow_execute=False, live_http_used=False)
        if os.environ.get(ENV_URL, "").strip() or os.environ.get(ENV_TOKEN, "").strip():
            self.skipTest("official Box env unexpectedly present")
        self.assertEqual(report.classification, AccessClass.ENV_NOT_CONFIGURED)
        self.assertFalse(report.http_called)
        self.assertFalse(report.live_verified)


class TestPr201Gate(unittest.TestCase):
    def test_gate_contract(self) -> None:
        from thinkbox.kilo_pr201_upstash_box_access import validate_features_manifest

        ok, violations = validate_features_manifest()
        self.assertTrue(ok, violations)

    def test_verify_script(self) -> None:
        import subprocess
        import sys

        root = Path(__file__).resolve().parents[2]
        proc = subprocess.run(
            [sys.executable, str(root / "scripts/verify_kilo_pr201_upstash_box_access.py")],
            capture_output=True,
            text=True,
            cwd=root,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        summary = json.loads(proc.stdout)
        self.assertFalse(summary["live_verified"])
        self.assertEqual(summary["this_run_classification"], "A")


if __name__ == "__main__":
    unittest.main()
