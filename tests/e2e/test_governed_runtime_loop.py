"""Phase 1 e2e: governed runtime loop without network (audit F009 scaffold)."""

from __future__ import annotations

import asyncio
import unittest

from thinkbox.engine import EngineConfig, ThinkBoxEngine
from thinkbox.governed import GovernedEngine, GovernedEngineConfig


class TestGovernedRuntimeLoopE2E(unittest.TestCase):
    """Minimal mock-provider-free loop: token → admission → execute_goal → ledger."""

    def test_governed_goal_with_valid_token(self) -> None:
        base = ThinkBoxEngine(EngineConfig())
        governed = GovernedEngine(GovernedEngineConfig(engine=base))
        token = governed.register_agent("e2e-agent", ["goal:execute"])

        async def run() -> dict:
            return await governed.execute_goal(
                "hermetic e2e goal",
                token_value=token,
                agent_id="e2e-agent",
                capability="goal:execute",
            )

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(run())
        finally:
            loop.close()

        self.assertTrue(result.get("governed"))
        self.assertTrue(governed.ledger.verify())

    def test_governed_goal_denied_without_token(self) -> None:
        base = ThinkBoxEngine(EngineConfig())
        governed = GovernedEngine(GovernedEngineConfig(engine=base))
        governed.register_agent("e2e-agent-2", ["goal:execute"])

        async def run() -> dict:
            return await governed.execute_goal(
                "should not run",
                token_value="invalid-token",
                agent_id="e2e-agent-2",
                capability="goal:execute",
            )

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(run())
        finally:
            loop.close()

        self.assertFalse(result.get("governed", True))
        self.assertTrue(governed.ledger.verify())


if __name__ == "__main__":
    unittest.main()
