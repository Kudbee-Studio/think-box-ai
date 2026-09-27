"""KUDBEECLI Phase 2 deepen — toolkit and CLI integration tests (PR #178)."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from thinkbox.cli import build_parser, dispatch
from thinkbox.cli_inspect import CLI_EXIT_OK
from thinkbox.cli_phase2 import bind_receipt_hermetic, load_config_from_env, negotiate
from thinkbox.cli_phase2.errors import CliToolkitError
from thinkbox.cli_phase2.fixtures import load_fixture
from thinkbox.cli_phase2.inspect_status import cli_health_report
from thinkbox.cli_phase2.redact import redact_mapping
from thinkbox.cli_phase2.sanitize import sanitize_relative_path
from thinkbox.cli_phase2.secrets import scan_for_secrets


class TestCliPhase2Toolkit(unittest.TestCase):
    def test_config_fail_closed(self) -> None:
        with self.assertRaises(CliToolkitError):
            load_config_from_env({"THINKBOX_CLI_BASE_URL": "ftp://bad"})
        cfg = load_config_from_env({"THINKBOX_CLI_DRY_RUN": "true"})
        self.assertTrue(cfg.dry_run)

    def test_negotiate_capabilities(self) -> None:
        caps = negotiate(("inspect", "json"), ("json", "tasks"))
        self.assertEqual(caps.capabilities, ("json",))

    def test_receipt_bind(self) -> None:
        proof = bind_receipt_hermetic("r1", {"a": 1})
        self.assertTrue(proof.bound)
        self.assertEqual(len(proof.payload_sha256), 64)

    def test_fixture_load(self) -> None:
        doc = load_fixture("health_ok.json")
        self.assertTrue(doc.get("ready"))

    def test_redact_and_sanitize(self) -> None:
        out = redact_mapping({"token": "abcdefghijklmnop"})
        self.assertEqual(out["token"], "[REDACTED]")
        with self.assertRaises(CliToolkitError):
            sanitize_relative_path("../etc/passwd")
        safe = sanitize_relative_path("data/proofs/sample.json")
        self.assertTrue(safe.endswith("sample.json"))

    def test_secret_scan(self) -> None:
        hits = scan_for_secrets("api_key=sk-abcdefghijklmnopqrstuvwxyz")
        self.assertGreaterEqual(len(hits), 1)

    def test_health_report_hermetic(self) -> None:
        report = cli_health_report()
        self.assertFalse(report["live_api_called"])
        self.assertIn("environment", report)


class TestCliPhase2Commands(unittest.TestCase):
    def test_cli_health_json(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["cli", "health", "--json"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = dispatch(args)
        self.assertEqual(code, CLI_EXIT_OK)
        payload = json.loads(buf.getvalue())
        self.assertFalse(payload["live_api_called"])

    def test_cli_dry_run(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["cli", "dry-run", "--json"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = dispatch(args)
        self.assertEqual(code, CLI_EXIT_OK)
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["dry_run"])


if __name__ == "__main__":
    unittest.main()
