"""Integration of autonomous workflows with enterprise swarm pool.

Wraps autonomous workflow loops as swarm-executable tasks, enabling
concurrent execution of multiple autonomous loops with production-grade
resilience, metrics, and circuit breaker protection.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Optional

from .engine import ThinkBoxEngine, EngineConfig
from .swarm_enterprise import EnterpriseSwarmPool, ExecutionMetrics, TaskConfig, TaskPriority

logger = logging.getLogger(__name__)


@dataclass
class AutonomousWorkflowSpec:
    """Specification for an autonomous workflow to execute in swarm."""

    workflow_id: str
    goal: str
    initial_observations: list[str]
    max_iterations: int = 10
    priority: TaskPriority = TaskPriority.NORMAL
    timeout_ms: int = 300000  # 5 minutes for workflow execution


@dataclass
class WorkflowExecutionResult:
    """Result of a single autonomous workflow execution."""

    workflow_id: str
    success: bool
    iterations: int
    final_decision: Optional[str] = None
    metrics: Optional[ExecutionMetrics] = None
    error: Optional[str] = None


class AutonomousSwarmPool:
    """Executor for autonomous workflows in enterprise swarm pool."""

    def __init__(
        self,
        engine: Optional[ThinkBoxEngine] = None,
        swarm: Optional[EnterpriseSwarmPool] = None,
        max_concurrent_workflows: int = 8,
    ):
        """Initialize autonomous swarm pool.

        Args:
            engine: ThinkBoxEngine for workflow logic (default: new instance)
            swarm: EnterpriseSwarmPool for task execution (default: new instance)
            max_concurrent_workflows: Max concurrent autonomous workflows
        """
        self.engine = engine or ThinkBoxEngine(EngineConfig())
        self.swarm = swarm or EnterpriseSwarmPool(max_workers=max_concurrent_workflows)
        self.max_concurrent = max_concurrent_workflows
        self._results: dict[str, WorkflowExecutionResult] = {}

    async def execute_workflow(
        self,
        spec: AutonomousWorkflowSpec,
    ) -> WorkflowExecutionResult:
        """Execute a single autonomous workflow in the swarm pool.

        Args:
            spec: Workflow specification

        Returns:
            WorkflowExecutionResult with execution details
        """
        config = TaskConfig(
            priority=spec.priority,
            timeout_ms=spec.timeout_ms,
        )

        # Encode workflow as prompt for swarm task
        prompt = self._encode_workflow_prompt(spec)

        # Execute in swarm pool
        try:
            metric = await self.swarm.execute_task(
                task_id=spec.workflow_id,
                prompt=prompt,
                config=config,
            )

            # Parse result
            result = WorkflowExecutionResult(
                workflow_id=spec.workflow_id,
                success=metric.success,
                iterations=metric.attempt,
                final_decision=metric.output if metric.success else None,
                metrics=metric,
            )

            if not metric.success:
                result.error = metric.error_type

            self._results[spec.workflow_id] = result
            return result

        except Exception as e:
            result = WorkflowExecutionResult(
                workflow_id=spec.workflow_id,
                success=False,
                iterations=0,
                error=str(e),
            )
            self._results[spec.workflow_id] = result
            return result

    async def execute_workflows_concurrently(
        self,
        specs: list[AutonomousWorkflowSpec],
    ) -> list[WorkflowExecutionResult]:
        """Execute multiple autonomous workflows concurrently.

        Args:
            specs: List of workflow specifications

        Returns:
            List of execution results
        """
        # Execute all workflows concurrently in swarm pool
        results = await asyncio.gather(
            *[self.execute_workflow(spec) for spec in specs],
            return_exceptions=False,
        )

        return results

    def _encode_workflow_prompt(self, spec: AutonomousWorkflowSpec) -> str:
        """Encode autonomous workflow as model prompt."""
        observations = "\n".join(f"- {obs}" for obs in spec.initial_observations)

        return f"""
Execute autonomous workflow: {spec.workflow_id}

Goal: {spec.goal}

Current observations:
{observations}

Steps to follow:
1. SENSE: Review current observations
2. DECIDE: Based on goal and observations, determine next action
3. ACT: Record the decision
4. LEARN: Extract lesson for future iterations

Provide your decision in JSON format:
{{
    "action": "...",
    "reasoning": "...",
    "confidence": 0.0-1.0,
    "next_observation_prompt": "What should we observe next?"
}}
"""

    def get_workflow_result(self, workflow_id: str) -> Optional[WorkflowExecutionResult]:
        """Get result for a completed workflow."""
        return self._results.get(workflow_id)

    def get_all_results(self) -> dict[str, WorkflowExecutionResult]:
        """Get all workflow results."""
        return self._results.copy()

    def get_pool_metrics(self) -> dict[str, Any]:
        """Get aggregate swarm pool metrics."""
        pool_metrics = self.swarm.metrics
        health = self.swarm.get_health_status()

        results = self._results.values()
        successful = sum(1 for r in results if r.success)
        total = len(results)

        return {
            "total_workflows": total,
            "successful_workflows": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "pool_metrics": {
                "total_tasks": pool_metrics.total_tasks,
                "success_rate": f"{pool_metrics.success_rate:.1%}",
                "avg_latency_ms": f"{pool_metrics.avg_latency_ms:.0f}",
                "p95_latency_ms": f"{pool_metrics.p95_latency_ms:.0f}",
            },
            "health": health,
        }

    async def shutdown(self) -> None:
        """Gracefully shutdown the autonomous swarm pool."""
        logger.info("Shutting down autonomous swarm pool")
        await self.swarm.shutdown()
