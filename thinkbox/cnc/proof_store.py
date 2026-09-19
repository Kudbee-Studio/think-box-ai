"""Proof store for CNC manufacturing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thinkbox.cnc.proof import ProofPackage


class ProofStore:
    def __init__(self, storage_path: str = "data/cnc/proofs"):
        self.storage_path = Path(storage_path)
        self._proofs: list[ProofPackage] = []
        self._load()

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        for f in self.storage_path.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                proof = ProofPackage(**data)
                self._proofs.append(proof)
            except (json.JSONDecodeError, ValueError):
                continue

    def create_proof(self, job_id: str, evidence_label: str = "simulated") -> ProofPackage:
        from thinkbox.cnc.proof import ProofPackage as PP
        proof = PP(job_id=job_id, evidence_label=evidence_label)
        self._proofs.append(proof)
        self._save(proof)
        return proof

    def _save(self, proof: ProofPackage) -> None:
        self.storage_path.mkdir(parents=True, exist_ok=True)
        f = self.storage_path / f"{proof.proof_id}.json"
        f.write_text(json.dumps(proof.model_dump(), indent=2))

    def get_proof(self, proof_id: str) -> ProofPackage | None:
        for p in self._proofs:
            if p.proof_id == proof_id:
                return p
        return None

    def list_proofs(self) -> list[ProofPackage]:
        return self._proofs

    def query_proofs(self, job_id: str | None = None, evidence_label: str | None = None) -> list[ProofPackage]:
        results = self._proofs
        if job_id is not None:
            results = [p for p in results if p.job_id == job_id]
        if evidence_label is not None:
            results = [p for p in results if p.evidence_label == evidence_label]
        return results
