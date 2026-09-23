"""Unit tests for KUDBEECLI Phase 2 commands and persistence."""

from __future__ import annotations

import argparse
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from typing import Any


def _ns(**kwargs: Any) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


class TestPersistentAgentRegistry(unittest.TestCase):
    def test_agent_list_persists_across_instances(self) -> None:
        from thinkbox.identity import IdentityLedger
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "identities.db"
            store1 = IdentityLedger(db_path=db)
            store1.register("agent-1", ["read", "write"])
            store1.register("agent-2", ["execute"])
            store2 = IdentityLedger(db_path=db)
            agents = store2.list()
            ids = [a["agent_id"] for a in agents]
            self.assertIn("agent-1", ids)
            self.assertIn("agent-2", ids)

    def test_agent_registry_preserves_capabilities(self) -> None:
        from thinkbox.identity import IdentityLedger
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "identities.db"
            store1 = IdentityLedger(db_path=db)
            store1.register("agent-x", ["read"])
            store2 = IdentityLedger(db_path=db)
            found = store2.get("agent-x")
            self.assertIsNotNone(found)
            self.assertIn("read", found.capabilities)

    def test_agent_registry_preserves_revoke(self) -> None:
        from thinkbox.identity import IdentityLedger
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "identities.db"
            store1 = IdentityLedger(db_path=db)
            store1.register("agent-x", ["read"])
            store1.revoke("agent-x")
            store2 = IdentityLedger(db_path=db)
            found = store2.get("agent-x")
            self.assertIsNotNone(found)
            self.assertTrue(found.revoked)

    def test_agent_registry_in_memory_default(self) -> None:
        from thinkbox.identity import IdentityLedger
        store = IdentityLedger()
        store.register("agent-1", ["read"])
        self.assertEqual(len(store.list()), 1)

    def test_cli_agent_list_empty(self) -> None:
        import thinkbox.cli as cli
        args = _ns(db=None)
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_agent_list(args)
        output = out.getvalue()
        self.assertIn("No registered agents", output)


class TestTracePersistence(unittest.TestCase):
    def test_trace_persists_across_instances(self) -> None:
        from thinkbox.thinktrace import ThinkTraceCapture
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "traces.db"
            store1 = ThinkTraceCapture(max_traces=100, db_path=db)
            t1 = store1.capture("agent-a", "thought 1", evidence_refs=["ref1"])
            t2 = store1.capture("agent-b", "thought 2", evidence_refs=[])
            store2 = ThinkTraceCapture(max_traces=100, db_path=db)
            self.assertEqual(store2.count(), 2)
            found = store2.find_by_id(t1.trace_id)
            self.assertIsNotNone(found)
            self.assertTrue(found.grounded)
            self.assertEqual(found.thought, "thought 1")

    def test_trace_find_by_id_not_found(self) -> None:
        from thinkbox.thinktrace import ThinkTraceCapture
        store = ThinkTraceCapture(max_traces=100)
        found = store.find_by_id("nonexistent")
        self.assertIsNone(found)

    def test_trace_in_memory_default(self) -> None:
        from thinkbox.thinktrace import ThinkTraceCapture
        store = ThinkTraceCapture(max_traces=100)
        t = store.capture("agent", "thought")
        self.assertEqual(store.count(), 1)
        found = store.find_by_id(t.trace_id)
        self.assertIsNotNone(found)

    def test_cli_trace_show_not_found(self) -> None:
        import thinkbox.cli as cli
        args = _ns(trace_id="nonexistent-id", db=None)
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_trace_show(args)
        output = out.getvalue()
        self.assertIn("Trace not found", output)


class TestCLISwarmLive(unittest.TestCase):
    def test_swarm_live_blocked_no_key(self) -> None:
        import thinkbox.cli as cli
        env_val = os.environ.pop("INCEPTION_API_KEY", None)
        try:
            args = _ns()
            with redirect_stdout(io.StringIO()) as out:
                cli.cmd_swarm_live(args)
        except SystemExit as e:
            self.assertEqual(e.code, 1)
        finally:
            if env_val is not None:
                os.environ["INCEPTION_API_KEY"] = env_val

    def test_swarm_live_authorized(self) -> None:
        import thinkbox.cli as cli
        env_val = os.environ.get("INCEPTION_API_KEY")
        os.environ["INCEPTION_API_KEY"] = "test-key-not-live"
        try:
            args = _ns()
            with redirect_stdout(io.StringIO()) as out:
                cli.cmd_swarm_live(args)
            output = out.getvalue()
            self.assertIn("AUTHORIZED", output)
            self.assertIn("founder authorization", output)
        finally:
            if env_val is None:
                os.environ.pop("INCEPTION_API_KEY", None)
            else:
                os.environ["INCEPTION_API_KEY"] = env_val


