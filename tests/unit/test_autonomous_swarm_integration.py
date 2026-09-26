"""Tests for autonomous swarm integration.

Tests the binding between autonomous workflows and enterprise swarm pool.
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from thinkbox.autonomous_swarm_integration import (
    AutonomousSwarmPool,
    AutonomousWorkflowSpec,
    WorkflowExecutionResult,
)
from thinkbox.swarm_enterprise import (
    ExecutionMetrics,
    EnterpriseSwarmPool,
    TaskPriority,
)


class TestAutonomousSwarmIntegration(unittest.IsolatedAsyncioTestCase):
    """Test suite for AutonomousSwarmPool."""

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        self.pool = AutonomousSwarmPool(max_concurrent_workflows=4)

    async def asyncTearDown(self) -> None:
        """Clean up after tests."""
        await self.pool.shutdown()

    async def test_single_workflow_execution(self) -> None:
        """Test executing a single autonomous workflow."""
        spec = AutonomousWorkflowSpec(
            workflow_id="wf_001",
            goal="Optimize system latency",
            initial_observations=["Current latency: 500ms", "System load: 60%"],
            max_iterations=5,
            priority=TaskPriority.HIGH,
        )

        # Create actual ExecutionMetrics to verify against
        metric = ExecutionMetrics(
            task_id="wf_001",
            success=True,
            latency_ms=150.5,
            tokens_used=850,
            attempt=0,
        )

        # Mock the execute_task method with async function
        async def mock_execute_task(task_id, prompt, config):
            return metric

        self.pool.swarm.execute_task = mock_execute_task

        result = await self.pool.execute_workflow(spec)

        self.assertEqual(result.workflow_id, "wf_001")
        self.assertTrue(result.success)
        self.assertEqual(result.iterations, 0)
        self.assertIsNotNone(result.metrics)
        self.assertIsNone(result.error)

    async def test_workflow_execution_failure(self) -> None:
        """Test handling workflow execution failure."""
        spec = AutonomousWorkflowSpec(
            workflow_id="wf_002",
            goal="Analyze performance metrics",
            initial_observations=["Metric A: 100", "Metric B: 200"],
        )

        # Mock failure
        metric = ExecutionMetrics(
            task_id="wf_002",
            success=False,
            latency_ms=200.0,
            tokens_used=0,
            attempt=3,
            error_type="TimeoutError",
            retry_count=3,
        )

        async def mock_execute_task(task_id, prompt, config):
            return metric

        self.pool.swarm.execute_task = mock_execute_task

        result = await self.pool.execute_workflow(spec)

        self.assertEqual(result.workflow_id, "wf_002")
        self.assertFalse(result.success)
        self.assertEqual(result.error, "TimeoutError")
        self.assertEqual(result.iterations, 3)

    async def test_concurrent_workflow_execution(self) -> None:
        """Test executing multiple workflows concurrently."""
        specs = [
            AutonomousWorkflowSpec(
                workflow_id=f"wf_{i:03d}",
                goal=f"Task {i}",
                initial_observations=[f"Observation {i}"],
            )
            for i in range(4)
        ]

        # Mock all executions
        async def mock_execute(task_id: str, prompt: str, config):
            await asyncio.sleep(0.01)  # Simulate latency
            return ExecutionMetrics(
                task_id=task_id,
                success=True,
                latency_ms=50.0,
                tokens_used=500,
                attempt=0,
            )

        self.pool.swarm.execute_task = mock_execute

        results = await self.pool.execute_workflows_concurrently(specs)

        self.assertEqual(len(results), 4)
        self.assertTrue(all(r.success for r in results))
        self.assertEqual(len(self.pool._results), 4)

    async def test_workflow_execution_exception_handling(self) -> None:
        """Test handling of exceptions during workflow execution."""
        spec = AutonomousWorkflowSpec(
            workflow_id="wf_exception",
            goal="Test exception handling",
            initial_observations=["Test"],
        )

        # Mock exception
        async def mock_execute_task_error(task_id, prompt, config):
            raise RuntimeError("Mock execution error")

        self.pool.swarm.execute_task = mock_execute_task_error

        result = await self.pool.execute_workflow(spec)

        self.assertEqual(result.workflow_id, "wf_exception")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertIn("Mock execution error", result.error)

    async def test_get_workflow_result(self) -> None:
        """Test retrieving a workflow result."""
        spec = AutonomousWorkflowSpec(
            workflow_id="wf_retrieve",
            goal="Test retrieval",
            initial_observations=["Test"],
        )

        metric = ExecutionMetrics(
            task_id="wf_retrieve",
            success=True,
            latency_ms=100.0,
            tokens_used=500,
            attempt=0,
        )

        async def mock_execute_task(task_id, prompt, config):
            return metric

        self.pool.swarm.execute_task = mock_execute_task

        result = await self.pool.execute_workflow(spec)
        retrieved = self.pool.get_workflow_result("wf_retrieve")

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.workflow_id, "wf_retrieve")
        self.assertTrue(retrieved.success)

    async def test_get_all_results(self) -> None:
        """Test retrieving all workflow results."""
        specs = [
            AutonomousWorkflowSpec(
                workflow_id=f"wf_all_{i}",
                goal=f"Task {i}",
                initial_observations=["Test"],
            )
            for i in range(3)
        ]

        async def mock_execute_task(task_id, prompt, config):
            return ExecutionMetrics(
                task_id=task_id,
                success=True,
                latency_ms=100.0,
                tokens_used=500,
                attempt=0,
            )

        self.pool.swarm.execute_task = mock_execute_task

        await self.pool.execute_workflows_concurrently(specs)
        all_results = self.pool.get_all_results()

        self.assertEqual(len(all_results), 3)
        self.assertTrue(all(r.success for r in all_results.values()))

    async def test_pool_metrics(self) -> None:
        """Test getting aggregate pool metrics."""
        specs = [
            AutonomousWorkflowSpec(
                workflow_id=f"wf_metrics_{i}",
                goal=f"Task {i}",
                initial_observations=["Test"],
            )
            for i in range(5)
        ]

        # Mock mixed results (3 success, 2 failure)
        async def mock_execute(task_id: str, prompt: str, config):
            success = int(task_id.split("_")[-1]) < 3
            return ExecutionMetrics(
                task_id=task_id,
                success=success,
                latency_ms=100.0 + (50 if success else 200),
                tokens_used=500 if success else 0,
                attempt=0,
                error_type=None if success else "MockError",
            )

        self.pool.swarm.execute_task = mock_execute

        await self.pool.execute_workflows_concurrently(specs)
        metrics = self.pool.get_pool_metrics()

        self.assertEqual(metrics["total_workflows"], 5)
        self.assertEqual(metrics["successful_workflows"], 3)
        self.assertAlmostEqual(metrics["success_rate"], 0.6, places=2)
        self.assertIn("pool_metrics", metrics)
        self.assertIn("health", metrics)

    def test_workflow_prompt_encoding(self) -> None:
        """Test workflow prompt encoding."""
        spec = AutonomousWorkflowSpec(
            workflow_id="wf_prompt",
            goal="Test goal",
            initial_observations=["Obs1", "Obs2", "Obs3"],
        )

        prompt = self.pool._encode_workflow_prompt(spec)

        self.assertIn(spec.workflow_id, prompt)
        self.assertIn(spec.goal, prompt)
        self.assertIn("Obs1", prompt)
        self.assertIn("Obs2", prompt)
        self.assertIn("Obs3", prompt)
        self.assertIn("SENSE:", prompt)
        self.assertIn("DECIDE:", prompt)
        self.assertIn("ACT:", prompt)
        self.assertIn("LEARN:", prompt)

    async def test_workflow_priority_configuration(self) -> None:
        """Test that workflow priority is passed to swarm pool."""
        spec = AutonomousWorkflowSpec(
            workflow_id="wf_priority",
            goal="High priority task",
            initial_observations=["Test"],
            priority=TaskPriority.CRITICAL,
        )

        self.captured_config = None

        async def capture_config(task_id: str, prompt: str, config):
            self.captured_config = config
            return ExecutionMetrics(
                task_id=task_id,
                success=True,
                latency_ms=100.0,
                tokens_used=500,
                attempt=0,
            )

        self.pool.swarm.execute_task = capture_config

        await self.pool.execute_workflow(spec)

        self.assertIsNotNone(self.captured_config)
        self.assertEqual(self.captured_config.priority, TaskPriority.CRITICAL)

    async def test_workflow_timeout_configuration(self) -> None:
        """Test that workflow timeout is passed to swarm pool."""
        spec = AutonomousWorkflowSpec(
            workflow_id="wf_timeout",
            goal="Test timeout",
            initial_observations=["Test"],
            timeout_ms=600000,  # 10 minutes
        )

        self.captured_timeout_config = None

        async def capture_config(task_id: str, prompt: str, config):
            self.captured_timeout_config = config
            return ExecutionMetrics(
                task_id=task_id,
                success=True,
                latency_ms=100.0,
                tokens_used=500,
                attempt=0,
            )

        self.pool.swarm.execute_task = capture_config

        await self.pool.execute_workflow(spec)

        self.assertIsNotNone(self.captured_timeout_config)
        self.assertEqual(self.captured_timeout_config.timeout_ms, 600000)


class TestAutonomousWorkflowSpec(unittest.TestCase):
    """Test AutonomousWorkflowSpec dataclass."""

    def test_spec_creation(self) -> None:
        """Test creating a workflow spec."""
        spec = AutonomousWorkflowSpec(
            workflow_id="wf_test",
            goal="Test goal",
            initial_observations=["Obs1", "Obs2"],
        )

        self.assertEqual(spec.workflow_id, "wf_test")
        self.assertEqual(spec.goal, "Test goal")
        self.assertEqual(len(spec.initial_observations), 2)
        self.assertEqual(spec.max_iterations, 10)
        self.assertEqual(spec.priority, TaskPriority.NORMAL)
        self.assertEqual(spec.timeout_ms, 300000)

    def test_spec_with_custom_values(self) -> None:
        """Test creating a spec with custom values."""
        spec = AutonomousWorkflowSpec(
            workflow_id="wf_custom",
            goal="Custom goal",
            initial_observations=["Obs"],
            max_iterations=20,
            priority=TaskPriority.HIGH,
            timeout_ms=600000,
        )

        self.assertEqual(spec.max_iterations, 20)
        self.assertEqual(spec.priority, TaskPriority.HIGH)
        self.assertEqual(spec.timeout_ms, 600000)


class TestWorkflowExecutionResult(unittest.TestCase):
    """Test WorkflowExecutionResult dataclass."""

    def test_result_creation_success(self) -> None:
        """Test creating a successful result."""
        result = WorkflowExecutionResult(
            workflow_id="wf_test",
            success=True,
            iterations=5,
            final_decision="Action taken",
        )

        self.assertEqual(result.workflow_id, "wf_test")
        self.assertTrue(result.success)
        self.assertEqual(result.iterations, 5)
        self.assertEqual(result.final_decision, "Action taken")
        self.assertIsNone(result.error)

    def test_result_creation_failure(self) -> None:
        """Test creating a failed result."""
        result = WorkflowExecutionResult(
            workflow_id="wf_fail",
            success=False,
            iterations=0,
            error="Execution failed",
        )

        self.assertEqual(result.workflow_id, "wf_fail")
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Execution failed")
        self.assertIsNone(result.final_decision)


if __name__ == "__main__":
    unittest.main()
