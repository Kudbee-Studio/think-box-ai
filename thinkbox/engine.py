"""Unified ThinkBox Engine — wires all subsystems into a single pipeline."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncGenerator, Callable

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
        self._post_run_callback: Callable[[dict[str, Any]], None] | None = None
        self._verified_task_runner: Callable[..., Any] | None = None
        self._experiment_manager: Any = None

    def set_verified_task_runner(self, runner: Callable[..., Any] | None) -> None:
        """Inject the governed verified-execution runner (dependency injection).

        runner(task_id, prompt, verification, context) is awaited for every
        task node whose metadata carries a "verification" spec. The engine
        never imports governance or retry code; GovernedEngine supplies the
        runner delegating to its canonical execute_verified_task primitive.
        With no runner injected (default), behavior is identical to legacy.
        """
        self._verified_task_runner = runner

    def set_experiment_manager(self, manager: Any | None) -> None:
        """Inject an ExperimentManager for Memory -> Planning binding (DI).

        When set, execute_goal() retrieves the prior experiment recommendation
        via ExperimentManager.get_last_next_action() and passes it to
        TaskDecomposer.decompose() so the task graph is parameterized by
        prior experiment outcomes. With no manager injected, behavior is
        identical to legacy (no prior recommendation, single root task).
        """
        self._experiment_manager = manager

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

    async def execute_goal(self, goal: str, graph: TaskGraph | None = None) -> dict[str, Any]:
        self._running = True
        start_time = time.monotonic()
        goal_run_id = f"goal_{uuid.uuid4().hex[:8]}"

        self.emit("root", TaskState.RUNNING, f"Starting goal: {goal[:100]}", goal_run_id=goal_run_id)

        if graph is None:
            recommendation = None
            if self._experiment_manager is not None:
                recommendation = self._experiment_manager.get_last_next_action()
            graph = self.decomposer.decompose(goal, prior_recommendation=recommendation)
        self.emit("root", TaskState.RUNNING, f"Decomposed into {len(graph.tasks)} tasks", goal_run_id=goal_run_id)

        results: dict[str, Any] = {}
        layers = graph.get_execution_order()

        for layer in layers:
            layer_tasks = [graph.tasks[tid] for tid in layer]
            self.emit("root", TaskState.RUNNING, f"Executing layer with {len(layer_tasks)} tasks", goal_run_id=goal_run_id)

            async def _execute_task(node: TaskNode) -> tuple[str, Any]:
                self.emit(node.id, TaskState.RUNNING, f"Task: {node.description[:80]}", goal_run_id=goal_run_id)

                pruned = self.pruner.prune_to_budget(node.description)

                await self.autoscaler.wait_if_paused()

                verification = node.metadata.get("verification")
                if verification is not None and self._verified_task_runner is not None:
                    context = {
                        "goal_run_id": goal_run_id,
                        "goal": goal,
                        "dependencies": list(node.dependencies),
                        "experiment_id": node.metadata.get("experiment_id", ""),
                        "session_id": node.metadata.get("session_id", ""),
                    }
                    verified = await self._verified_task_runner(node.id, pruned, verification, context)
                    status = verified.get("execution_status", "")
                    ok = bool(verified.get("valid"))
                    self.emit(
                        node.id,
                        TaskState.SUCCESS if ok else TaskState.FAILED,
                        status,
                        goal_run_id=goal_run_id,
                        execution_status=status,
                        attempts=verified.get("attempts"),
                        retries_used=verified.get("retries_used"),
                        taxonomy=verified.get("taxonomy", ""),
                        final_taxonomy=verified.get("final_taxonomy", ""),
                        converted=verified.get("converted"),
                        latency_s=verified.get("latency_s"),
                        experiment_id=context["experiment_id"],
                        session_id=context["session_id"],
                    )
                    return node.id, verified

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

        def _is_verified(r: Any) -> bool:
            return isinstance(r, dict) and "execution_status" in r

        successful = sum(
            1 for r in results.values()
            if (isinstance(r, ExecutionResult) and r.success)
            or (_is_verified(r) and r.get("valid"))
        )

        summary = {
            "engine_id": self.engine_id,
            "goal_run_id": goal_run_id,
            "total_tasks": len(graph.tasks),
            "completed": len(results),
            "successful": successful,
            "failed": len(results) - successful,
            "total_time_ms": round(elapsed, 2),
            "events": len(self._events),
        }

        verified_results = {tid: r for tid, r in results.items() if _is_verified(r)}

        # Per-layer telemetry for deeper DAG analysis (fan-out/fan-in)
        layers_telemetry: list[dict[str, Any]] = []
        if verified_results:
            for layer_idx, layer in enumerate(layers):
                layer_task_ids = [tid for tid in layer if tid in verified_results]
                if not layer_task_ids:
                    layer_task_ids = [tid for tid in layer if tid in results]
                layer_counts = {"FIRST_TRY_SUCCESS": 0, "RECOVERED_SUCCESS": 0,
                                "FAILED_AFTER_RETRY": 0, "BUDGET_EXHAUSTED": 0,
                                "UNVERIFIED": 0, "retries": 0}
                for tid in layer_task_ids:
                    r = verified_results.get(tid) or results.get(tid)
                    if isinstance(r, dict) and "execution_status" in r:
                        status = r.get("execution_status", "")
                        if status in layer_counts:
                            layer_counts[status] += 1
                        layer_counts["retries"] += int(r.get("retries_used") or 0)
                layer_total = len(layer_task_ids)
                layer_ok = layer_counts["FIRST_TRY_SUCCESS"] + layer_counts["RECOVERED_SUCCESS"]
                layers_telemetry.append({
                    "layer_index": layer_idx,
                    "tasks": layer_total,
                    "first_try_successes": layer_counts["FIRST_TRY_SUCCESS"],
                    "recovered_successes": layer_counts["RECOVERED_SUCCESS"],
                    "failures": layer_counts["FAILED_AFTER_RETRY"],
                    "budget_exhausted": layer_counts["BUDGET_EXHAUSTED"],
                    "retries": layer_counts["retries"],
                    "verification_rate": round(layer_ok / layer_total, 4) if layer_total else 0.0,
                    "task_ids": layer_task_ids,
                    "fan_in_dependencies": [
                        node.dependencies for node in [graph.tasks[tid] for tid in layer_task_ids if tid in graph.tasks]
                    ],
                })
            summary["layers_telemetry"] = layers_telemetry

        if verified_results:
            counts = {s: 0 for s in (
                "FIRST_TRY_SUCCESS", "RECOVERED_SUCCESS", "FAILED_AFTER_RETRY",
                "BUDGET_EXHAUSTED", "UNVERIFIED",
            )}
            per_task: dict[str, Any] = {}
            retries = 0
            for tid, r in verified_results.items():
                status = r.get("execution_status", "")
                if status in counts:
                    counts[status] += 1
                retries += int(r.get("retries_used") or 0)
                per_task[tid] = {
                    "execution_status": status,
                    "valid": bool(r.get("valid")),
                    "taxonomy": r.get("taxonomy", ""),
                    "final_taxonomy": r.get("final_taxonomy", ""),
                    "attempts": r.get("attempts"),
                    "retries_used": r.get("retries_used"),
                    "converted": r.get("converted"),
                    "latency_s": r.get("latency_s"),
                    "experiment_id": (graph.tasks[tid].metadata.get("experiment_id", "")
                                      if tid in graph.tasks else ""),
                }
            n = len(verified_results)
            verified_ok = counts["FIRST_TRY_SUCCESS"] + counts["RECOVERED_SUCCESS"]
            summary["verified"] = {
                "tasks": n,
                "first_try_successes": counts["FIRST_TRY_SUCCESS"],
                "recovered_successes": counts["RECOVERED_SUCCESS"],
                "failures": counts["FAILED_AFTER_RETRY"],
                "budget_exhausted": counts["BUDGET_EXHAUSTED"],
                "unverified": counts["UNVERIFIED"],
                "retries": retries,
                "verification_rate": round(verified_ok / n, 4) if n else 0.0,
                "per_task": per_task,
            }

        self.emit("root", TaskState.SUCCESS, "Goal execution complete", **summary)
        if self._post_run_callback is not None:
            try:
                self._post_run_callback(summary)
            except Exception:
                pass
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

    def on_run_complete(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register a callback invoked after each successful goal execution.

        Used to wire SelfImprovementLoop and other post-run evaluations.
        The callback receives the run summary dict and must not raise.
        """
        self._post_run_callback = callback

    def wire_improvement_runner(
        self,
        runner: Any,
        baseline_components: dict[str, float] | None = None,
    ) -> None:
        """Wire SelfImprovementLoop into execute_goal().

        After each successful goal execution, evaluates the run summary,
        asks the runner to propose and retest an improvement for the
        weakest TSSI component, and records the verdict.
        """
        components = baseline_components or {}

        def _on_complete(summary: dict[str, Any]) -> None:
            baseline_index = runner.evaluate(summary)
            runner.run_cycle("", baseline_index, components)

        self.on_run_complete(_on_complete)
