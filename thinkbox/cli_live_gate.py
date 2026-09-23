"""KUDBEECLI Phase 2 — fail-closed live credential gate (authorization check only)."""

from __future__ import annotations

import os
from typing import Any

# Founder must set explicit ack; provider key alone is insufficient.
_ACK_ENV = "THINKBOX_SWARM_LIVE_ACK"
_PROVIDER_KEYS = (
    "INCEPTION_API_KEY",
    "THINKBOX_OPENAI_COMPAT_API_KEY",
)


def swarm_live_authorization_report() -> dict[str, Any]:
    """
    Return whether live swarm execution would be permitted.

    Does not perform network I/O. ``authorized`` is True only when a provider
    credential and founder ack are both present.
    """
    ack = os.environ.get(_ACK_ENV, "").strip().lower() in ("1", "true", "yes", "accept")
    provider_present = any(os.environ.get(k, "").strip() for k in _PROVIDER_KEYS)
    missing: list[str] = []
    if not provider_present:
        missing.append(f"one of: {', '.join(_PROVIDER_KEYS)}")
    if not ack:
        missing.append(f"{_ACK_ENV}=1 (founder explicit live ack)")
    return {
        "authorized": provider_present and ack,
        "provider_credential_present": provider_present,
        "founder_ack_present": ack,
        "missing": missing,
        "mode": "authorization_check_only",
        "live_api_called": False,
        "evidence_label": "inferred",
    }


def require_swarm_live_authorization() -> tuple[bool, dict[str, Any]]:
    """Convenience wrapper for CLI dispatch."""
    report = swarm_live_authorization_report()
    return bool(report["authorized"]), report
