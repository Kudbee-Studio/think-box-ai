import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from core.runtime.agent import Agent, Goal, ThinkBox
from core.runtime.planner import Planner
from core.runtime.thinkbox import ThinkBoxLifecycle

class TestRuntimeWiring(unittest.TestCase):
    def test_planner_is_async_and_returns_steps(self):
        planner = Planner()
        tb = ThinkBox(goal=Goal(statement="test", success_criteria=[]))
        steps = asyncio.run(planner.plan(tb))
        self.assertTrue(len(steps) > 0)
        self.assertEqual(steps[0].id, "step-1")

    def test_agent_awaits_planner_and_executes_step(self):
        # Mock actor and observer to isolate planner
        mock_actor = MagicMock()
        mock_actor.execute_step = AsyncMock(return_value={"status": "success"})
        mock_observer = MagicMock()
        mock_observer.validate = MagicMock(return_value=True)
        agent = Agent(agent_id="a1")
        goal = Goal(statement="test", success_criteria=[])
        planner = Planner()
        # Run full loop
        result = asyncio.run(agent.run(goal, planner=planner, actor=mock_actor, observer=mock_observer))
        self.assertEqual(result["status"], "success")
        # Ensure actor was called (provider would be invoked inside planner if it existed)
        mock_actor.execute_step.assert_awaited()

if __name__ == "__main__":
    unittest.main()
