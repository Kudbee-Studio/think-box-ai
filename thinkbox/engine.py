"""Unified ThinkBox Engine — wires all subsystems into a single pipeline."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncGenerator

from thinkbox.decomposer import TaskDecomposer, TaskGraph, TaskNode
from thinkbox.pruner import ContextPruner
from thinkbox.autoscaler import DynamicAutoscaler, ScalerConfig
from thinkbox.model_client import AsyncModelClient, ModelConfig
from thinkbox.swarm import AsyncWorkerPool, ExecutionResult, SpeculativeResult
from thinkbox.git_engine import GitEngine, GitConfig


class TaskState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SPECULATING = "SPECULATING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


@dataclass
class TaskEvent:
    task_id: str
    state: TaskState
    timestamp: str
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EngineConfig:
    model_config: ModelConfig = field(default_factory=ModelConfig)
    scaler_config: ScalerConfig = field(default_factory=ScalerConfig)
    git_config: GitConfig = field(default_factory=GitConfig)
    repo_path: str = "."
    speculative: bool = True
    max_retries: int = 3


class ThinkBoxEngine:
    def __init__(self, config: EngineConfig | None = None):
        self.config = config or EngineConfig()
        self.engine_id = f"engine_{uuid.uuid4().hex[:8]}"
        self.decomposer = TaskDecomposer()
        self.pruner = ContextPruner()
        self.autoscaler = DynamicAutoscaler(self.config.scaler_config)
        self.model_client = AsyncModelClient(self.config.model_config)
        self.swarm = AsyncWorkerPool(self.model_client, self.config.scaler_config.default_workers)
        self.git_engine = GitEngine(self.config.repo_path, self.config.git_config)
        self._events: list[TaskEvent] = []
        self._event_queue: asyncio.Queue[TaskEvent] = asyncio.Queue()
        self._running = False

    @property
    def events(self) -> list[TaskEvent]:
        return self._events.copy()

    def emit(self, task_id: str, state: TaskState, message: str = "", **kwargs: Any) -> None:
        event = TaskEvent(
            task_id=task_id,
            state=state,
            timestamp=datetime.now(timezone.utc).isoformat(),
            message=message,
            metadata=kwargs,
        )
        self._events.append(event)
        try:
            self._event_queue.put_nowait(event)
        except Exception:
            pass

    async def event_stream(self) -> AsyncGenerator[TaskEvent, None]:
        while self._running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                yield event
            except asyncio.TimeoutError:
                continue

    async def execute_goal(self, goal: str) -> dict[str, Any]:
        self._running = True
        start_time = time.monotonic()

        self.emit("root", TaskState.RUNNING, f"Starting goal: {goal[:100]}")

        graph = self.decomposer.decompose(goal)
        self.emit("root", TaskState.RUNNING, f"Decomposed into {len(graph.tasks)} tasks")

        results: dict[str, Any] = {}
        layers = graph.get_execution_order()

        for layer in layers:
            layer_tasks = [graph.tasks[tid] for tid in layer]
            self.emit("root", TaskState.RUNNING, f"Executing layer with {len(layer_tasks)} tasks")

            async def _execute_task(node: TaskNode) -> tuple[str, Any]:
                self.emit(node.id, TaskState.RUNNING, f"Task: {node.description[:80]}")

                pruned = self.pruner.prune_to_budget(node.description)

                await self.autoscaler.wait_if_paused()

                if self.config.speculative:
                    result = await self.swarm.execute_with_speculation(node.id, pruned)
                    if result.winner:
                        self.emit(node.id, TaskState.SUCCESS, f"Succeeded after {len(result.attempts)} attempts")
                        return node.id, result.winner
                    else:
                        self.emit(node.id, TaskState.FAILED, "All speculative attempts failed")
                        return node.id, result.attempts[-1] if result.attempts else None
                else:
                    result = await self.swarm.execute_task(node.id, pruned)
                    if result.success:
                        self.emit(node.id, TaskState.SUCCESS, "Task completed successfully")
                    else:
                        self.emit(node.id, TaskState.FAILED, f"Task failed: {result.output[:100]}")
                    return node.id, result

            layer_results = await asyncio.gather(
                *[_execute_task(node) for node in layer_tasks],
                return_exceptions=True,
            )

            for item in layer_results:
                if isinstance(item, tuple):
                    task_id, result = item
                    results[task_id] = result

        elapsed = (time.monotonic() - start_time) * 1000

        successful = sum(
            1 for r in results.values()
            if isinstance(r, ExecutionResult) and r.success
        )

        summary = {
            "engine_id": self.engine_id,
            "total_tasks": len(graph.tasks),
            "completed": len(results),
            "successful": successful,
            "failed": len(results) - successful,
            "total_time_ms": round(elapsed, 2),
            "events": len(self._events),
        }

        self.emit("root", TaskState.SUCCESS, "Goal execution complete", **summary)
        self._running = False
        return summary

    def get_stats(self) -> dict[str, Any]:
        return {
            "engine_id": self.engine_id,
            "events_processed": len(self._events),
            "swarm_stats": self.swarm.get_stats(),
            "autoscaler": {
                "current_workers": self.autoscaler.current_workers,
                "target_workers": self.autoscaler.target_workers,
                "metrics": {
                    "cpu_percent": self.autoscaler.metrics.cpu_percent,
                    "memory_percent": self.autoscaler.metrics.memory_percent,
                    "gpu_vram_used_percent": self.autoscaler.metrics.gpu_vram_used_percent,
                },
            },
        }
