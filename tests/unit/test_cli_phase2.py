"""KUDBEECLI Phase 2 — persistence, shell, dashboard, swarm live gate."""

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from thinkbox.cli import build_parser, dispatch, shell_execute
from thinkbox.cli_inspect import CLI_EXIT_FAIL, CLI_EXIT_OK, CLI_EXIT_USAGE
from thinkbox.cli_live_gate import swarm_live_authorization_report
from thinkbox.cli_persist import (
    SQLiteIdentityStore,
    SQLiteTraceStore,
    init_persist_files,
    resolve_identity_db_path,
    resolve_trace_db_path,
    sync_identity_ledger_to_sqlite,
    sync_traces_to_sqlite,
)
from thinkbox.cli_shell import CliShell
from thinkbox.identity import IdentityLedger
from thinkbox.thinktrace import ThinkTraceCapture


class TestCliPersistPaths(unittest.TestCase):
    def test_resolve_paths_default_under_data(self) -> None:
        p = resolve_identity_db_path()
        self.assertIn("identity_ledger.db", str(p))
        self.assertIn("think_trace.db", str(resolve_trace_db_path()))

    def test_init_creates_sqlite_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            id_p = Path(tmp) / "id.db"
            tr_p = Path(tmp) / "tr.db"
            with mock.patch.dict(
                os.environ,
                {
                    "THINKBOX_IDENTITY_LEDGER_PATH": str(id_p),
                    "THINKBOX_TRACE_DB_PATH": str(tr_p),
                },
            ):
                payload = init_persist_files(seed=True)
            self.assertTrue(id_p.is_file())
            self.assertTrue(tr_p.is_file())
            self.assertGreaterEqual(payload["identity_count"], 1)

    def test_sync_identity_and_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            id_p = Path(tmp) / "id.db"
            tr_p = Path(tmp) / "tr.db"
            ledger = IdentityLedger()
            ledger.register(agent_id="a1", capabilities=["x"], policy_version="1")
            sync_identity_ledger_to_sqlite(ledger, id_p)
            store = SQLiteIdentityStore(id_p)
            try:
                self.assertEqual(store.count(), 1)
            finally:
                store.close()
            capture = ThinkTraceCapture()
            capture.capture("a1", "thought", evidence_refs=["e1"])
            sync_traces_to_sqlite(capture, tr_p)
            tstore = SQLiteTraceStore(tr_p)
            try:
                self.assertEqual(tstore.stats()["total"], 1)
            finally:
                tstore.close()


class TestCliSwarmLiveGate(unittest.TestCase):
    def test_fail_closed_without_credentials(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            report = swarm_live_authorization_report()
        self.assertFalse(report["authorized"])
        self.assertFalse(report["live_api_called"])

    def test_authorized_only_with_ack_and_provider(self) -> None:
        env = {
            "INCEPTION_API_KEY": "test-key",
            "THINKBOX_SWARM_LIVE_ACK": "1",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            report = swarm_live_authorization_report()
        self.assertTrue(report["authorized"])

    def test_cli_swarm_live_exit_fail_without_ack(self) -> None:
        with mock.patch.dict(os.environ, {"INCEPTION_API_KEY": "k"}, clear=True):
            parser = build_parser()
            args = parser.parse_args(["swarm", "live", "--json"])
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = dispatch(args)
        self.assertEqual(code, CLI_EXIT_FAIL)
        self.assertFalse(json.loads(buf.getvalue())["authorized"])


class TestCliDashboardAndPersistCommands(unittest.TestCase):
    def test_dashboard_status_json(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["dashboard", "status", "--json"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = dispatch(args)
        self.assertEqual(code, CLI_EXIT_OK)
        data = json.loads(buf.getvalue())
        self.assertIn("dashboard_summary", data)
        self.assertFalse(data["live_mercury_queried"])

    def test_persist_status_json(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["persist", "status", "--json"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = dispatch(args)
        self.assertEqual(code, CLI_EXIT_OK)
        self.assertIn("identity_path", json.loads(buf.getvalue()))

    def test_identity_list_missing_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope.db"
            parser = build_parser()
            args = parser.parse_args(["identity", "list", "--db", str(missing), "--json"])
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = dispatch(args)
            self.assertEqual(code, CLI_EXIT_FAIL)


class TestCliShell(unittest.TestCase):
    def test_shell_one_liner_help(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["shell", "-c", "help"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = dispatch(args)
        self.assertEqual(code, CLI_EXIT_OK)
        self.assertIn("Commands", buf.getvalue())

    def test_shell_execute_unknown_returns_usage(self) -> None:
        self.assertEqual(shell_execute(["not-a-command"]), CLI_EXIT_USAGE)

    def test_shell_repl_max_lines(self) -> None:
        inp = io.StringIO("help\nexit\n")
        out = io.StringIO()
        shell = CliShell(shell_execute, input_stream=inp, output_stream=out)
        code = shell.run(max_lines=1)
        self.assertEqual(code, CLI_EXIT_OK)


class TestCliPhase2Parser(unittest.TestCase):
    def test_phase2_subcommands_registered(self) -> None:
        parser = build_parser()
        for argv in (
            ["shell", "-c", "help"],
            ["dashboard", "status"],
            ["swarm", "live", "--check-only"],
            ["persist", "init"],
            ["identity", "path"],
            ["trace", "stats"],
        ):
            args = parser.parse_args(argv)
            self.assertIsNotNone(args.command)


if __name__ == "__main__":
    unittest.main()
