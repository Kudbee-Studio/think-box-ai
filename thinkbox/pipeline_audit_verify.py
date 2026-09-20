"""Verify founder audit packet attestations."""

from __future__ import annotations

from typing import Any

from thinkbox.pipeline_audit_packet import attest_audit_packet


def verify_audit_packet(payload: dict[str, Any], *, attestation_key: str) -> dict[str, Any]:
    """Recompute HMAC over packet body (attestation field excluded)."""
    body = dict(payload)
    claimed = str(body.pop("attestation", "") or "")
    if not claimed:
        return {"verified": False, "reason": "missing_attestation", "evidence_label": "rejected"}
    expected = attest_audit_packet(body, attestation_key)
    ok = expected == claimed
    return {
        "verified": ok,
        "reason": "ok" if ok else "attestation_mismatch",
        "packet_digest": body.get("packet_digest"),
        "evidence_label": "verified" if ok else "rejected",
        "auto_merge": False,
    }
