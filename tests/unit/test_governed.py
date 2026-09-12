"""Unit tests for thinkbox/governed.py — admission-gated engine facade."""

import unittest
from unittest.mock import AsyncMock, Mock

from thinkbox.engine import EngineConfig, ThinkBoxEngine
from thinkbox.governed import GovernedEngine, GovernedEngineConfig


class TestGovernedEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = Mock(spec=ThinkBoxEngine)
        self.engine.events = []
        self.engine.emit = lambda *a, **k: None
        self.governed = GovernedEngine(GovernedEngineConfig(engine=self.engine))

    def test_register_agent_returns_token(self):
        token = self.governed.register_agent("a1", ["file:read"])
        self.assertTrue(token.startswith("govt."))

    def test_authorize_allowed(self):
        token = self.governed.register_agent("a1", ["file:read"])
        decision = self.governed.authorize(token, "a1", "file:read", "read_file")
        self.assertTrue(decision.allowed)

    def test_authorize_denied_and_ledgered(self):
        decision = self.governed.authorize("", "a1", "file:read", "read_file")
        self.assertFalse(decision.allowed)
        entries = self.governed.ledger.entries()
        self.assertEqual(len(entries), 1)
        self.assertFalse(entries[0]["allowed"])

    def test_execute_goal_denied_returns_governed_false(self):
        token = self.governed.register_agent("a1", ["file:read", "goal:execute"])
        self.governed._tokens.revoke_for_agent("a1")
        import asyncio

        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(self.governed.execute_goal("test", token_value=token, agent_id="a1", capability="goal:execute"))
        loop.close()
        self.assertEqual(result["governed"], False)
        self.assertIn("invalid", result["reason"])
        self.engine.execute_goal.assert_not_called()

    def test_execute_goal_without_gate_defers_to_base(self):
        self.engine.execute_goal = AsyncMock(return_value={"completed": 1})
        import asyncio

        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(self.governed.execute_goal("test"))
        loop.close()
        self.assertIn("completed", result)
        self.assertEqual(result["governed"], True)

    def test_execute_goal_with_valid_token_runs(self):
        token = self.governed.register_agent("a1", ["goal:execute"])
        self.engine.execute_goal = AsyncMock(return_value={"completed": 3})
        import asyncio

        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(self.governed.execute_goal("test", token_value=token, agent_id="a1", capability="goal:execute"))
        loop.close()
        self.assertTrue(result["governed"])
        self.assertEqual(result["completed"], 3)


if __name__ == "__main__":
    unittest.main()