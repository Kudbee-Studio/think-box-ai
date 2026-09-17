#!/usr/bin/env python3
"""LOCAL THINK BOX EXPERIMENT LOOP — $0, deterministic, no server.

Demonstrates the full Think Box lifecycle:
  INTENT → PLAN → THINK JOB → EXECUTION → ARTIFACT → VALIDATION → PROOF → OUTCOME → MEMORY → SELF-IMPROVEMENT → DASHBOARD → REPLAY

Runs entirely in-process with SQLite persistence and a synthetic model.
No HTTP server, no GPU, no cloud credentials, no network required.

Usage:
    python3 examples/think_box_experiment.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from thinkbox.burst import BurstConfig, BurstRunner, synthetic_model
from thinkbox.decomposer import TaskDecomposer, TaskGraph, TaskNode
from thinkbox.engine import EngineConfig, ThinkBoxEngine
from thinkbox.grounding import GroundingScorer
from thinkbox.harvest import HarvestReplay
from thinkbox.ledger import ActionLedger
from thinkbox.model_client import AsyncModelClient, ModelConfig
from thinkbox.session import create_session
from thinkbox.swarm import AsyncWorkerPool, ExecutionResult
from thinkbox.workspace import ThinkBox, WorkspaceRegistry, WorkspaceStore


SYNTHETIC_RESPONSES: dict[str, str] = {
    "claim_facts": "fact_geo: Paris is the capital of France. fact_arith: 2+2=4. fact_chem: H2O is water.",
    "claim_analysis": "The evidence supports claim_geo and claim_arith. claim_chem requires verification.",
    "claim_verify": "All claims verified against fact cards. Groundedness: 0.73.",
}


class SyntheticModelClient(AsyncModelClient):
    FACT_CARDS: dict[str, str] = {
        "What is the capital of France?": "fact_geo: Paris is the capital of France",
        "What is 2+2?": "fact_arith: 2+2=4",
        "What is water?": "fact_chem: H2O is water",
    }

    def __init__(self, config: ModelConfig | None = None) -> None:
        pass

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        await asyncio.sleep(0.001)
        for question, card in self.FACT_CARDS.items():
            if question in prompt:
                return card
        for question, card in self.FACT_CARDS.items():
            if question.lower()[:20] in prompt.lower():
                return card
        return "Analyzed with synthetic model — result is deterministic."

    async def stream(self, prompt: str, **kwargs: Any) -> AsyncGenerator[str, None]:
        yield self.generate(prompt, **kwargs)


FACT_CARDS: dict[str, str] = {
    "What is the capital of France?": "fact_geo: Paris is the capital of France",
    "What is 2+2?": "fact_arith: 2+2=4",
    "What is water?": "fact_chem: H2O is water",
}


@dataclass
class ExperimentOutcome:
    session_id: str
    job_id: str
    intent: str
    task_count: int
    successful_tasks: int
    grounding_score: float
    proof_status: str
    outcome: str
    lessons: list[str] = field(default_factory=list)
    next_improvement: str = ""


def run_experiment(
    intent: str = "Analyze three claims against fact cards",
    db_path: str = "data/evals/experiment.db",
) -> ExperimentOutcome:
    create_session(metadata={"intent": intent})

    workspace = ThinkBox(
        box_id=f"box_{uuid.uuid4().hex[:12]}",
        owner_id="kilo",
        capabilities=frozenset(["goal:execute", "file:read", "cnc:simulate"]),
        state={"intent": intent, "phase": "experiment"},
        substrate="local",
    )

    store = WorkspaceStore(db_path)
    store.save(workspace)

    ledger = ActionLedger(db_path)
    ledger.append(
        agent_id="kilo",
        capability="goal:execute",
        action="experiment_start",
        allowed=True,
        reason="Local deterministic experiment",
        metadata={"session_id": workspace.box_id, "intent": intent},
    )

    config = EngineConfig(
        model_config=ModelConfig(),
        speculative=False,
        max_retries=1,
        repo_path=str(Path(__file__).resolve().parent.parent),
    )

    model_client = SyntheticModelClient()
    pool = AsyncWorkerPool(model_client=model_client, max_workers=4)

    engine = ThinkBoxEngine(config)
    engine.swarm = pool

    ledger.append(
        agent_id="kilo",
        capability="goal:execute",
        action="plan_start",
        allowed=True,
        reason="Planning phase",
        metadata={"box_id": workspace.box_id},
    )

    decomposer = TaskDecomposer()
    subtasks = [f"Answer: {q}" for q in FACT_CARDS.keys()]
    graph = decomposer.decompose_with_subtasks(intent, subtasks)

    task_map = graph.tasks
    results: dict[str, Any] = {}
    grounding_scores: list[float] = []
    artifacts: list[dict[str, Any]] = []

    for layer in graph.get_execution_order():
        for task_id in layer:
            task = task_map[task_id]
            description = task.description

            result = asyncio.run(pool.execute_task(task_id, description))
            results[task_id] = result

            artifact = {
                "task_id": task_id,
                "description": description,
                "success": result.success,
                "output": result.output,
                "execution_time_ms": result.execution_time_ms,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            artifacts.append(artifact)

            ledger.append(
                agent_id="kilo",
                capability="goal:execute",
                action=f"task_{task_id}",
                allowed=True,
                reason="Task execution",
                metadata={
                    "task_id": task_id,
                    "output": result.output[:100],
                    "success": result.success,
                },
            )

            scorer = GroundingScorer(threshold=0.3)
            score = scorer.score(
                claim=description,
                evidence=result.output,
                reasoning=result.output,
            )
            grounding_scores.append(score.score)

    ledger.append(
        agent_id="kilo",
        capability="goal:execute",
        action="validate",
        allowed=True,
        reason="Validation phase",
        metadata={"task_count": len(artifacts), "grounding_scores": grounding_scores},
    )

    burst_config = BurstConfig(
        max_pairs=len(artifacts),
        max_calls=len(artifacts) * 2,
        max_spend=1.0,
        output_dir="data/evals/burst",
    )
    burst_report = BurstRunner(config=burst_config, ledger=ledger).run()

    harvest = HarvestReplay().replay_dir(burst_config.output_dir)

    avg_grounding = sum(grounding_scores) / len(grounding_scores) if grounding_scores else 0.0

    successful = sum(1 for r in results.values() if isinstance(r, ExecutionResult) and r.success)

    lessons = []
    for artifact in artifacts:
        if artifact["success"]:
            lessons.append(f"{artifact['task_id']}: completed with grounding {next((g for a, g in zip(artifacts, grounding_scores) if a['task_id'] == artifact['task_id']), 0):.3f}")
        else:
            lessons.append(f"{artifact['task_id']}: FAILED")

    ledger.append(
        agent_id="kilo",
        capability="goal:execute",
        action="experiment_complete",
        allowed=True,
        reason="Experiment completed",
        metadata={
            "tasks": len(artifacts),
            "successful": successful,
            "grounding": avg_grounding,
            "lessons": lessons,
        },
    )

    workspace.state.update({
        "intent": intent,
        "tasks": len(artifacts),
        "successful": successful,
        "grounding": avg_grounding,
        "phase": "complete",
        "artifacts": [a["task_id"] for a in artifacts],
        "lessons": lessons,
        "proof_status": burst_report.groundness_score > 0.5 and "PASS" or "FAIL",
    })
    store.save(workspace)

    engine.emit("root", "SUCCESS", f"Experiment complete: {successful}/{len(artifacts)} tasks")

    next_improvement = (
        "Increase grounding threshold for harder claims; "
        "add more fact cards for uncovered domains."
        if avg_grounding < 0.8
        else "Maintain current configuration; grounding above 0.8."
    )

    return ExperimentOutcome(
        session_id=workspace.box_id,
        job_id=burst_report.burst_id,
        intent=intent,
        task_count=len(artifacts),
        successful_tasks=successful,
        grounding_score=avg_grounding,
        proof_status=burst_report.groundness_score > 0.5 and "PASS" or "FAIL",
        outcome=f"{successful}/{len(artifacts)} tasks completed",
        lessons=lessons,
        next_improvement=next_improvement,
    )


def main() -> None:
    print("=" * 70)
    print("  LOCAL THINK BOX EXPERIMENT LOOP")
    print("  $0 | Deterministic | No Server | SQLite")
    print("=" * 70)
    print()

    start = time.monotonic()
    outcome = run_experiment()
    elapsed = time.monotonic() - start

    print(f"SESSION:      {outcome.session_id}")
    print(f"JOB:          {outcome.job_id}")
    print(f"INTENT:       {outcome.intent}")
    print(f"TASKS:        {outcome.successful_tasks}/{outcome.task_count}")
    print(f"GROUNDING:    {outcome.grounding_score:.4f}")
    print(f"PROOF:        {outcome.proof_status}")
    print(f"OUTCOME:      {outcome.outcome}")
    print(f"DURATION:     {elapsed:.3f}s")
    print()
    print("LESSONS:")
    for lesson in outcome.lessons:
        print(f"  - {lesson}")
    print()
    print(f"NEXT:         {outcome.next_improvement}")
    print()
    print("Persisted to: data/evals/experiment.db")
    print("Replay:         HarvestReplay().replay_dir('data/evals/burst')")


if __name__ == "__main__":
    main()
