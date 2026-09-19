"""Safety gates for CNC manufacturing."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EMERGENCY_STOP = "EMERGENCY_STOP"


@dataclass
class ApprovalGate:
    gate_id: str = ""
    job_id: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    approver_id: str = ""
    reason: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.gate_id:
            self.gate_id = f"gate-{uuid.uuid4().hex[:8]}"
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def model_dump(self) -> dict[str, Any]:
        return {"gate_id": self.gate_id, "job_id": self.job_id, "status": self.status.value, "approver_id": self.approver_id, "reason": self.reason, "timestamp": self.timestamp}


@dataclass
class SafetyGate:
    gate_id: str = ""
    job_id: str = ""
    requires_approval: bool = True
    is_safe: bool = True
    issues: list[str] = field(default_factory=list)
    checks_passed: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.gate_id:
            self.gate_id = f"sg-{uuid.uuid4().hex[:8]}"

    def check_safety(self) -> SafetyGate:
        self.is_safe = len(self.issues) == 0
        return self

    def model_dump(self) -> dict[str, Any]:
        return {"gate_id": self.gate_id, "job_id": self.job_id, "requires_approval": self.requires_approval, "is_safe": self.is_safe, "issues": self.issues, "checks_passed": self.checks_passed}


class SafetyGateStore:
    def __init__(self, storage_path: str = "data/cnc/safety"):
        self.storage_path = Path(storage_path)
        self._gates: list[ApprovalGate] = []
        self._load()

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        for f in self.storage_path.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                gate = ApprovalGate(**data)
                self._gates.append(gate)
            except (json.JSONDecodeError, ValueError):
                continue

    def _save(self, gate: ApprovalGate) -> None:
        self.storage_path.mkdir(parents=True, exist_ok=True)
        f = self.storage_path / f"{gate.gate_id}.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(gate.model_dump(), indent=2))

    def approve(self, job_id: str, approver_id: str, reason: str = "") -> ApprovalGate:
        gate = ApprovalGate(job_id=job_id, approver_id=approver_id, reason=reason, status=ApprovalStatus.APPROVED)
        self._gates.append(gate)
        self._save(gate)
        return gate

    def emergency_stop(self, job_id: str = "all") -> list[ApprovalGate]:
        stopped = []
        for gate in self._gates:
            if job_id == "all" or gate.job_id == job_id:
                gate.status = ApprovalStatus.EMERGENCY_STOP
                stopped.append(gate)
        return stopped

    def list_gates(self) -> list[ApprovalGate]:
        return self._gates

    def get_gate(self, gate_id: str) -> ApprovalGate | None:
        for g in self._gates:
            if g.gate_id == gate_id:
                return g
        return None

    def get_gate_by_job_id(self, job_id: str) -> ApprovalGate | None:
        for g in self._gates:
            if g.job_id == job_id:
                return g
        return None

    def approve(self, job_id: str, approver_id: str, reason: str = "") -> ApprovalGate:
        gate = ApprovalGate(job_id=job_id, approver_id=approver_id, reason=reason, status=ApprovalStatus.APPROVED)
        self._gates.append(gate)
        self._save(gate)
        return gate

    def emergency_stop(self, job_id: str = "all") -> list[ApprovalGate]:
        stopped = []
        for gate in self._gates:
            if job_id == "all" or gate.job_id == job_id:
                gate.status = ApprovalStatus.EMERGENCY_STOP
                stopped.append(gate)
        return stopped

    def list_gates(self) -> list[ApprovalGate]:
        return self._gates

    def get_gate(self, gate_id: str) -> ApprovalGate | None:
        for g in self._gates:
            if g.gate_id == gate_id:
                return g
        return None
