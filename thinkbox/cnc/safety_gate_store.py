"""Safety gate store for CNC manufacturing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thinkbox.cnc.safety import ApprovalGate, ApprovalStatus


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
