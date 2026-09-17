"""THINK ORGANISM — HOST + SPECIALIZED CAPABILITY + FEEDBACK pattern.

A persistent Think Box containing specialized capabilities that
interact through shared memory, policy, execution, feedback,
validation, and proof. Designed for testable computational
improvement through repeated Think Jobs.

This is NOT a biological system. It is a deterministic,
measurable experiment architecture.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from thinkbox.organism.cells import CellResult, CellType


@dataclass
class CellRegistration:
    cell_id: str
    cell_type: str
    capability: str
    description: str = ""


@dataclass
class ThinkJobResult:
    job_id: str = ""
    intent: str = ""
    trial: int = 0
    cell_results: list[CellResult] = field(default_factory=list)
    proof: str = ""
    outcome: str = ""
    success: bool = False
    execution_time_ms: float = 0.0
    memory_used: bool = False
    learning_applied: bool = False
    substrate: str = "local"
    timestamp: str = ""
    ledger_entries: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ExperimentOutcome:
    experiment_id: str = ""
    trials: int = 0
    results: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    comparison: dict[str, Any] = field(default_factory=dict)
    substrate: str = "local"
    conclusion: str = "INCONCLUSIVE"
    metrics: dict[str, Any] = field(default_factory=dict)
    proof: str = ""
    timestamp: str = ""


@dataclass
class TrialResult:
    trial: int = 0
    condition: str = ""
    success: bool = False
    execution_time_ms: float = 0.0
    latency: float = 0.0
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
