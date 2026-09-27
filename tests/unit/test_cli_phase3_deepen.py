"""KUDBEECLI Phase 3 deepen — toolkit and CLI integration tests (PR #180)."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout

from thinkbox.cli import build_parser, dispatch
from thinkbox.cli_inspect import CLI_EXIT_OK
from thinkbox.cli_phase3 import emit_formatted, load_phase3_config_from_env, negotiate_phase3
from thinkbox.cli_phase3.cassette import replay_cassette
from thinkbox.cli_phase3.errors import CliPhase3Error
from thinkbox.cli_phase3.exit_codes import map_outcome
from thinkbox.cli_phase3.formatters import OutputFormat
from thinkbox.cli_phase3.job_mirror import create_job_hermetic
from thinkbox.cli_phase3.path_sandbox import resolve_sandbox_path
from thinkbox.cli_phase3.sdk_bridge import cli_sdk_dry_run
from thinkbox.cli_phase3.secrets import scan_text_for_secrets
from thinkbox.cli_phase3.status_report import cli_phase3_status_report


class TestCliPhase3Toolkit(unittest.TestCase):
    def test_config_and_profile(self) -> None:
        cfg = load_phase3_config_from_env({"THINKBOX_CLI_PROFILE": "default"})
        self.assertEqual(cfg.active_profile, "default")
        with self.assertRaises(CliPhase3Error):
            load_phase3_config_from_env({"THINKBOX_CLI_OUTPUT_FORMAT": "xml"})

    def test_negotiate_and_formatters(self) -> None:
        caps = negotiate_phase3(("batch", "job_mirror"), ("batch", "cassette"))
        self.assertEqual(caps.capabilities, ("batch",))
        table = emit_formatted({"a": 1}, OutputFormat.JSON)
        self.assertIn('"a"', table)

    def test_job_and_cassette(self) -> None:
        job = create_job_hermetic("demo")
        self.assertTrue(job.job_id.startswith("tb_job_cli3_"))
        replay = replay_cassette("health_flow")
        self.assertTrue(replay["replayed"])

    def test_sandbox_and_secrets(self) -> None:
        path = resolve_sandbox_path("kudbee_cli/pr180_features.json", ("data",))
        self.assertTrue(path.name.endswith("pr180_features.json"))
        with self.assertRaises(CliPhase3Error):
            resolve_sandbox_path("../etc/passwd", ("data",))
        hits = scan_text_for_secrets("token=sk-abcdefghijklmnopqrstuvwxyz123456")
        self.assertGreaterEqual(len(hits), 1)

    def test_sdk_bridge_and_exit_codes(self) -> None:
        payload = cli_sdk_dry_run("/v1/think", {"goal": "x"})
        self.assertFalse(payload["live_api_called"])
        self.assertEqual(map_outcome("ok"), 0)

    def test_status_report(self) -> None:
        report = cli_phase3_status_report()
        self.assertFalse(report["live_api_called"])
        self.assertEqual(report["four_state_max"], "TEST_VERIFIED")


class TestCliPhase3Commands(unittest.TestCase):
    def test_cli_status_json(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["cli", "status", "--format", "json"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = dispatch(args)
        self.assertEqual(code, CLI_EXIT_OK)
        payload = json.loads(buf.getvalue())
        self.assertFalse(payload["live_api_called"])

    def test_cli_job_create(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["cli", "job", "create", "phase3-demo", "--format", "json"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = dispatch(args)
        self.assertEqual(code, CLI_EXIT_OK)
        payload = json.loads(buf.getvalue())
        self.assertIn("job_id", payload)


if __name__ == "__main__":
    unittest.main()
