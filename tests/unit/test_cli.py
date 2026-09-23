"""Unit tests for thinkbox.cli (KUDBEECLI Phase 1 wiring)."""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from thinkbox.cli import build_parser, dispatch, main
from thinkbox.cli_inspect import CLI_EXIT_FAIL, CLI_EXIT_OK, CLI_EXIT_USAGE
from thinkbox.ledger import ActionLedger

ROOT = Path(__file__).resolve().parents[2]
PROOF_SAMPLE = ROOT / "data/thinkboxmd/big_swarm_20260921_135330.json"


class TestCliParser(unittest.TestCase):
    def test_phase1_subcommands_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["swarm", "agents", "--json"])
        self.assertEqual(args.command, "swarm")
        self.assertEqual(args.swarm_command, "agents")
        self.assertTrue(args.json)

    def test_version_flag(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["--version"])
        self.assertEqual(ctx.exception.code, 0)

    def test_no_command_exits_usage(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            main([])
        self.assertEqual(ctx.exception.code, CLI_EXIT_USAGE)


class TestCliEnvStatus(unittest.TestCase):
    def test_env_status_json(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["env", "status", "--json"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = dispatch(args)
        self.assertEqual(code, CLI_EXIT_OK)
        payload = json.loads(buf.getvalue())
        self.assertIn("substrate", payload)


class TestCliLedgerVerify(unittest.TestCase):
    def test_ledger_verify_fail_closed_missing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["ledger", "verify", "--path", "/no/ledger.db", "--json"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = dispatch(args)
        self.assertEqual(code, CLI_EXIT_FAIL)

    def test_ledger_verify_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.db"
            ActionLedger(path).append("a", "c", "x", True, "ok", {})
            parser = build_parser()
            args = parser.parse_args(["ledger", "verify", "--path", str(path), "--json"])
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = dispatch(args)
            self.assertEqual(code, CLI_EXIT_OK)
            self.assertTrue(json.loads(buf.getvalue())["valid"])


class TestCliProofCheck(unittest.TestCase):
    def test_proof_check_invalid_path(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["proof", "check", "/missing.json", "--json"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = dispatch(args)
        self.assertEqual(code, CLI_EXIT_FAIL)

    def test_proof_check_valid_when_artifact_present(self) -> None:
        if not PROOF_SAMPLE.is_file():
            self.skipTest("proof artifact missing")
        parser = build_parser()
        args = parser.parse_args(["proof", "check", str(PROOF_SAMPLE), "--json"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = dispatch(args)
        self.assertEqual(code, CLI_EXIT_OK)


class TestCliSwarm(unittest.TestCase):
    def test_swarm_agents_json(self) -> None:
        if not PROOF_SAMPLE.is_file():
            self.skipTest("proof artifact missing")
        parser = build_parser()
        proof_dir = str(PROOF_SAMPLE.parent)
        args = parser.parse_args(
            ["swarm", "agents", "--proof-dir", proof_dir, "--limit", "1", "--json"]
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = dispatch(args)
        self.assertEqual(code, CLI_EXIT_OK)
        data = json.loads(buf.getvalue())
        self.assertGreaterEqual(data["proofs_considered"], 1)

    def test_swarm_status_json(self) -> None:
        if not PROOF_SAMPLE.is_file():
            self.skipTest("proof artifact missing")
        parser = build_parser()
        args = parser.parse_args(
            [
                "swarm",
                "status",
                "--proof-dir",
                str(PROOF_SAMPLE.parent),
                "--limit",
                "2",
                "--json",
            ]
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = dispatch(args)
        self.assertEqual(code, CLI_EXIT_OK)


class TestCliSessionList(unittest.TestCase):
    def test_session_list_does_not_crash(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["session", "list", "--json", "--limit", "5"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = dispatch(args)
        self.assertEqual(code, CLI_EXIT_OK)
        self.assertIn("sessions", json.loads(buf.getvalue()))


class TestCliSessionInspect(unittest.TestCase):
    def test_session_inspect_missing_returns_fail(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["session", "inspect", "--id", "tb_sess_nonexistent"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = dispatch(args)
        self.assertEqual(code, CLI_EXIT_FAIL)


if __name__ == "__main__":
    unittest.main()
