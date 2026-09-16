"""Proof package for CNC manufacturing decisions."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ProofPackage:
    proof_id: str = ""
    job_id: str = ""
    evidence_label: str = "simulated"
    decisions: list[dict[str, Any]] = field(default_factory=list)
    validations: list[dict[str, Any]] = field(default_factory=list)
    approvals: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    hash: str = ""

    def __post_init__(self) -> None:
        if not self.proof_id:
            self.proof_id = f"proof-{uuid.uuid4().hex[:8]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        data = json.dumps({"proof_id": self.proof_id, "job_id": self.job_id, "evidence_label": self.evidence_label, "decisions": self.decisions, "validations": self.validations, "approvals": self.approvals}, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def model_dump(self) -> dict[str, Any]:
        return {"proof_id": self.proof_id, "job_id": self.job_id, "evidence_label": self.evidence_label, "decisions": self.decisions, "validations": self.validations, "approvals": self.approvals, "created_at": self.created_at, "hash": self.hash}


class ProofStore:
    def __init__(self, storage_path: str = "data/cnc/proofs"):
        self.storage_path = Path(storage_path)
        self._proofs: list[ProofPackage] = []
        self._load()

    def _load(self) -> None:
        for f in self.storage_path.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                proof = ProofPackage(**data)
                self._proofs.append(proof)
            except (json.JSONDecodeError, ValueError):
                continue

    def create_proof(self, job_id: str, evidence_label: str = "simulated") -> ProofPackage:
        proof = ProofPackage(job_id=job_id, evidence_label=evidence_label)
        self._proofs.append(proof)
        self._save(proof)
        return proof

    def _save(self, proof: ProofPackage) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        f = self.storage_path / f"{proof.proof_id}.json"
        f.write_text(json.dumps(proof.model_dump(), indent=2))

    def get_proof(self, proof_id: str) -> ProofPackage | None:
        for p in self._proofs:
            if p.proof_id == proof_id:
                return p
        return None

    def list_proofs(self) -> list[ProofPackage]:
        return self._proofs
