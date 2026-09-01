"""ThinkBox Cross-Model Consensus — Multi-LLM voting and aggregation.

Features:
11. MultiModelVoting — Aggregate outputs from multiple LLMs
12. ConfidenceScoring — Bayesian confidence estimation
13. DisagreementResolver — Escalation protocol for disagreements
14. ModelRankingEngine — Dynamic model ranking by task type
15. ConsensusAuditTrail — Immutable record of consensus decisions
"""

from __future__ import annotations

import hashlib
import json
import statistics
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ModelOutput:
    model_id: str
    output: str
    confidence: float = 0.5
    latency_ms: float = 0.0
    token_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsensusResult:
    consensus_id: str
    task_id: str
    winning_output: str
    winning_model: str
    agreement_score: float
    model_outputs: list[ModelOutput]
    method: str = "majority_vote"
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class ConfidenceScorer:
    @staticmethod
    def bayes_confidence(output: str, model_reliability: float, prior: float = 0.5) -> float:
        output_length = len(output)
        has_structure = any(marker in output for marker in ["def ", "class ", "import ", "{", "}", "```"])
        has_content = output_length > 50

        likelihood = 0.5
        if has_structure:
            likelihood += 0.2
        if has_content:
            likelihood += 0.15
        if output_length > 200:
            likelihood += 0.1

        posterior = (likelihood * model_reliability) / (
            (likelihood * model_reliability) + ((1 - likelihood) * (1 - model_reliability))
        ) if (likelihood * model_reliability) + ((1 - likelihood) * (1 - model_reliability)) > 0 else prior

        return round(posterior, 4)

    @staticmethod
    def length_score(output: str, expected_range: tuple[int, int] = (100, 2000)) -> float:
        length = len(output)
        min_len, max_len = expected_range
        if min_len <= length <= max_len:
            return 1.0
        if length < min_len:
            return max(0.1, length / min_len)
        return max(0.1, max_len / length)


class MultiModelVoting:
    def __init__(self) -> None:
        self._models: dict[str, float] = {}
        self._lock = threading.Lock()

    def register_model(self, model_id: str, reliability: float = 0.8) -> None:
        with self._lock:
            self._models[model_id] = reliability

    def vote(self, task_id: str, outputs: list[ModelOutput]) -> ConsensusResult:
        if not outputs:
            return ConsensusResult(
                consensus_id=f"cons_{uuid.uuid4().hex[:8]}",
                task_id=task_id,
                winning_output="",
                winning_model="none",
                agreement_score=0.0,
                model_outputs=[],
                method="no_outputs",
            )

        if len(outputs) == 1:
            return ConsensusResult(
                consensus_id=f"cons_{uuid.uuid4().hex[:8]}",
                task_id=task_id,
                winning_output=outputs[0].output,
                winning_model=outputs[0].model_id,
                agreement_score=1.0,
                model_outputs=outputs,
                method="single_model",
            )

        for output in outputs:
            reliability = self._models.get(output.model_id, 0.7)
            output.confidence = ConfidenceScorer.bayes_confidence(output.output, reliability)

        scored = sorted(outputs, key=lambda o: o.confidence, reverse=True)
        winner = scored[0]

        agreement = self._calculate_agreement(outputs)

        return ConsensusResult(
            consensus_id=f"cons_{uuid.uuid4().hex[:8]}",
            task_id=task_id,
            winning_output=winner.output,
            winning_model=winner.model_id,
            agreement_score=agreement,
            model_outputs=outputs,
            method="weighted_vote",
        )

    def _calculate_agreement(self, outputs: list[ModelOutput]) -> float:
        if len(outputs) <= 1:
            return 1.0

        confidences = [o.confidence for o in outputs]
        if not confidences:
            return 0.0

        mean_conf = statistics.mean(confidences)
        variance = statistics.variance(confidences) if len(confidences) > 1 else 0

        agreement = mean_conf * (1 - min(variance, 1.0))
        return round(max(0.0, min(1.0, agreement)), 4)


