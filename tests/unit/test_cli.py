"""Unit tests for KUDBEECLI commands in thinkbox/cli.py."""

from __future__ import annotations

import argparse
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from typing import Any


def _ns(**kwargs: Any) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


class TestCLISwarmAgents(unittest.TestCase):
    def test_swarm_agents_output(self) -> None:
        import thinkbox.cli as cli
        args = _ns(agents=0)
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_swarm_agents(args)
        output = out.getvalue()
        self.assertIn("Swarm Population: 300", output)
        self.assertIn("Unique task IDs: 300", output)

    def test_swarm_agents_flag_ignored(self) -> None:
        import thinkbox.cli as cli
        args = _ns(agents=999)
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_swarm_agents(args)
        output = out.getvalue()
        self.assertIn("Note: --agents 999 requested", output)


class TestCLISwarmStatus(unittest.TestCase):
    def test_swarm_status_output(self) -> None:
        import thinkbox.cli as cli
        args = _ns()
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_swarm_status(args)
        output = out.getvalue()
        self.assertIn("Population: 300", output)


class TestCLILedgerVerify(unittest.TestCase):
    def test_ledger_verify_empty_memory(self) -> None:
        import thinkbox.cli as cli
        args = _ns(path=":memory:")
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_ledger_verify(args)
        output = out.getvalue()
        self.assertIn("Hash chain verified: True", output)

    def test_ledger_verify_with_file(self) -> None:
        import thinkbox.cli as cli
        from thinkbox.ledger import ActionLedger
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            ledger = ActionLedger(db_path)
            ledger.append("a", "cap", "action", True, "ok")
            args = _ns(path=db_path)
            with redirect_stdout(io.StringIO()) as out:
                cli.cmd_ledger_verify(args)
            output = out.getvalue()
            self.assertIn("Hash chain verified: True", output)
            self.assertIn("Entries: 1", output)
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestCLIEnvStatus(unittest.TestCase):
    def test_env_status_redacted(self) -> None:
        import thinkbox.cli as cli
        args = _ns()
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_env_status(args)
        output = out.getvalue()
        self.assertIn("Environment Status (redacted)", output)
        self.assertNotIn("sk-", output)
        self.assertNotIn("ucat_", output)
        self.assertNotIn("ghp_", output)

    def test_env_status_no_secrets(self) -> None:
        import thinkbox.cli as cli
        args = _ns()
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_env_status(args)
        output = out.getvalue()
        sensitive_patterns = ["api_key=", "token=", "secret=", "password="]
        for pattern in sensitive_patterns:
            self.assertNotIn(pattern, output)


class TestCLIConfigRedacted(unittest.TestCase):
    def test_config_redacted_output(self) -> None:
        import thinkbox.cli as cli
        args = _ns()
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_config_redacted(args)
        output = out.getvalue()
        self.assertIn("Config (redacted", output)
        self.assertNotIn("sk-", output)
        self.assertNotIn("ucat_", output)

    def test_config_redacted_no_secrets(self) -> None:
        import thinkbox.cli as cli
        args = _ns()
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_config_redacted(args)
        output = out.getvalue()
        self.assertNotIn("API_KEY=<", output)
        self.assertNotIn("TOKEN=<", output)


class TestCLIAgentList(unittest.TestCase):
    def test_agent_list_empty(self) -> None:
        import thinkbox.cli as cli
        args = _ns()
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_agent_list(args)
        output = out.getvalue()
        self.assertIn("No registered agents", output)


class TestCLIGovernanceCheck(unittest.TestCase):
    def test_governance_check_allowed(self) -> None:
        import thinkbox.cli as cli
        args = _ns()
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_governance_check(args)
        output = out.getvalue()
        self.assertIn("Governance Check", output)
        self.assertIn("Allowed: True", output)
        self.assertNotIn("govt.", output)


class TestCLITraceShow(unittest.TestCase):
    def test_trace_show_not_found(self) -> None:
        import thinkbox.cli as cli
        args = _ns(trace_id="nonexistent-id")
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_trace_show(args)
        output = out.getvalue()
        self.assertIn("Trace not found", output)

    def test_trace_show_captures_trace(self) -> None:
        import thinkbox.cli as cli
        from thinkbox.thinktrace import ThinkTraceCapture
        capture = ThinkTraceCapture(max_traces=10000)
        trace = capture.capture(
            agent_id="cli",
            thought="test thought",
            evidence_refs=["ref1"],
            tags=["test"],
        )
        args = _ns(trace_id=trace.trace_id)
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_trace_show(args)
        output = out.getvalue()
        self.assertIn("Trace not found", output)
        self.assertIn("Total traces in capture:", output)


class TestCLIReceiptsPR(unittest.TestCase):
    def test_receipts_pr_empty(self) -> None:
        import thinkbox.cli as cli
        args = _ns(pr_number=99999)
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_receipts_pr(args)
        output = out.getvalue()
        self.assertIn("receipts: 0", output)


class TestCLIIntegration(unittest.TestCase):
    def test_session_list_stub(self) -> None:
        import thinkbox.cli as cli
        args = _ns(limit=20)
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_session_list(args)
        output = out.getvalue()
        self.assertIn("No session commands", output)

    def test_existing_run_command_help(self) -> None:
        import thinkbox.cli as cli
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            try:
                cli.main()
            except SystemExit:
                pass
        output = out.getvalue() + err.getvalue()
        self.assertIn("run", output)
        self.assertIn("swarm", output)
        self.assertIn("ledger", output)
        self.assertIn("governance", output)


if __name__ == "__main__":
    unittest.main()