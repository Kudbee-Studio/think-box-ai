"""Governance token rotation safeguards (hermetic)."""

from __future__ import annotations

from typing import Any

from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.identity import IdentityLedger


def issue_rotated_token(
    *,
    signing_key: str,
    agent_id: str,
    capabilities: list[str],
    ttl_seconds: float = 3600.0,
) -> dict[str, Any]:
    tokens = GovernanceTokenService(signing_key=signing_key)
    identities = IdentityLedger()
    identities.register(agent_id=agent_id, capabilities=capabilities)
    issued = tokens.issue(
        TokenRequest(agent_id=agent_id, capabilities=capabilities, ttl_seconds=ttl_seconds)
    )
    stale = tokens.verify("invalid-token-value")
    return {
        "token_issued": bool(issued.token_value),
        "stale_rejected": stale is None,
        "agent_id": agent_id,
        "capabilities": capabilities,
        "evidence_label": "simulated",
    }