class DisagreementResolver:
    def __init__(self, consensus_threshold: float = 0.6) -> None:
        self._threshold = consensus_threshold

    def resolve(self, consensus_result: ConsensusResult) -> tuple[str, str]:
        if consensus_result.agreement_score >= self._threshold:
            return "accepted", consensus_result.winning_output

        if consensus_result.agreement_score >= 0.4:
            top_outputs = sorted(
                consensus_result.model_outputs,
                key=lambda o: o.confidence,
                reverse=True,
            )[:2]
            best = top_outputs[0]
            return "accepted_with_caution", best.output

        return "escalate", self._build_escalation_prompt(consensus_result)

    def _build_escalation_prompt(self, result: ConsensusResult) -> str:
        prompt = "Multiple models disagree. Please review the following outputs and select the best:\n\n"
        for i, output in enumerate(result.model_outputs, 1):
            prompt += f"--- Model {i} ({output.model_id}, confidence: {output.confidence:.2f}) ---\n"
            prompt += output.output[:500] + "\n\n"
        prompt += "Select the best output or provide a corrected version."
        return prompt


class ModelRankingEngine:
    def __init__(self) -> None:
        self._rankings: dict[str, dict[str, dict[str, float]]] = {}
        self._lock = threading.Lock()

    def record_result(self, model_id: str, task_type: str, success: bool, latency_ms: float, quality: float = 0.5) -> None:
        with self._lock:
            if task_type not in self._rankings:
                self._rankings[task_type] = {}
            if model_id not in self._rankings[task_type]:
                self._rankings[task_type][model_id] = {
                    "success_rate": 0.0,
                    "avg_latency_ms": 0.0,
                    "quality_score": 0.0,
                    "tasks_completed": 0,
                }

            stats = self._rankings[task_type][model_id]
            n = stats["tasks_completed"]
            stats["success_rate"] = (stats["success_rate"] * n + (1.0 if success else 0.0)) / (n + 1)
            stats["avg_latency_ms"] = (stats["avg_latency_ms"] * n + latency_ms) / (n + 1)
            stats["quality_score"] = (stats["quality_score"] * n + quality) / (n + 1)
            stats["tasks_completed"] = n + 1

    def get_ranking(self, task_type: str) -> list[tuple[str, float]]:
        with self._lock:
            models = self._rankings.get(task_type, {})
            if not models:
                return []

            scored = []
            for model_id, stats in models.items():
                if stats["tasks_completed"] < 3:
                    continue
                score = (
                    stats["success_rate"] * 0.4
                    + stats["quality_score"] * 0.4
                    + (1.0 / (1.0 + stats["avg_latency_ms"] / 1000)) * 0.2
                )
                scored.append((model_id, round(score, 4)))

            return sorted(scored, key=lambda x: x[1], reverse=True)

    def get_best_model(self, task_type: str) -> str | None:
        rankings = self.get_ranking(task_type)
        return rankings[0][0] if rankings else None


class ConsensusAuditTrail:
    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def record(self, consensus_result: ConsensusResult) -> str:
        record = {
            "consensus_id": consensus_result.consensus_id,
            "task_id": consensus_result.task_id,
            "winning_model": consensus_result.winning_model,
            "agreement_score": consensus_result.agreement_score,
            "method": consensus_result.method,
            "timestamp": consensus_result.timestamp,
            "model_count": len(consensus_result.model_outputs),
            "record_hash": "",
        }
        record["record_hash"] = hashlib.sha256(
            json.dumps(record, sort_keys=True).encode()
        ).hexdigest()[:16]

        with self._lock:
            self._records.append(record)

        return record["record_hash"]

    def get_trail(self, task_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            records = self._records
            if task_id:
                records = [r for r in records if r["task_id"] == task_id]
            return records[-limit:]
