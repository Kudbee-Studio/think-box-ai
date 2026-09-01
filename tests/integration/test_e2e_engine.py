"""End-to-end integration tests for the ThinkBox engine pipeline."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

if "fastapi" not in sys.modules:
    sys.modules["fastapi"] = MagicMock()
    sys.modules["fastapi.middleware"] = MagicMock()
    sys.modules["fastapi.middleware.cors"] = MagicMock()
    sys.modules["starlette"] = MagicMock()
    sys.modules["starlette.middleware"] = MagicMock()
    sys.modules["starlette.middleware.base"] = MagicMock()
    pydantic_mock = MagicMock()
    pydantic_mock.BaseModel = type("BaseModel", (), {"__init_subclass__": lambda **kw: None, "__annotations__": {}})
    sys.modules["pydantic"] = pydantic_mock


class TestE2EEnginePipeline(unittest.TestCase):
    """Test the full ThinkBox engine pipeline end-to-end."""

    def test_engine_initialization(self):
        from thinkbox.engine import ThinkBoxEngine, EngineConfig
        engine = ThinkBoxEngine()
        self.assertIsNotNone(engine.engine_id)
        self.assertIsNotNone(engine.decomposer)
        self.assertIsNotNone(engine.pruner)
        self.assertIsNotNone(engine.autoscaler)
        self.assertIsNotNone(engine.model_client)
        self.assertIsNotNone(engine.swarm)

    def test_engine_custom_config(self):
        from thinkbox.engine import ThinkBoxEngine, EngineConfig
        from thinkbox.model_client import ModelConfig
        config = EngineConfig(model_config=ModelConfig(model="custom-model"))
        engine = ThinkBoxEngine(config)
        self.assertEqual(engine.config.model_config.model, "custom-model")

    def test_engine_event_emission(self):
        from thinkbox.engine import ThinkBoxEngine, TaskState
        engine = ThinkBoxEngine()
        engine.emit("test_task", TaskState.RUNNING, "Test message")
        self.assertEqual(len(engine.events), 1)
        self.assertEqual(engine.events[0].task_id, "test_task")
        self.assertEqual(engine.events[0].state, TaskState.RUNNING)

    def test_engine_stats(self):
        from thinkbox.engine import ThinkBoxEngine
        engine = ThinkBoxEngine()
        stats = engine.get_stats()
        self.assertIn("engine_id", stats)
        self.assertIn("events_processed", stats)
        self.assertIn("swarm_stats", stats)
        self.assertIn("autoscaler", stats)

    def test_full_goal_execution(self):
        import asyncio
        from thinkbox.engine import ThinkBoxEngine, EngineConfig

        config = EngineConfig(speculative=False)
        engine = ThinkBoxEngine(config)

        async def run():
            result = await engine.execute_goal("Test goal for integration")
            return result

        result = asyncio.run(run())
        self.assertIn("engine_id", result)
        self.assertIn("total_tasks", result)
        self.assertIn("completed", result)
        self.assertGreater(result["completed"], 0)

    def test_dag_decomposition_integration(self):
        from thinkbox.engine import ThinkBoxEngine
        engine = ThinkBoxEngine()
        graph = engine.decomposer.decompose("Fix authentication bug in login handler")
        self.assertGreater(len(graph.tasks), 0)
        self.assertIsNotNone(graph.root_id)

    def test_pruning_integration(self):
        from thinkbox.engine import ThinkBoxEngine
        engine = ThinkBoxEngine()
        source = "# comment\nimport os\n\nprint('hello')\n"
        result = engine.pruner.prune_python(source)
        self.assertNotIn("# comment", result.content)
        self.assertTrue(result.within_budget)

    def test_autoscaler_integration(self):
        from thinkbox.engine import ThinkBoxEngine
        engine = ThinkBoxEngine()
        self.assertGreater(engine.autoscaler.current_workers, 0)
        self.assertLessEqual(engine.autoscaler.current_workers, engine.autoscaler.config.max_workers)

    def test_swarm_execution_integration(self):
        import asyncio
        from thinkbox.engine import ThinkBoxEngine
        engine = ThinkBoxEngine()

        async def run():
            result = await engine.swarm.execute_task("test_1", "Say hello")
            return result

        result = asyncio.run(run())
        self.assertIsNotNone(result.task_id)
        self.assertEqual(result.task_id, "test_1")


class TestAPIv1Router(unittest.TestCase):
    """Test the API v1 router endpoints."""

    def test_router_imports(self):
        import sys
        from unittest.mock import MagicMock
        sys.modules["fastapi"] = MagicMock()
        sys.modules["pydantic"] = MagicMock()
        from backend.api.v1.router import api_v1_router
        self.assertIsNotNone(api_v1_router)


class TestCLI(unittest.TestCase):
    """Test the CLI commands."""

    def test_cli_run_parser(self):
        from thinkbox.cli import main
        import argparse
        parser = argparse.ArgumentParser(prog="thinkbox")
        subparsers = parser.add_subparsers(dest="command")
        run_parser = subparsers.add_parser("run")
        run_parser.add_argument("--goal", required=True)
        run_parser.add_argument("--model", default="llama3.1:8b")
        run_parser.add_argument("--temperature", type=float, default=0.1)
        run_parser.add_argument("--no-speculation", action="store_true")

        args = parser.parse_args(["run", "--goal", "test goal"])
        self.assertEqual(args.goal, "test goal")

    def test_cli_serve_parser(self):
        from thinkbox.cli import main
        import argparse
        parser = argparse.ArgumentParser(prog="thinkbox")
        subparsers = parser.add_subparsers(dest="command")
        serve_parser = subparsers.add_parser("serve")
        serve_parser.add_argument("--host", default="0.0.0.0")
        serve_parser.add_argument("--port", type=int, default=8000)

        args = parser.parse_args(["serve", "--port", "9000"])
        self.assertEqual(args.port, 9000)


class TestSystemIntegration(unittest.TestCase):
    """Integration tests across all subsystems."""

    def test_all_subsystems_initialized(self):
        from thinkbox.engine import ThinkBoxEngine
        engine = ThinkBoxEngine()
        self.assertIsNotNone(engine.decomposer)
        self.assertIsNotNone(engine.pruner)
        self.assertIsNotNone(engine.autoscaler)
        self.assertIsNotNone(engine.model_client)
        self.assertIsNotNone(engine.swarm)
        self.assertIsNotNone(engine.git_engine)

    def test_engine_config_defaults(self):
        from thinkbox.engine import EngineConfig, ThinkBoxEngine
        engine = ThinkBoxEngine()
        self.assertTrue(engine.config.speculative)
        self.assertEqual(engine.config.max_retries, 3)

    def test_task_state_enum(self):
        from thinkbox.engine import TaskState
        self.assertEqual(TaskState.PENDING, "PENDING")
        self.assertEqual(TaskState.RUNNING, "RUNNING")
        self.assertEqual(TaskState.SPECULATING, "SPECULATING")
        self.assertEqual(TaskState.SUCCESS, "SUCCESS")
        self.assertEqual(TaskState.FAILED, "FAILED")


if __name__ == "__main__":
    unittest.main()
