"""THINK ORGANISM — Metrics Collection and Comparison."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrialMetrics:
    trial: int = 0
    condition: str = ""
    success: bool = False
    execution_time_ms: float = 0.0
    task_success: bool = False
    verification_success: bool = False
    errors: int = 0
    retries: int = 0
    artifact_quality: float = 0.0
    proof_complete: bool = False
    memory_reuse: bool = False
    learning_reuse: bool = False
    proof: str = ""
    outcome: str = ""
    cells_executed: list[str] = field(default_factory=list)
    timestamp: str = ""


@dataclass
class Comparison:
    baseline: dict[str, float] = field(default_factory=dict)
    organism: dict[str, float] = field(default_factory=dict)
    deltas: dict[str, float] = field(default_factory=dict)
    conclusion: str = "INCONCLUSIVE"
    evidence: str = ""


class MetricsCollector:
    def __init__(self) -> None:
        self._data: dict[str, list[TrialMetrics]] = {}

    def record(
        self,
        condition: str,
        trial: int,
        success: bool,
        time_ms: float,
        task_success: bool = False,
        verification_success: bool = False,
        errors: int = 0,
        retries: int = 0,
        artifact_quality: float = 0.0,
        proof_complete: bool = False,
        memory_reuse: bool = False,
        learning_reuse: bool = False,
        proof: str = "",
        outcome: str = "",
        cells_executed: list[str] | None = None,
    ) -> None:
        cells = cells_executed or []
        metrics = TrialMetrics(
            trial=trial, condition=condition, success=success,
            execution_time_ms=time_ms, task_success=task_success,
            verification_success=verification_success, errors=errors,
            retries=retries, artifact_quality=artifact_quality,
            proof_complete=proof_complete, memory_reuse=memory_reuse,
            learning_reuse=learning_reuse, proof=proof[:200],
            outcome=outcome[:200], cells_executed=cells, timestamp="",
        )
        if condition not in self._data:
            self._data[condition] = []
        self._data[condition].append(metrics)

    def get_metrics(self, condition: str) -> dict[str, Any]:
        trials = self._data.get(condition, [])
        if not trials:
            return {condition: {"condition": condition, "trials": 0}}
        metrics = {
            "condition": condition,
            "trials": len(trials),
            "avg_time_ms": sum(t.execution_time_ms for t in trials) / len(trials),
            "success_rate": sum(1 for t in trials if t.success) / len(trials),
            "task_success_rate": sum(1 for t in trials if t.task_success) / len(trials),
            "verification_rate": sum(1 for t in trials if t.verification_success) / len(trials),
            "avg_errors": sum(t.errors for t in trials) / len(trials),
            "avg_retries": sum(t.retries for t in trials) / len(trials),
            "avg_artifact_quality": sum(t.artifact_quality for t in trials) / len(trials),
            "proof_complete_rate": sum(1 for t in trials if t.proof_complete) / len(trials),
            "memory_reuse_count": sum(1 for t in trials if t.memory_reuse),
            "learning_reuse_count": sum(1 for t in trials if t.learning_reuse),
        }
        return {condition: metrics}

    def compare(self, condition_a: str, condition_b: str) -> Comparison:
        a_data = self.get_metrics(condition_a)
        b_data = self.get_metrics(condition_b)
        metrics_a = a_data.get(condition_a, {})
        metrics_b = b_data.get(condition_b, {})

        deltas: dict[str, float] = {}
        for key in [
            "avg_time_ms", "success_rate", "task_success_rate",
            "verification_rate", "avg_errors", "avg_retries",
            "avg_artifact_quality", "proof_complete_rate",
        ]:
            val_a = metrics_a.get(key, 0)
            val_b = metrics_b.get(key, 0)
            if val_b != 0:
                deltas[key] = ((val_a - val_b) / abs(val_b)) * 100
            else:
                deltas[key] = 0.0

        conclusion = self.classify(condition_b, condition_a)
        return Comparison(
            baseline=metrics_a, organism=metrics_b,
            deltas=deltas, conclusion=conclusion,
            evidence=f"Compared {condition_a} ({metrics_a.get('trials', 0)} trials) vs {condition_b} ({metrics_b.get('trials', 0)} trials)",
        )

    def classify(self, condition_a: str, condition_b: str) -> str:
        a_data = self.get_metrics(condition_a)
        b_data = self.get_metrics(condition_b)
        metrics_a = a_data.get(condition_a, {})
        metrics_b = b_data.get(condition_b, {})

        if metrics_b.get("trials", 0) == 0:
            return "FAILED"
        if metrics_a.get("trials", 0) == 0:
            return "INCONCLUSIVE"

        b_success = metrics_b.get("success_rate", 0)
        a_success = metrics_a.get("success_rate", 0)
        b_quality = metrics_b.get("avg_artifact_quality", 0)
        a_quality = metrics_a.get("avg_artifact_quality", 0)
        b_proof = metrics_b.get("proof_complete_rate", 0)
        a_proof = metrics_a.get("proof_complete_rate", 0)
        b_time = metrics_b.get("avg_time_ms", 0)
        a_time = metrics_a.get("avg_time_ms", 0)

        improvements = 0
        regressions = 0
        if b_success > a_success: improvements += 1
        elif b_success < a_success: regressions += 1
        if b_quality > a_quality: improvements += 1
        elif b_quality < a_quality: regressions += 1
        if b_proof > a_proof: improvements += 1
        elif b_proof < a_proof: regressions += 1
        if b_time < a_time and a_time > 0: improvements += 1

        if improvements >= 3: return "IMPROVED"
        if regressions >= 2: return "REGRESSION"
        if improvements == 0 and regressions == 0: return "NO MEASURABLE IMPROVEMENT"
        if improvements == regressions: return "INCONCLUSIVE"
        if improvements > regressions: return "IMPROVED"
        return "INCONCLUSIVE"


def format_comparison(comparison: Comparison) -> str:
    lines = [
        "=== EXPERIMENT COMPARISON ===",
        f"Baseline: {comparison.baseline.get('trials', 0)} trials",
        f"Organism: {comparison.organism.get('trials', 0)} trials",
        f"Conclusion: {comparison.conclusion}",
        f"Evidence: {comparison.evidence}",
        "",
        "Deltas (organism - baseline, %):",
    ]
    for key, delta in comparison.deltas.items():
        lines.append(f"  {key}: {delta:+.1f}%")
    return "\n".join(lines)
