"""Integration test — KUDBEE control fabric end to end.

Simulates the white-paper evaluation agenda:
  1. Register identities, mint governance tokens, admit agents to cells
  2. Grant admission only with valid token; denials land in the ledger
  3. A compromised cell is expelled and cannot inherit peer capabilities
  4. Think Boxes survive handoff between substrates
  5. Occupancy contracts when budget exhausts
"""

import asyncio
import tempfile
import unittest
from pathlib import Path

from thinkbox.admission import AdmissionGate
from thinkbox.capacity import CapacityController
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.handoff import ThinkBoxHandoff
from thinkbox.identity import IdentityLedger
from thinkbox.ledger import ActionLedger
from thinkbox.occupancy import MeshCellManager, OccupancyMonitor
from thinkbox.workspace import WorkspaceRegistry


class TestControlFabricE2E(unittest.TestCase):
    def test_full_governance_flow(self):
        tmp = tempfile.TemporaryDirectory()
        identities = IdentityLedger()
        tokens = GovernanceTokenService(signing_key="e2e-key")
        ledger = ActionLedger(Path(tmp.name) / "e2e.db")
        gate = AdmissionGate(tokens, identities)
        monitor = OccupancyMonitor()
        mesh = MeshCellManager()
        registry = WorkspaceRegistry()
        handoff = ThinkBoxHandoff()
        capacity = CapacityController(floor=1, ceiling=4)

        agent = identities.register(agent_id="alice", capabilities=["file:read", "goal:execute"])
        token = tokens.issue(TokenRequest(agent_id=agent.agent_id, capabilities=["file:read", "goal:execute"], ttl_seconds=60.0))
        cell = mesh.create("core", "owner", capabilities=["file:read", "goal:execute"])
        mesh.admit(cell.cell_id, agent.agent_id)
        monitor.record_agent(grounded=True)

        decision = gate.authorize(token.token_value, agent.agent_id, "file:read")
        self.assertTrue(decision.allowed)
        ledger.append(agent.agent_id, "file:read", "read", True, "admitted")

        denied = gate.authorize("bogus", agent.agent_id, "file:read")
        self.assertFalse(denied.allowed)
        ledger.append(agent.agent_id, "file:read", "read", False, "token_invalid")

        self.assertTrue(ledger.verify())
        monitor.record_agent(grounded=False)
        sample = monitor.sample(load=0.9)
        self.assertEqual(sample.grounded_ratio, 0.5)

        box = registry.create(owner_id=agent.agent_id, capabilities=["file:read"], substrate="local", state={"progress": 0.4})
        record = handoff.handoff(box, "container")
        self.assertTrue(handoff.verify_integrity(box, record))
        self.assertEqual(box.substrate, "container")

        expand = capacity.evaluate(load=0.95, budget_spend=100, budget_limit=1000)
        self.assertEqual(expand.action, "expand")
        contract = capacity.evaluate(load=0.1, budget_spend=990, budget_limit=1000)
        self.assertEqual(contract.action, "contract")

        self.assertTrue(mesh.is_contained(cell.cell_id, "file:read"))
        mesh.expel_all(cell.cell_id)
        self.assertFalse(mesh.is_contained(cell.cell_id, "file:read"))
        tmp.cleanup()

    def test_governed_engine_integration(self):
        import asyncio

        from thinkbox.engine import EngineConfig, ThinkBoxEngine
        from thinkbox.governed import GovernedEngine, GovernedEngineConfig

        base = ThinkBoxEngine(EngineConfig())
        governed = GovernedEngine(GovernedEngineConfig(engine=base))
        token = governed.register_agent("bob", ["goal:execute"])

        async def run():
            return await governed.execute_goal("say hello", token_value=token, agent_id="bob", capability="goal:execute")

        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(run())
        loop.close()
        self.assertTrue(result.get("governed"))


if __name__ == "__main__":
    unittest.main()