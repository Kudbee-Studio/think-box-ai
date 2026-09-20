"""Founder merge proof lifecycle — versioned key metadata for audit packets (hermetic).

Does not rotate ``THINKBOX_FOUNDER_MERGE_PROOF_KEY`` at runtime; production
rotation is an operator action outside this module.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from thinkbox.pipeline_dashboard import compute_founder_merge_proof


@dataclass(frozen=True)
class FounderProofKeyMeta:
    version: str
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "fingerprint": self.fingerprint}


def key_fingerprint(proof_key: str) -> str:
    if not proof_key:
        return ""
    return hashlib.sha256(proof_key.encode("utf-8")).hexdigest()[:16]


def build_proof_attestation(
    pr_number: int,
    proof_key: str,
    *,
    key_version: str = "v1",
) -> dict[str, Any]:
    """PR-bound proof + key metadata for audit (never exposes raw key)."""
    proof = compute_founder_merge_proof(pr_number, proof_key)
    meta = FounderProofKeyMeta(version=key_version, fingerprint=key_fingerprint(proof_key))
    return {
        "pr_number": pr_number,
        "founder_proof": proof,
        "key_meta": meta.to_dict(),
        "evidence_label": "simulated",
        "github_merge": False,
    }


def validate_proof_key_rotation(
    current_key: str,
    previous_fingerprint: str,
) -> dict[str, Any]:
    """Rotation guard: current key must differ from retired fingerprint."""
    fp = key_fingerprint(current_key)
    rotated = bool(previous_fingerprint) and fp != previous_fingerprint
    return {
        "current_fingerprint": fp,
        "previous_fingerprint": previous_fingerprint,
        "rotation_detected": rotated,
        "evidence_label": "simulated",
    }
