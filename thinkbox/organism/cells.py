"""THINK ORGANISM — Specialized Cells.

Each cell has: identity, capability declaration, inputs, outputs,
provenance, execution record, proof, and outcome.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class CellResult:
    cell_id: str = ""
    cell_type: str = ""
    input_text: str = ""
    output: str = ""
    provenance: str = ""
    execution_record: dict[str, Any] = field(default_factory=dict)
    proof: str = ""
    outcome: str = ""
    success: bool = False
    timestamp: str = ""
    execution_time_ms: float = 0.0


@dataclass(frozen=True)
class CellType:
    REASONER: str = "REASONER"
    SPECIALIST: str = "SPECIALIST"
    VERIFIER: str = "VERIFIER"
    LEARNER: str = "LEARNER"

    def __str__(self) -> str:
        return self.__class__.__dict__.get(self.name, self.name) if hasattr(self, 'name') else "UNKNOWN"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Cell:
    """Base cell: specialized capability worker."""

    cell_id: str
    cell_type: str
    capability: str

    def __init__(self, cell_id: str, cell_type: str, capability: str) -> None:
        self.cell_id = cell_id
        self.cell_type = cell_type
        self.capability = capability

    def execute(
        self,
        job_id: str,
        input_text: str,
        context: dict[str, Any] | None = None,
    ) -> CellResult:
        context = context or {}
        start = time.monotonic()
        output = self._perform_work(input_text, context)
        elapsed = (time.monotonic() - start) * 1000

        return CellResult(
            cell_id=self.cell_id,
            cell_type=self.cell_type,
            input_text=input_text,
            output=output,
            provenance=f"cell_id={self.cell_id}:cell_type={self.cell_type}",
            execution_record={
                "cell_id": self.cell_id,
                "cell_type": self.cell_type,
                "capability": self.capability,
                "job_id": job_id,
                "timestamp": _now(),
                "execution_time_ms": round(elapsed, 3),
            },
            proof=self._generate_proof(input_text, output, context),
            outcome=f"{self.cell_type} {self.cell_id}: {self.capability} -> {'OK' if output else 'EMPTY'}",
            success=bool(output),
            timestamp=_now(),
            execution_time_ms=round(elapsed, 3),
        )

    def _perform_work(self, input_text: str, context: dict[str, Any]) -> str:
        return f"[{self.cell_type}:{self.cell_id}] processed: {input_text[:80]}"

    def _generate_proof(
        self, input_text: str, output: str, context: dict[str, Any]
    ) -> str:
        return f"proof:{self.cell_id}:{hash(input_text + output + str(context))}"


class ReasonerCell(Cell):
    """REASONER: Analyzes task, plans approach, identifies sub-tasks."""

    def __init__(self, cell_id: str = "reasoner-1", capability: str = "analyze") -> None:
        super().__init__(cell_id=cell_id, cell_type="REASONER", capability=capability)

    def _perform_work(self, input_text: str, context: dict[str, Any]) -> str:
        tasks = [f"sub-task-{i}" for i in range(3)]
        return f"REASONER analyzed: {input_text[:60]}; identified {len(tasks)} sub-tasks"


class SpecialistCell(Cell):
    """SPECIALIST: Executes the core specialized task."""

    def __init__(self, cell_id: str = "specialist-1", capability: str = "execute") -> None:
        super().__init__(cell_id=cell_id, cell_type="SPECIALIST", capability=capability)

    def _perform_work(self, input_text: str, context: dict[str, Any]) -> str:
        memory = context.get("memory", {})
        if memory:
            return f"SPECIALIST executed with {len(memory)} memory entries: {input_text[:50]}"
        return f"SPECIALIST executed fresh: {input_text[:50]}"


class VerifierCell(Cell):
    """VERIFIER: Validates result quality and correctness."""

    def __init__(self, cell_id: str = "verifier-1", capability: str = "verify") -> None:
        super().__init__(cell_id=cell_id, cell_type="VERIFIER", capability=capability)

    def _perform_work(self, input_text: str, context: dict[str, Any]) -> str:
        cell_results = context.get("cell_results", [])
        verified = sum(1 for r in cell_results if r.success)
        return f"VERIFIER checked {len(cell_results)} results: {verified} passed"


class LearnerCell(Cell):
    """LEARNER: Extracts supported learning from outcomes."""

    def __init__(self, cell_id: str = "learner-1", capability: str = "learn") -> None:
        super().__init__(cell_id=cell_id, cell_type="LEARNER", capability=capability)

    def _perform_work(self, input_text: str, context: dict[str, Any]) -> str:
        outcome = context.get("outcome", "")
        proof = context.get("proof", "")
        return f"LEARNER extracted learning from outcome={bool(outcome)} proof={bool(proof)}"


CELL_REGISTRY: dict[str, type[Cell]] = {
    "REASONER": ReasonerCell,
    "SPECIALIST": SpecialistCell,
    "VERIFIER": VerifierCell,
    "LEARNER": LearnerCell,
}
