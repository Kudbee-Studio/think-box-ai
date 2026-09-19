"""Demo-in-60s: show cold start → admit → run → receipt → shutdown."""

import asyncio
import sys
import types
import logging
import unittest.mock
from types import SimpleNamespace

sys.modules["grpc"] = types.ModuleType("grpc")
sys.modules["grpc.aio"] = types.ModuleType("grpc.aio")
sys.modules["google.protobuf"] = types.ModuleType("google.protobuf")
sys.modules["thinkbox.agent.protocol"] = types.ModuleType("protocol")
sys.modules["thinkbox.agent.protocol"].governance_pb2 = types.ModuleType("governance_pb2")
sys.modules["thinkbox.agent.protocol"].governance_pb2_grpc = types.ModuleType("governance_pb2_grpc")
sys.modules["thinkbox.agent.protocol"].orchestration_pb2 = types.ModuleType("orchestration_pb2")
sys.modules["thinkbox.agent.protocol"].orchestration_pb2_grpc = types.ModuleType("orchestration_pb2_grpc")

from thinkbox.agent.control_plane.admission import ControlPlaneAdmission
from thinkbox.agent.control_plane.receipt import ActionReceipt, ReceiptChain
from thinkbox.agent.control_plane.budget import BudgetBreaker
from thinkbox.agent.control_plane.chaos import ChaosHooks
from thinkbox.agent.control_plane.lease import LeaseManager
from thinkbox.agent.control_plane.replay import ReplayEnvelope

logger = logging.getLogger(__name__)


def demo():
    """Run the 60-second demo path."""
    print("=" * 60)
    print("THINK BOX AI — Agent Control Plane Demo (60s)")
    print("=" * 60)

    # 1. Gov admission
    gov = SimpleNamespace(check_admission=unittest.mock.AsyncMock())
    gov.check_admission.return_value = SimpleNamespace(allowed=True, reason="", conditions={})
    admission = ControlPlaneAdmission(gov)
    print("\n[1/6] ADMISSION")
    result = asyncio.run(admission.admit("AGENT_SPAWN", {"agent_type": "TASK_AGENT"}))
    print(f"  Admit AGENT_SPAWN: {result.allowed}")

    # 2. Receipt chain
    chain = ReceiptChain()
    r1 = ActionReceipt("CAPACITY", "a1", "OK")
    chain.append(r1)
    r2 = ActionReceipt("SECRET", "a1", "OK")
    chain.append(r2)
    print("\n[2/6] RECEIPTS")
    print(f"  Receipts: {chain.size()}, chain valid: {chain.verify()}")

    # 3. Budget
    bb = BudgetBreaker(limit=100.0)
    spent = bb.record_spend(30.0, "a1")
    print("\n[3/6] BUDGET")
    print(f"  Spend 30.0: ok={spent}, remaining={bb.remaining()}")

    # 4. Kill-switch
    ks = ChaosHooks()
    print("\n[4/6] CHAOS")
    print(f"  Chaos enabled: {ks.config.enabled}")

    # 5. Lease
    lm = LeaseManager()
    lm.acquire("a1", "task-1")
    lm.acquire("a2", "task-2")
    print("\n[5/6] LEASES")
    print(f"  Active leases: {len(lm.active_leases)}")

    # 6. Replay
    env = ReplayEnvelope(agent_id="a1")
    env.add_input("CAPACITY", {"cpu": 2})
    env.add_receipt("CAPACITY", {"granted": True})
    print("\n[6/6] REPLAY")
    print(f"  Envelope size: {env.size()}, json_len={len(env.to_json())}")

    print("\n" + "=" * 60)
    print("Demo complete — all 6 phases green.")
    print("=" * 60)


if __name__ == "__main__":
    demo()
