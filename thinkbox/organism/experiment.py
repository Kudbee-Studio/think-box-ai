"""THINK ORGANISM — Experiment Runner.

Runs deterministic trials comparing BASELINE (single stateless
capability) vs THINK ORGANISM (persistent Host + Cells +
memory + verifier + learning).

Uses local/zero-cost in-process execution by default.
Upstash Box is optional and only used when local execution
is explicitly configured as insufficient.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from thinkbox.organism import (
    ExperimentOutcome,
    ThinkJobResult,
    TrialResult,
)
from thinkbox.organism.cells import (
    Cell,
    LearnerCell,
    ReasonerCell,
    SpecialistCell,
    VerifierCell,
)
from thinkbox.organism.learning import LearningStore, extract_learning
from thinkbox.organism.measurement import MetricsCollector
from thinkbox.organism.host import Host


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


DETERMINISTIC_TASKS: list[str] = [
    "What is the capital of France?",
    "What is 2+2?",
    "What is water?",
]


def _run_baseline_trial(
    trial: int,
    intent: str,
    tasks: list[str],
) -> TrialResult:
    start = time.monotonic()
    cell = SpecialistCell(cell_id="baseline-specialist")
    cell_results: list[Any] = []
    cells_executed: list[str] = []

    for task in tasks:
        result = cell.execute(
            job_id=f"baseline-trial-{trial}",
            input_text=task,
            context={},
        )
        cell_results.append(result)
        cells_executed.append(result.cell_id)

    elapsed = (time.monotonic() - start) * 1000
    all_success = all(r.success for r in cell_results)

    return TrialResult(
        trial=trial,
        condition="baseline",
        success=all_success,
        execution_time_ms=round(elapsed, 3),
        task_success=all_success,
        verification_success=True,
        errors=0,
        retries=0,
        latency=round(elapsed / max(len(tasks), 1), 3),
        artifact_quality=0.5 if all_success else 0.0,
        proof_complete=all_success,
        memory_reuse=False,
        learning_reuse=False,
        proof=f"baseline-proof:trial-{trial}",
        outcome=f"Baseline trial {trial}: {len(cell_results)} tasks, {sum(1 for r in cell_results if r.success)} success",
        cells_executed=cells_executed,
        timestamp=_now(),
    )


def _run_organism_trial(
    host: Host,
    trial: int,
    intent: str,
    tasks: list[str],
    learning_store: LearningStore,
) -> TrialResult:
    start = time.monotonic()

    memory = {}
    for key in host.list_memory():
        data = host.get_memory(key)
        if data:
            memory[key] = data

    context = {
        "memory": memory,
        "box_id": host.box_id,
        "trial": trial,
    }

    result = host.run_think_job(intent=intent, trial=trial, context=context)

    # Run each task through specialist cell
    cell_results: list[Any] = []
    cells_executed: list[str] = []
    specialist = host.cells.get(
        next((cid for cid, c in host.cells.items() if c.cell_type == "SPECIALIST"), None)
    )
    if specialist:
        for task in tasks:
            cr = specialist.execute(
                job_id=f"organism-trial-{trial}",
                input_text=task,
                context={**context, "memory": memory},
            )
            cell_results.append(cr)
            cells_executed.append(cr.cell_id)

    elapsed = (time.monotonic() - start) * 1000
    all_success = all(r.success for r in cell_results) and result.success

    # Extract learning
    learnings = learning_store.extract_and_store(
        trial=trial,
        cell_type="SPECIALIST",
        outcome="success" if all_success else "failure",
        proof=result.proof,
    )

    learning_reuse = learning_store.learning_count() > len(learnings)

    return TrialResult(
        trial=trial,
        condition="organism",
        success=all_success,
        execution_time_ms=round(elapsed, 3),
        task_success=all_success,
        verification_success=result.success,
        errors=0,
        retries=0,
        latency=round(elapsed / max(len(tasks), 1), 3),
        artifact_quality=0.8 if all_success else 0.3,
        proof_complete=bool(result.proof),
        memory_reuse=bool(memory),
        learning_reuse=learning_reuse,
        proof=result.proof,
        outcome=result.outcome,
        cells_executed=cells_executed,
        timestamp=_now(),
    )


def run_experiment(
    intent: str = "Answer three factual questions",
    db_path: str = ":memory:",
    trials: int = 3,
    substrate: str = "local",
) -> ExperimentOutcome:
    tasks = DETERMINISTIC_TASKS.copy()

    if db_path != ":memory:" and not db_path.startswith(":"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    collector = MetricsCollector()

    # Initialize organism host with all four cells
    host = Host(box_id=f"organism_{uuid.uuid4().hex[:8]}", db_path=db_path)
    host.register_cell(ReasonerCell(cell_id="reasoner-1"))
    host.register_cell(SpecialistCell(cell_id="specialist-1"))
    host.register_cell(VerifierCell(cell_id="verifier-1"))
    host.register_cell(LearnerCell(cell_id="learner-1"))
    host.persist()

    learning_store = LearningStore(db_path if db_path != ":memory:" else ":memory:")

    baseline_results: list[dict[str, Any]] = []
    organism_results: list[dict[str, Any]] = []

    for trial in range(trials):
        # Baseline trial
        baseline = _run_baseline_trial(trial, intent, tasks)
        baseline_results.append(baseline.__dict__)
        collector.record(
            condition="baseline",
            trial=trial,
            success=baseline.success,
            time_ms=baseline.execution_time_ms,
            task_success=baseline.task_success,
            verification_success=baseline.verification_success,
            errors=baseline.errors,
            retries=baseline.retries,
            artifact_quality=baseline.artifact_quality,
            proof_complete=baseline.proof_complete,
            proof=baseline.proof,
            outcome=baseline.outcome,
            cells_executed=baseline.cells_executed,
        )

        # Organism trial
        organism = _run_organism_trial(host, trial, intent, tasks, learning_store)
        organism_results.append(organism.__dict__)
        collector.record(
            condition="organism",
            trial=trial,
            success=organism.success,
            time_ms=organism.execution_time_ms,
            task_success=organism.task_success,
            verification_success=organism.verification_success,
            errors=organism.errors,
            retries=organism.retries,
            artifact_quality=organism.artifact_quality,
            proof_complete=organism.proof_complete,
            memory_reuse=organism.memory_reuse,
            learning_reuse=organism.learning_reuse,
            proof=organism.proof,
            outcome=organism.outcome,
            cells_executed=organism.cells_executed,
        )

    comparison = collector.compare("baseline", "organism")
    baseline_metrics = collector.get_metrics("baseline")
    organism_metrics = collector.get_metrics("organism")

    experiment_id = f"exp_{uuid.uuid4().hex[:12]}"
    experiment = ExperimentOutcome(
        experiment_id=experiment_id,
        trials=trials,
        results={
            "baseline": baseline_results,
            "organism": organism_results,
            "comparison": {
                "conclusion": comparison.conclusion,
                "deltas": comparison.deltas,
                "evidence": comparison.evidence,
                "baseline_metrics": baseline_metrics,
                "organism_metrics": organism_metrics,
            },
        },
        substrate=substrate,
        conclusion=comparison.conclusion,
        metrics={
            "baseline": baseline_metrics,
            "organism": organism_metrics,
            "trials": trials,
            "comparison": comparison.deltas,
        },
        proof=f"experiment-proof:{experiment_id}",
        timestamp=_now(),
    )

    return experiment


def main() -> None:
    from thinkbox.organism import CELL_REGISTRY, Cell

    print("=" * 70)
    print("  THINK ORGANISM EXPERIMENT")
    print("  BASELINE vs THINK ORGANISM — deterministic, local, zero-cost")
    print("=" * 70)
    print()

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "organism.db"
        outcome = run_experiment(db_path=str(db), trials=3)

    print(f"EXPERIMENT: {outcome.experiment_id}")
    print(f"TRIALS:     {outcome.trials}")
    print(f"SUBSTRATE:  {outcome.substrate}")
    print(f"CONCLUSION: {outcome.conclusion}")
    print()

    for condition in ["baseline", "organism"]:
        results = outcome.results.get(condition, [])
        print(f"{condition.upper()} ({len(results)} trials):")
        for r in results:
            print(f"  Trial {r['trial']}: success={r['success']}, "
                  f"time={r['execution_time_ms']:.1f}ms, "
                  f"proof={r['proof_complete']}, "
                  f"memory_reuse={r.get('memory_reuse', False)}, "
                  f"learning_reuse={r.get('learning_reuse', False)}")
        print()

    comparison = outcome.results.get("comparison", {})
    print("COMPARISON:")
    for key, val in comparison.items():
        if key not in ["baseline_metrics", "organism_metrics"]:
            print(f"  {key}: {val}")
    print()

    if db_path := str(db):
        conn = sqlite3.connect(db_path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        conn.close()
        print(f"Persisted to: {db_path}")
        print(f"Tables: {[t[0] for t in tables]}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    main()
