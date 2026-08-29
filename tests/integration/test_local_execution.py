"""Integration test for the LocalExecProvider.

This test proves the live local execution path end-to-end:

    echo "KUDBEE_LOCAL_OK"

It runs through the Actor (when wired) so the full chain is exercised:

    KUDBEE
      ↓
    Actor.execute_step
      ↓
    Execution Provider (local)
      ↓
    subprocess
      ↓
    KUDBEE_LOCAL_OK

The test uses only stdlib + the real LocalExecProvider. No mocks, no Docker,
no shell=True. It must pass on the current UpCloud host.
"""

from __future__ import annotations

import asyncio
import unittest

from core.execution import LocalExecProvider
from core.governance.audit import AuditLog
from core.runtime.actor import Actor
from core.runtime.planner import Step


def _run(coro):
    return asyncio.run(coro)


class TestLocalExecutionIntegration(unittest.TestCase):
    """Prove LocalExecProvider works through the Actor path."""

    def test_direct_provider_executes_echo(self) -> None:
        provider = LocalExecProvider()
        self.assertTrue(_run(provider.health_check()))

        result = _run(provider.execute('echo "KUDBEE_LOCAL_OK"', timeout=10.0))
        self.assertEqual(result.return_code, 0)
        self.assertIn("KUDBEE_LOCAL_OK", result.stdout)
        self.assertEqual(result.provider, "local")

    def test_actor_routes_execute_step_to_provider(self) -> None:
        provider = LocalExecProvider()
        actor = Actor(execution_provider=provider)

        step = Step(
            id="local-e2e-1",
            description="echo KUDBEE_LOCAL_OK",
            action="execute",
            command='echo "KUDBEE_LOCAL_OK"',
        )
        agent = type("FakeAgent", (), {"agent_id": "local-test-agent"})()
        think_box = type("FakeThinkBox", (), {})()

        result = _run(actor.execute_step(agent, think_box, step))
        self.assertEqual(result["status"], "success")
        self.assertIn("KUDBEE_LOCAL_OK", result["output"])

    def test_actor_records_evidence_after_execution(self) -> None:
        """Every execute leaves one evidence record via the audit log."""
        provider = LocalExecProvider()
        audit_log = AuditLog()
        actor = Actor(execution_provider=provider, audit_log=audit_log)

        step = Step(
            id="evidence-1",
            description="echo KUDBEE_LOCAL_OK",
            action="execute",
            command='echo "KUDBEE_LOCAL_OK"',
        )
        agent = type("FakeAgent", (), {"agent_id": "evidence-agent"})()
        think_box = type("FakeThinkBox", (), {"think_box_id": "tb-evidence-1"})()

        result = _run(actor.execute_step(agent, think_box, step))
        self.assertEqual(result["status"], "success")

        entries = audit_log.list_entries()
        evidence = [e for e in entries if e["action"] == "execution_evidence"]
        self.assertEqual(len(evidence), 1, "exactly one evidence record expected")

        meta = evidence[0]["metadata"]
        self.assertEqual(meta["provider"], "local")
        self.assertEqual(meta["exit_code"], 0)
        self.assertTrue(meta["ok"])
        self.assertIn("KUDBEE_LOCAL_OK", meta["stdout"])
        self.assertEqual(meta["think_box_id"], "tb-evidence-1")
        self.assertEqual(meta["step_id"], "evidence-1")
        self.assertIn("echo", " ".join(meta["argv"]))
        self.assertIn("started_at", meta)
        self.assertIn("finished_at", meta)

    def test_fail_closed_when_firecracker_requested_but_unavailable(self) -> None:
        from core.execution.firecracker import FirecrackerExecProvider

        provider = FirecrackerExecProvider()
        self.assertFalse(_run(provider.health_check()))

        with self.assertRaises(Exception):
            _run(provider.execute('echo "KUDBEE_LOCAL_OK"', timeout=5.0))

    def test_firecracker_fail_closed_records_evidence_not_success(self) -> None:
        """When Firecracker is unavailable, evidence shows ok=false — not a fake success."""
        from core.execution.firecracker import FirecrackerExecProvider

        provider = FirecrackerExecProvider()
        audit_log = AuditLog()
        actor = Actor(execution_provider=provider, audit_log=audit_log)

        step = Step(
            id="fc-fail-1",
            description="firecracker unavailable",
            action="execute",
            command='echo "KUDBEE_LOCAL_OK"',
        )
        agent = type("FakeAgent", (), {"agent_id": "fc-fail-agent"})()
        think_box = type("FakeThinkBox", (), {"think_box_id": "tb-fc-fail"})()

        result = _run(actor.execute_step(agent, think_box, step))
        self.assertEqual(result["status"], "error")

        entries = audit_log.list_entries()
        evidence = [e for e in entries if e["action"] == "execution_evidence"]
        self.assertEqual(len(evidence), 1, "evidence must record the failure")
        self.assertFalse(evidence[0]["metadata"]["ok"])
        self.assertEqual(evidence[0]["metadata"]["exit_code"], -1)
        self.assertIn("execution_unavailable", evidence[0]["metadata"].get("error", ""))


if __name__ == "__main__":
    unittest.main()
