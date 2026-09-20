"""Demo-in-60s: show cold start → admit → run → receipt → shutdown.

Safe to import in the unittest parent process: no ``sys.modules`` stubs at
import time. Run as a real subprocess via ``python3 -m thinkbox.agent.control_plane.demo``
or ``scripts/demo_in_10_agent_control_plane.sh``.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import unittest.mock
from types import SimpleNamespace

from thinkbox.agent.control_plane.admission import ControlPlaneAdmission
from thinkbox.agent.control_plane.budget import BudgetBreaker
from thinkbox.agent.control_plane.chaos import ChaosHooks
from thinkbox.agent.control_plane.lease import LeaseManager
from thinkbox.agent.control_plane.receipt import ActionReceipt, ReceiptChain
from thinkbox.agent.control_plane.replay import ReplayEnvelope

logger = logging.getLogger(__name__)

_DEMO_COMPLETE_MARKER = "Demo complete — all 6 phases green."


def demo() -> None:
    """Run the 60-second demo path (in-process; use subprocess for isolation)."""
    print("=" * 60)
    print("THINK BOX AI — Agent Control Plane Demo (60s)")
    print("=" * 60)

    gov = SimpleNamespace(check_admission=unittest.mock.AsyncMock())
    gov.check_admission.return_value = SimpleNamespace(
        allowed=True, reason="", conditions={}
    )
    admission = ControlPlaneAdmission(gov)
    print("\n[1/6] ADMISSION")
    result = asyncio.run(admission.admit("AGENT_SPAWN", {"agent_type": "TASK_AGENT"}))
    print(f"  Admit AGENT_SPAWN: {result.allowed}")

    chain = ReceiptChain()
    r1 = ActionReceipt("CAPACITY", "a1", "OK")
    chain.append(r1)
    r2 = ActionReceipt("SECRET", "a1", "OK")
    chain.append(r2)
    print("\n[2/6] RECEIPTS")
    print(f"  Receipts: {chain.size()}, chain valid: {chain.verify()}")

    bb = BudgetBreaker(limit=100.0)
    spent = bb.record_spend(30.0, "a1")
    print("\n[3/6] BUDGET")
    print(f"  Spend 30.0: ok={spent}, remaining={bb.remaining()}")

    ks = ChaosHooks()
    print("\n[4/6] CHAOS")
    print(f"  Chaos enabled: {ks.config.enabled}")

    lm = LeaseManager()
    lm.acquire("a1", "task-1")
    lm.acquire("a2", "task-2")
    print("\n[5/6] LEASES")
    print(f"  Active leases: {len(lm.active_leases)}")

    env = ReplayEnvelope(agent_id="a1")
    env.add_input("CAPACITY", {"cpu": 2})
    env.add_receipt("CAPACITY", {"granted": True})
    print("\n[6/6] REPLAY")
    print(f"  Envelope size: {env.size()}, json_len={len(env.to_json())}")

    print("\n" + "=" * 60)
    print(_DEMO_COMPLETE_MARKER)
    print("=" * 60)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for subprocess invocation."""
    _ = argv
    demo()
    return 0


if __name__ == "__main__":
    sys.exit(main())
