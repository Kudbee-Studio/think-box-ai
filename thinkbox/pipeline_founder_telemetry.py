"""Founder proof validation telemetry (redacted)."""

from __future__ import annotations

from typing import Any

from thinkbox.pipeline_dashboard import verify_founder_merge_proof
from thinkbox.pipeline_founder_proof_lifecycle import key_fingerprint


def founder_proof_validation_event(
    pr_number: int,
    proof_key: str,
    proof: str,
    *,
    correlation_id: str = "",
) -> dict[str, Any]:
    """Record-safe outcome of PR-bound founder proof check."""
    ok = verify_founder_merge_proof(pr_number, proof_key, proof)
    return {
        "pr_number": pr_number,
        "proof_valid": ok,
        "proof_length": len(proof or ""),
        "key_fingerprint": key_fingerprint(proof_key),
        "correlation_id": correlation_id,
        "pr_bound": True,
        "evidence_label": "verified" if ok else "rejected",
        "secrets_exposed": False,
    }
