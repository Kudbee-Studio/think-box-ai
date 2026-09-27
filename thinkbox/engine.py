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
    telemetry_interval_s: float = 5.0


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
        self._experiment_analytics: Any = None
        self._opportunity_manager: Any = None
        self._loop_tracer: Any = None
        self._auto_tuner: Any = None
        self._generalizer: Any = None
        self._session_manager: Any = None
        self._loop_bootstrap: Any = None
        self._telemetry_interval: float = self.config.telemetry_interval_s
        self._last_telemetry_time: float = 0.0

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
        """Inject the ExperimentManager for Memory -> Planning binding (DI).

        When set, execute_goal() retrieves the prior experiment recommendation
        via ExperimentManager.get_last_next_action() and passes it to
        TaskDecomposer.decompose() so the task graph is parameterized by
        prior experiment outcomes. With no manager injected, behavior is
        identical to legacy (no prior recommendation, single root task).
        """
        self._experiment_manager = manager

    def wire_experiment_feedback(self, manager: Any | None, analytics: Any | None,
                                 opportunity_manager: Any | None = None) -> None:
        """Wire Execution -> Memory -> Learning -> Opportunity feedback loop (DI).

        When set, execute_goal() persists the run summary as experiment
        outcome data and generates a new recommendation via NextActionGenerator.
        The recommendation is registered as an Opportunity via OpportunityManager
        for the next planning cycle. This closes the
        Planning -> Execution -> Verification -> Feedback -> Memory -> Opportunity loop.

        With no manager/analytics injected, execute_goal() behaves identically
        to legacy (no feedback recording).
        """
        self._experiment_manager = manager
        self._experiment_analytics = analytics
        self._opportunity_manager = opportunity_manager

    def set_loop_tracer(self, tracer: Any | None) -> None:
        """Inject a LoopTracer for autonomous loop observability (DI).

        When set, execute_goal() traces each loop iteration:
        start_iteration at goal execution -> complete_iteration after
        feedback registers an opportunity. Proves the closed loop
        is functioning via measurable cycle times and recommendation traceability.
        With no tracer injected, behavior is identical to legacy.
        """
        self._loop_tracer = tracer

    def set_auto_tuner(self, tuner: Any | None) -> None:
        """Inject an EngineAutoTuner for self-tuning (DI).

        The auto-tuner reviews LoopTracer measurements and adjusts engine
        config (max_retries, worker counts) based on observed performance.
        With no tuner injected, behavior is identical to legacy.
        """
        self._auto_tuner = tuner

    def set_generalizer(self, generalizer: Any | None) -> "ThinkBoxEngine":
        """Inject a CrossExperimentGeneralizer for pattern generalization (DI).

        When set, execute_goal() periodically analyzes cross-experiment
        patterns from loop iterations. With no generalizer injected,
        behavior is identical to legacy.
        """
        self._generalizer = generalizer
        return self

    def set_session_manager(self, manager: Any | None) -> None:
        """Inject a LoopSessionManager for cross-cycle session management (DI).

        When set, the engine can close the current session and start a new one,
        enabling comparison of performance across loop cycles.
        With no manager injected, behavior is identical to legacy.
        """
        self._session_manager = manager

    def set_loop_bootstrap(self, bootstrap: Any | None) -> "ThinkBoxEngine":
        """Inject a LoopBootstrap for cold-start initialization (DI).

        When set, execute_goal() bootstraps the loop with seed data if
        no prior recommendation exists. This enables the autonomous loop
        to start from a clean system without manual priming.
        """
        self._loop_bootstrap = bootstrap
        return self

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

        iteration_id = None
        if self._loop_tracer is not None:
            iteration_id = self._loop_tracer.start_iteration(goal_run_id)

        if graph is None:
            recommendation = None
            opportunity_rec = None
            if self._opportunity_manager is not None:
                opp = self._opportunity_manager.get_current_opportunity()
                if opp is not None:
                    opportunity_rec = opp.recommendation
                    self.emit("root", TaskState.RUNNING,
                              "Consuming current opportunity", goal_run_id=goal_run_id,
                              opportunity_id=opp.opportunity_id,
                              opportunity_priority=opp.priority)
            if self._experiment_manager is not None:
                recommendation = self._experiment_manager.get_last_next_action()
            recommendation = opportunity_rec or recommendation

            if recommendation is None and self._loop_bootstrap is not None:
                boot_result = self._loop_bootstrap.bootstrap()
                if boot_result.bootstrapped:
                    recommendation = boot_result.recommendation
                    self.emit("root", TaskState.RUNNING,
                              "Loop bootstrapped from cold start",
                              goal_run_id=goal_run_id,
                              bootstrap_experiment_id=boot_result.experiment_id,
                              source=boot_result.source)

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

        task_reports: list[dict[str, Any]] = []
        for tid, r in results.items():
            node = graph.tasks.get(tid)
            report: dict[str, Any] = {"task_id": tid, "description": node.description if node else ""}
            if isinstance(r, ExecutionResult):
                report.update(success=r.success, output=r.output, error_type=r.error_type)
            elif _is_verified(r):
                report.update(success=bool(r.get("valid")), output=r.get("output", r.get("final_output", "")),
                              error_type=r.get("final_taxonomy", ""))
            else:
                report.update(success=False, output="", error_type=type(r).__name__)
            task_reports.append(report)
        summary["tasks"] = task_reports

        verified_results ={tid: r for tid, r in results.items() if _is_verified(r)}

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
        self._record_execution_feedback(summary, goal_run_id, iteration_id)
        self._auto_tune()
        self._running = False
        return summary

    def _record_execution_feedback(self, summary: dict[str, Any], goal_run_id: str,
                                   iteration_id: Optional[str] = None) -> None:
        """Persist execution summary as experiment outcome and generate next-action recommendation.

        This closes the Planning -> Execution -> Verification -> Feedback -> Memory loop:
        execution results feed into ExperimentManager -> NextActionGenerator produces
        a refined recommendation available for the next execute_goal() call.

        No-ops when no ExperimentManager/ExperimentAnalytics are injected.
        Fail-closed: errors are swallowed to avoid disrupting execution flow.
        """
        if self._experiment_manager is None or self._experiment_analytics is None:
            return
        try:
            from thinkbox.experiment_analytics import NextActionGenerator

            total = summary.get("total_tasks", 0)
            successful = summary.get("successful", 0)
            failed = summary.get("failed", 0)
            if total > 0:
                throughput = round(successful / total, 6)
            else:
                throughput = 0.0
            error_rate = round(failed / total, 6) if total > 0 else 0.0
            p50_latency = round(summary.get("total_time_ms", 0) / max(total, 1) / 1000, 6)

            metrics_run = {
                "throughput": throughput,
                "p50_latency": p50_latency,
                "p95_latency": p50_latency * 2,
                "p99_latency": p50_latency * 3,
                "error_rate": error_rate,
                "iteration_count": total,
            }
            exp = self._experiment_manager.create_experiment(
                intent=f"goal:{goal_run_id}",
                hypothesis="Verified execution produced measurable outcomes",
                parameters={"goal_run_id": goal_run_id, "total_tasks": total},
                agent_id="thinkbox_engine",
                execution_mode="verified",
            )
            self._experiment_analytics.persist_run(exp.experiment_id, metrics_run)
            self._experiment_manager.record_outcome(
                exp.experiment_id,
                {"status": "completed", "summary": summary},
                confidence=0.9 if successful > 0 else 0.0,
                four_state="TEST_VERIFIED",
            )
            generator = NextActionGenerator(self._experiment_manager, self._experiment_analytics)
            next_action = generator.generate(exp.experiment_id, {"status": "completed"}, confidence=0.9)
            recommendation = next_action.get("recommended_next_experiment", next_action)
            self._register_opportunity(exp.experiment_id, goal_run_id, recommendation, metrics_run)
            self._complete_loop_iteration(exp.experiment_id, recommendation, metrics_run, iteration_id)
            self.emit("root", TaskState.SUCCESS, "Feedback recorded",
                      feedback_experiment_id=exp.experiment_id, goal_run_id=goal_run_id)
        except Exception:
            pass

    def _register_opportunity(self, experiment_id: str, goal_run_id: str,
                              recommendation: dict[str, Any], metrics: dict[str, Any]) -> None:
        """Register a Feedback -> Opportunity binding.

        When an OpportunityManager is injected, the feedback-generated
        recommendation is persisted as an opportunity for the next planning
        cycle. No-ops when no OpportunityManager is set.
        Fail-closed: errors are swallowed to avoid disrupting execution flow.
        """
        if self._opportunity_manager is None:
            return
        try:
            priority = "high" if recommendation.get("type") == "regression_followup" else "medium"
            opportunity = self._opportunity_manager.register_opportunity(
                source_experiment_id=experiment_id,
                source_goal_run_id=goal_run_id,
                recommendation=recommendation,
                metrics=metrics,
                priority=priority,
            )
            self.emit("root", TaskState.SUCCESS, "Opportunity registered",
                      opportunity_id=opportunity.opportunity_id,
                      goal_run_id=goal_run_id,
                      recommendation_type=recommendation.get("type", "unknown"))
        except Exception:
            pass

    def _complete_loop_iteration(self, experiment_id: str, recommendation: dict[str, Any],
                                 metrics: dict[str, Any], iteration_id: Optional[str]) -> None:
        """Complete a loop iteration in the LoopTracer (Observability -> Learning binding).

        Records the full cycle: goal execution -> feedback -> opportunity registration.
        No-ops when no LoopTracer is set or when no in-flight iteration exists.
        Fail-closed: errors are swallowed.
        """
        if self._loop_tracer is None or iteration_id is None:
            return
        try:
            opp_id = ""
            if self._opportunity_manager is not None:
                opp = self._opportunity_manager.get_current_opportunity()
                if opp is not None:
                    opp_id = opp.opportunity_id
            self._loop_tracer.complete_iteration(
                iteration_id=iteration_id,
                experiment_id=experiment_id,
                opportunity_id=opp_id,
                recommendation_type=recommendation.get("type", "unknown"),
                priority="high" if recommendation.get("type") == "regression_followup" else "medium",
                metrics=metrics,
            )
            self.emit("root", TaskState.SUCCESS, "Loop iteration traced",
                      iteration_id=iteration_id, goal_run_id=metrics.get("goal_run_id", ""),
                      experiment_id=experiment_id)
        except Exception:
            pass

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

    def _auto_tune(self) -> None:
        """Review LoopTracer measurements and adjust engine config (Self-Tuning).

        When both LoopTracer and EngineAutoTuner are injected, executes
        tuning decisions after each goal. No-op without them.
        Fail-closed: errors are swallowed.
        """
        if self._auto_tuner is None or self._loop_tracer is None:
            return
        try:
            decisions = self._auto_tuner.review_and_tune(self)
            if decisions:
                self.emit("root", TaskState.SUCCESS, "Auto-tuning applied",
                          tuning_decisions=len(decisions))
        except Exception:
            pass

        if self._generalizer is not None and self._loop_tracer is not None:
            metrics = self._loop_tracer.get_metrics()
            if metrics.total_iterations >= 3:
                self._generalize_patterns()

        self._record_closed_session()

        self._update_loop_dashboard()
        self._telemetry_tick()

    def _record_closed_session(self) -> None:
        """Record a closed loop session into dashboard state.

        When the session manager has closed a session, mirrors the
        resulting LoopSession into DashboardState.loop_sessions for
        real-time UI consumption. Fail-closed: errors are swallowed.
        """
        if self._session_manager is None:
            return
        try:
            from thinkbox.dashboard_state import get_dashboard_state, LoopSessionEntry

            state = get_dashboard_state()
            current = self._session_manager.get_current_session()
            if current is not None and current.session_id not in state.loop_sessions:
                entry = LoopSessionEntry(
                    session_id=current.session_id,
                    loop_id=current.loop_id,
                    started_at=current.started_at,
                    closed_at=current.closed_at,
                    iterations_count=current.iterations_count,
                    avg_throughput=current.avg_throughput,
                    avg_p50_latency=current.avg_p50_latency,
                    avg_error_rate=current.avg_error_rate,
                    total_cycle_time_s=current.total_cycle_time_s,
                    patterns_identified=current.patterns_identified,
                    improved_over_baseline=False,
                    summary=current.summary,
                )
                state.record_autonomous_loop_session(entry)
        except Exception:
            pass

    def _telemetry_tick(self) -> None:
        """Capture detailed telemetry for the autonomous loop dashboard.

        Called after _update_loop_dashboard(). Builds an AutonomousLoopTelemetry
        from LoopTracer metrics and EngineAutoTuner decision count, records
        convergence status, populates learning curve points from iteration
        history, and tracks convergence history. Rate-limited by
        telemetry_interval_s to avoid excessive writes.

        No-op when no LoopTracer is injected. Fail-closed: errors are swallowed.
        """
        if self._loop_tracer is None or not self._loop_tracer.get_current_loop_id():
            return
        now = time.monotonic()
        if now - self._last_telemetry_time < self._telemetry_interval:
            return
        self._last_telemetry_time = now
        try:
            from thinkbox.dashboard_state import get_dashboard_state, AutonomousLoopTelemetry

            state = get_dashboard_state()
            loop_id = self._loop_tracer.get_current_loop_id()
            metrics = self._loop_tracer.get_metrics()
            convergence = self._assess_convergence(metrics)

            learning_curve = self._build_learning_curve_points(loop_id)

            existing_telemetry = state.get_loop_telemetry(loop_id)
            convergence_history = []
            if existing_telemetry is not None:
                convergence_history = list(existing_telemetry.convergence_history)
            convergence_history.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "iteration": metrics.total_iterations,
                "status": convergence,
                "avg_cycle_time_s": metrics.avg_cycle_time_s,
                "throughput": round(metrics.total_iterations / metrics.total_cycle_time_s, 6)
                    if metrics.total_cycle_time_s > 0 else 0.0,
            })
            convergence_history = convergence_history[-100:]

            telemetry = AutonomousLoopTelemetry(
                total_iterations=metrics.total_iterations,
                total_cycle_time_s=metrics.total_cycle_time_s,
                avg_cycle_time_s=metrics.avg_cycle_time_s,
                min_cycle_time_s=metrics.min_cycle_time_s,
                max_cycle_time_s=metrics.max_cycle_time_s,
                throughput=round(metrics.total_iterations / metrics.total_cycle_time_s, 6)
                    if metrics.total_cycle_time_s > 0 else 0.0,
                recommendation_types=metrics.recommendation_types,
                priority_distribution=metrics.priority_distribution,
                learning_curve_points=learning_curve,
                convergence_status=convergence,
                convergence_history=convergence_history,
                last_iteration_id=metrics.latest_iteration_id,
                first_iteration_id=metrics.first_iteration_id,
            )
            state.record_loop_telemetry(loop_id, telemetry)
        except Exception:
            pass

    def _build_learning_curve_points(self, loop_id: str) -> list[dict[str, Any]]:
        """Build learning curve points from LoopTracer iteration history.

        Each point captures throughput and cycle time per iteration to enable
        convergence visualization on the control-plane UI.
        """
        iterations = self._loop_tracer.list_iterations(loop_id=loop_id, limit=100)
        points: list[dict[str, Any]] = []
        for i, it in enumerate(reversed(iterations)):
            points.append({
                "iteration": i + 1,
                "iteration_id": it.iteration_id,
                "throughput": it.metrics.get("throughput", 0.0),
                "avg_cycle_time_s": it.cycle_time_s,
                "avg_p50_latency": it.metrics.get("p50_latency", 0.0),
                "error_rate": it.metrics.get("error_rate", 0.0),
                "recommendation_type": it.recommendation_type,
                "timestamp": it.completed_at,
            })
        return points

    def _assess_convergence(self, metrics: Any) -> str:
        """Assess loop convergence status from metrics (Learning -> Observability binding).

        Returns 'converged' if >=5 iterations with low cycle-time spread (< 0.3),
        'improving' if iterations exist but spread is higher, 'pending' otherwise.
        """
        try:
            if metrics.total_iterations >= 5 and metrics.avg_cycle_time_s > 0:
                spread = (metrics.max_cycle_time_s - metrics.min_cycle_time_s) / metrics.avg_cycle_time_s
                if spread < 0.3:
                    return "converged"
                return "improving"
            if metrics.total_iterations > 0:
                return "improving"
            return "pending"
        except Exception:
            return "pending"

    def _update_loop_dashboard(self) -> None:
        """Update the autonomous loop dashboard entry with current state."""
        try:
            from thinkbox.dashboard_state import get_dashboard_state, AutonomousLoopEntry

            state = get_dashboard_state()
            loop_id = ""
            if self._loop_tracer is not None:
                loop_id = self._loop_tracer.get_current_loop_id()
                if not loop_id:
                    return

            metrics = self._loop_tracer.get_metrics() if self._loop_tracer else None
            patterns_count = self._generalizer.get_pattern_count() if self._generalizer else 0
            tuning_count = self._auto_tuner.get_decision_count() if self._auto_tuner else 0
            bootstrapped = not self._loop_bootstrap.needs_bootstrap() if self._loop_bootstrap else False

            current_session_id = ""
            if self._session_manager is not None:
                current = self._session_manager.get_current_session()
                if current is not None:
                    current_session_id = current.session_id

            entry = AutonomousLoopEntry(
                loop_id=loop_id,
                status="running",
                current_session_id=current_session_id,
                iterations_count=metrics.total_iterations if metrics else 0,
                patterns_identified=patterns_count,
                tuning_decisions=tuning_count,
                bootstrapped=bootstrapped,
                components={
                    "bootstrap": self._loop_bootstrap is not None,
                    "experiment_manager": self._experiment_manager is not None,
                    "decomposer": True,
                    "execution": True,
                    "feedback": self._experiment_analytics is not None,
                    "opportunity": self._opportunity_manager is not None,
                    "loop_tracer": self._loop_tracer is not None,
                    "auto_tuner": self._auto_tuner is not None,
                    "generalizer": self._generalizer is not None,
                    "session_manager": self._session_manager is not None,
                },
            )
            state.upsert_autonomous_loop(entry)
        except Exception:
            pass

    def _generalize_patterns(self) -> None:
        """Run cross-experiment generalization analysis (Observability -> Learning).

        Identifies generalizable patterns across loop iterations and
        stores them as organizational knowledge. Only runs when >=3
        iterations exist and a generalizer is injected.
        Fail-closed: errors are swallowed.
        """
        try:
            result = self._generalizer.generalize()
            if result.patterns_identified:
                self.emit("root", TaskState.SUCCESS, "Patterns generalized",
                          patterns_identified=len(result.patterns_identified),
                          generalization_confidence=result.generalization_confidence)
        except Exception:
            pass