class TestCLIDashboard(unittest.TestCase):
    def test_dashboard_status(self) -> None:
        import thinkbox.cli as cli
        args = _ns()
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_dashboard_status(args)
        output = out.getvalue()
        self.assertIn("Dashboard Status", output)
        self.assertIn("swarm_dashboard.py", output)
        self.assertIn("Run: python3 experiments/swarm_dashboard.py", output)


class TestCLIReply(unittest.TestCase):
    def test_shell_exit_clean(self) -> None:
        import thinkbox.cli as cli
        import threading
        results = {}

        def run_shell():
            with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
                try:
                    import io as _io
                    sys.stdin = _io.StringIO("exit\n")
                    cli.cmd_shell(_ns())
                except EOFError:
                    pass
                results["out"] = out.getvalue()
                results["err"] = err.getvalue()

        t = threading.Thread(target=run_shell)
        t.start()
        t.join(timeout=5)
        self.assertIn("Shell exited", results.get("out", ""))

    def test_shell_help(self) -> None:
        import thinkbox.cli as cli
        import threading
        results = {}

        def run_shell():
            with redirect_stdout(io.StringIO()) as out:
                try:
                    import io as _io
                    sys.stdin = _io.StringIO("help\nexit\n")
                    cli.cmd_shell(_ns())
                except EOFError:
                    pass
                results["out"] = out.getvalue()

        t = threading.Thread(target=run_shell)
        t.start()
        t.join(timeout=5)
        output = results.get("out", "")
        self.assertIn("KUDBEE CLI Shell", output)
        self.assertIn("swarm agents", output)
        self.assertIn("trace show", output)


class TestCLISwarmPhase2(unittest.TestCase):
    def test_swarm_agents_output(self) -> None:
        import thinkbox.cli as cli
        args = _ns(agents=0)
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_swarm_agents(args)
        output = out.getvalue()
        self.assertIn("Swarm Population: 300", output)

    def test_swarm_status_output(self) -> None:
        import thinkbox.cli as cli
        args = _ns()
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_swarm_status(args)
        output = out.getvalue()
        self.assertIn("Population: 300", output)


class TestCLILedgerPhase2(unittest.TestCase):
    def test_ledger_verify_empty(self) -> None:
        import thinkbox.cli as cli
        args = _ns(path=":memory:")
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_ledger_verify(args)
        output = out.getvalue()
        self.assertIn("Hash chain verified: True", output)


class TestCLIProofPhase2(unittest.TestCase):
    def test_proof_check_validates_existing(self) -> None:
        import thinkbox.cli as cli
        from thinkbox.swarm_stats import load_and_validate_proof
        import glob
        proofs = sorted(glob.glob("data/thinkboxmd/big_swarm_*.json"))
        if not proofs:
            self.skipTest("No proof files found")
        for p in reversed(proofs):
            _, errors = load_and_validate_proof(p)
            if not errors:
                args = _ns(path=p)
                with redirect_stdout(io.StringIO()) as out:
                    cli.cmd_proof_check(args)
                output = out.getvalue()
                self.assertIn("Status: VALID", output)
                return
        self.skipTest("No valid proof files found")


class TestCLIIntegrationPhase2(unittest.TestCase):
    def test_help_contains_all_commands(self) -> None:
        import thinkbox.cli as cli
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            try:
                cli.main()
            except SystemExit:
                pass
        output = out.getvalue() + err.getvalue()
        required = [
            "run", "serve", "benchmark", "stress",
            "session", "swarm", "ledger", "proof",
            "env", "agent", "governance", "config",
            "trace", "receipts", "shell", "dashboard",
        ]
        for cmd in required:
            self.assertIn(cmd, output, f"Missing command: {cmd}")

    def test_persistence_via_cli_agent_list(self) -> None:
        import thinkbox.cli as cli
        from thinkbox.identity import IdentityLedger
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cli_test.db"
            store = IdentityLedger(db_path=db)
            store.register("cli-agent", ["test"])
            args = _ns(db=str(db))
            with redirect_stdout(io.StringIO()) as out:
                cli.cmd_agent_list(args)
            output = out.getvalue()
            self.assertIn("cli-agent", output)


if __name__ == "__main__":
    unittest.main()